"""
وحدة التحليل الذكي للرسائل باستخدام Google Gemini (مجاني)
الهدف: اكتشاف "الجدال/المشاحنة" حول الكورة، الدين، أو السياسة
(مش مجرد ذكر الموضوع عرضيًا - لازم يكون فيه نبرة جدال أو خلاف فعلي)

يحتاج: GEMINI_API_KEY في .env
الحصول على المفتاح مجانًا من: https://aistudio.google.com/apikey
"""
import json
import logging

import httpx

import config

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)

SYSTEM_PROMPT = """أنت مساعد مراقبة لجروب تليجرام دراسي. مهمتك تحليل آخر رسائل من محادثة وتحديد:
هل آخر رسالة في المحادثة هي جزء من "جدال أو مشاحنة" (خلاف، نقاش حاد، تراشق، تعصب) حول واحد من المواضيع دي:
- الكورة (مباريات، أندية، لاعبين)
- الدين
- السياسة

مهم جداً:
- مجرد ذكر الموضوع مرة واحدة بشكل عابر أو مزحة خفيفة بدون رد فعل من حد تاني = مش مخالفة
- لازم يكون فيه فعلاً نقاش متصاعد أو خلاف أو حدة في الكلام بين أعضاء حول الموضوع ده
- ركز بشكل خاص على آخر رسالة، والسياق اللي قبلها بيساعدك تفهم هل فيه جدال فعلاً ولا لأ

رد بصيغة JSON فقط بدون أي نص إضافي، بالشكل ده بالظبط:
{"violation": true أو false, "topic": "الكورة" أو "الدين" أو "السياسة" أو null, "reason": "سبب مختصر"}"""


async def check_debate_violation(context_messages: list[str]) -> dict:
    """
    يفحص آخر رسائل المحادثة ويحدد لو فيه جدال عن الكورة/الدين/السياسة
    context_messages: قائمة بآخر الرسائل بالترتيب (الأقدم أولاً، الأحدث آخراً)
    يرجع: {"violation": bool, "topic": str|None, "reason": str}
    """
    if not config.AI_MODERATION_ENABLED or not context_messages:
        return {"violation": False, "topic": None, "reason": "AI moderation disabled"}

    conversation_text = "\n".join(f"- {m}" for m in context_messages)
    user_prompt = f"المحادثة (آخر رسالة هي الأهم):\n{conversation_text}"

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }

    url = GEMINI_ENDPOINT.format(model=config.GEMINI_MODEL, api_key=config.GEMINI_API_KEY)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
        return {
            "violation": bool(result.get("violation", False)),
            "topic": result.get("topic"),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.warning(f"فشل تحليل Gemini: {e}")
        # في حالة فشل الـ API، منمنعش الرسالة (fail-safe: ما نحذفش بدون تأكد)
        return {"violation": False, "topic": None, "reason": f"AI error: {e}"}
