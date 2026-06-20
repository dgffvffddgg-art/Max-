"""
بوت حماية جروبات تليجرام
يراقب الرسائل، يحذف السبام والألفاظ غير اللائقة، وينذر/يكتم الأعضاء المخالفين
كمان بيستخدم AI (Gemini) لاكتشاف الجدال حول الكورة/الدين/السياسة
وبيبعت تهنئة يومية للأعضاء الملتزمين

طريقة التشغيل: python bot.py
"""
import logging
from datetime import timedelta, datetime, time as dt_time
from zoneinfo import ZoneInfo

from telegram import Update, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import ai_moderation
import config
import database
import filters as content_filters

# ===== إعداد اللوج =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# المنطقة الزمنية المستخدمة لحساب "اليوم" (تستخدم في التهنئة اليومية)
TIMEZONE = ZoneInfo("Africa/Cairo")


def get_mention(user) -> str:
    """يرجع منشن قابل للنقر للمستخدم"""
    name = user.full_name or user.username or "العضو"
    return f"[{name}](tg://user?id={user.id})"


async def is_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.warning(f"تعذر التحقق من صلاحيات الأدمن: {e}")
        return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المعالج الرئيسي لكل رسالة نصية في الجروب"""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or chat.type not in ("group", "supergroup"):
        return

    # تجاهل الأدمنز تماماً
    if await is_admin(chat.id, user.id, context):
        return

    text = message.text or message.caption or ""
    if not text:
        return

    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    user_display_name = user.full_name or user.username or f"عضو {user.id}"

    # ===== الفحص بالفلتر التقليدي (سبام/شتايم/فلود) =====
    result = content_filters.analyze_message(chat.id, user.id, text)

    # ===== لو سليمة بالفلتر التقليدي، نفحصها بالـ AI (جدال كورة/دين/سياسة أو هزار/خروج عن الموضوع) =====
    ai_result = {"category": "clean", "topic": None, "reason": None}
    if not result["violation"] and config.AI_MODERATION_ENABLED:
        context_msgs = database.get_recent_context(chat.id, config.CONTEXT_MESSAGES_COUNT)
        context_msgs.append(f"{user_display_name}: {text}")
        ai_result = await ai_moderation.analyze_with_ai(context_msgs)

    # نسجل الرسالة في السياق دايماً (حتى لو مخالفة، عشان السياق يفضل متصل)
    database.add_message_to_context(
        chat.id, user_display_name, text, datetime.now(TIMEZONE).isoformat()
    )

    ai_violation = ai_result["category"] in ("debate", "offtopic", "inappropriate")
    is_violation = result["violation"] or ai_violation

    if not is_violation:
        # رسالة سليمة تماماً -> تُحسب كنشاط ملتزم اليوم
        database.record_activity(chat.id, user.id, user_display_name, today_str)
        return

    # ===== حذف الرسالة المخالفة =====
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"تعذر حذف الرسالة: {e}")
        return

    # العضو خالف النهاردة -> يُستبعد من تهنئة الالتزام اليومي
    database.mark_violation_today(chat.id, user.id, user_display_name, today_str)

    mention = get_mention(user)

    # ===== زيادة عداد الإنذارات =====
    new_count = database.increment_warning(chat.id, user.id)

    if new_count >= config.MAX_WARNINGS:
        # ===== كتم العضو =====
        try:
            until_date = message.date + timedelta(minutes=config.MUTE_DURATION_MINUTES)
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )
            database.reset_warnings(chat.id, user.id)
            mute_text = config.MUTE_MESSAGE_TEMPLATE.format(
                mention=mention,
                duration=config.MUTE_DURATION_MINUTES,
                max=config.MAX_WARNINGS,
            )
            sent = await context.bot.send_message(
                chat_id=chat.id, text=mute_text, parse_mode=ParseMode.MARKDOWN
            )
            context.job_queue.run_once(
                delete_message_job,
                config.WARNING_MESSAGE_LIFETIME,
                data={"chat_id": chat.id, "message_id": sent.message_id},
            )
        except Exception as e:
            logger.error(f"تعذر كتم العضو: {e}")
    else:
        # ===== إرسال التحذير المناسب حسب نوع المخالفة =====
        if ai_result["category"] == "debate":
            warning_text = config.AI_VIOLATION_WARNING_TEMPLATE.format(mention=mention)
        elif ai_result["category"] == "offtopic":
            warning_text = config.OFFTOPIC_VIOLATION_WARNING_TEMPLATE.format(mention=mention)
        elif ai_result["category"] == "inappropriate":
            warning_text = config.INAPPROPRIATE_LANGUAGE_WARNING_TEMPLATE.format(mention=mention)
        else:
            warning_text = config.WARNING_MESSAGE_TEMPLATE.format(
                mention=mention, count=new_count, max=config.MAX_WARNINGS
            )
        sent = await context.bot.send_message(
            chat_id=chat.id, text=warning_text, parse_mode=ParseMode.MARKDOWN
        )
        # حذف رسالة التحذير تلقائياً بعد فترة عشان متبوظش الجروب
        context.job_queue.run_once(
            delete_message_job,
            config.WARNING_MESSAGE_LIFETIME,
            data={"chat_id": chat.id, "message_id": sent.message_id},
        )

    reason = ai_result["reason"] if ai_violation else result["reason"]
    logger.info(
        f"مخالفة من {user.id} في {chat.id} | السبب: {reason} | الإنذار: {new_count}"
    )


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """مهمة مجدولة لحذف رسالة التحذير/الكتم بعد فترة"""
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except Exception:
        pass  # ممكن تكون اتحذفت بالفعل


# ===== أوامر الأدمن =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ بوت الحماية شغال!\n\n"
        "أضفني كأدمن في الجروب بصلاحية حذف الرسائل وكتم الأعضاء "
        "وهبدأ أراقب وأحذف السبام والألفاظ غير اللائقة تلقائياً."
    )


async def cmd_laws(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض قوانين الجروب لأي عضو يطلبها، وتتمسح الرسالة تلقائياً بعد فترة"""
    sent = await update.message.reply_text(config.GROUP_LAWS_TEXT)
    context.job_queue.run_once(
        delete_message_job,
        config.LAWS_MESSAGE_LIFETIME,
        data={"chat_id": sent.chat_id, "message_id": sent.message_id},
    )


async def cmd_resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يصفّر إنذارات عضو معين (رد على رسالته بالأمر /resetwarn)"""
    chat = update.effective_chat
    user = update.effective_user

    if not await is_admin(chat.id, user.id, context):
        await update.message.reply_text("⛔ الأمر ده للأدمنز بس.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("استخدم الأمر كـ reply على رسالة العضو المطلوب.")
        return

    target = update.message.reply_to_message.from_user
    database.reset_warnings(chat.id, target.id)
    await update.message.reply_text(f"✅ تم تصفير إنذارات {target.full_name}.")


async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض عدد إنذارات عضو معين (رد على رسالته)"""
    chat = update.effective_chat
    if not update.message.reply_to_message:
        await update.message.reply_text("استخدم الأمر كـ reply على رسالة العضو المطلوب.")
        return
    target = update.message.reply_to_message.from_user
    count = database.get_warning_count(chat.id, target.id)
    await update.message.reply_text(
        f"📊 عدد إنذارات {target.full_name}: {count}/{config.MAX_WARNINGS}"
    )


async def send_daily_compliance_messages(context: ContextTypes.DEFAULT_TYPE):
    """
    مهمة مجدولة تشتغل مرة كل يوم: تبعت رسالة واحدة في كل جروب نشط
    بتذكر فيها كل الأعضاء اللي اتكلموا طول اليوم من غير أي مخالفة
    """
    yesterday_str = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%Y-%m-%d")
    active_chats = database.get_active_chats_for_date(yesterday_str)

    for chat_id in active_chats:
        compliant = database.get_compliant_members(chat_id, yesterday_str)
        if not compliant:
            continue
        members_list = "\n".join(
            f"• [{name}](tg://user?id={uid})" for uid, name in compliant
        )
        text = config.DAILY_COMPLIANCE_MESSAGE_TEMPLATE.format(members_list=members_list)
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.warning(f"تعذر إرسال تهنئة الالتزام اليومي لـ {chat_id}: {e}")


def main():
    if not config.BOT_TOKEN:
        raise SystemExit(
            "❌ لازم تحط BOT_TOKEN في ملف .env قبل ما تشغل البوت. راجع .env.example"
        )

    database.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("laws", cmd_laws))
    app.add_handler(CommandHandler("resetwarn", cmd_resetwarn))
    app.add_handler(CommandHandler("warnings", cmd_warnings))
    app.add_handler(
        MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, handle_message)
    )

    # جدولة رسالة التهنئة اليومية: تشتغل الساعة 00:05 بتوقيت القاهرة كل يوم
    # (بتلخص نشاط "أمس" بعد ما يكون اليوم خلص فعلياً)
    app.job_queue.run_daily(
        send_daily_compliance_messages,
        time=dt_time(hour=0, minute=5, tzinfo=TIMEZONE),
    )

    logger.info("🛡️ البوت بدأ يشتغل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
