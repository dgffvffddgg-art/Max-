"""
بوت حماية جروبات تليجرام
يراقب الرسائل، يحذف السبام والألفاظ غير اللائقة، وينذر/يكتم الأعضاء المخالفين

طريقة التشغيل: python bot.py
"""
import logging
from datetime import timedelta

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

import config
import database
import filters as content_filters

# ===== إعداد اللوج =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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

    result = content_filters.analyze_message(chat.id, user.id, text)
    if not result["violation"]:
        return

    # ===== حذف الرسالة المخالفة =====
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"تعذر حذف الرسالة: {e}")
        return

    # ===== زيادة عداد الإنذارات =====
    new_count = database.increment_warning(chat.id, user.id)
    mention = get_mention(user)

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
        # ===== إرسال تحذير =====
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

    logger.info(
        f"مخالفة من {user.id} في {chat.id} | السبب: {result['reason']} | الإنذار: {new_count}"
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


def main():
    if not config.BOT_TOKEN:
        raise SystemExit(
            "❌ لازم تحط BOT_TOKEN في ملف .env قبل ما تشغل البوت. راجع .env.example"
        )

    database.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("resetwarn", cmd_resetwarn))
    app.add_handler(CommandHandler("warnings", cmd_warnings))
    app.add_handler(
        MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, handle_message)
    )

    logger.info("🛡️ البوت بدأ يشتغل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
