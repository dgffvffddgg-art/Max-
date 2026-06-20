"""
وحدة التحليل الذكي للرسائل باستخدام Google Gemini (مجاني)
الهدف: تصنيف آخر رسالة في المحادثة إلى واحدة من 3 حالات:
  1. "clean"    -> سليمة (تحية، شكر، رد عادي قصير، أو كلام عن الدراسة)
  2. "debate"   -> جدال/مشاحنة حول الكورة أو الدين أو السياسة
  3. "offtopic" -> هزار/مزح أو خروج عن موضوع الدراسة (بدون جدال)

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

SYSTEM_PROMPT = """أنت مساعد مراقبة لجروب تليجرام دراسي. مهمتك تحليل آخر رسالة في محادثة (بالاستعانة بالسياق اللي قبلها) وتصنيفها إلى واحدة من 3 حالات بالظبط:

1) "clean" — الرسالة سليمة ومسموح بيها، حتى لو مش عن الدراسة بحت، طالما هي:
   - تحية (صباح الخير، السلام عليكم)
   - شكر أو رد فعل قصير عادي (تسلم، تمام، مبروك، ربنا يوفقك)
   - أي كلام له علاقة بالدراسة (المدرس، المنهج، الامتحانات، الملازم، الواجبات)
   - سؤال أو نقاش جدي قصير وعادي بين الأعضاء

2) "debate" — جدال أو مشاحنة فعلية (خلاف، نقاش حاد، تراشق، تعصب) حول:
   - الكورة (مباريات، أندية، لاعبين)
   - الدين
   - السياسة
   مهم: لازم يكون فيه فعلاً تصاعد/خلاف/حدة، مش مجرد ذكر عابر للموضوع.

3) "offtopic" — هزار، مزح، نكت، أو نقاش (حتى لو هادئ ومن غير خلاف) عن موضوع
   مالوش علاقة بالدراسة ولا بالتحية/الشكر العادي (أفلام، ألعاب، حياة شخصية، ميمز، قصص مضحكة، إلخ)
   ومش جدال عن كورة/دين/سياسة (لو كان جدال عن المواضيع دي يبقى "debate" مش "offtopic")

قاعدة مهمة: لو في شك، أو الرسالة قصيرة وغامضة ومحتمل تكون رد فعل عادي، صنّفها "clean".

رد بصيغة JSON فقط بدون أي نص إضافي، بالشكل ده بالظبط:
{"category": "clean" أو "debate" أو "offtopic", "topic": "الكورة" أو "الدين" أو "السياسة" أو null, "reason": "سبب مختصر"}"""


async def analyze_with_ai(context_messages: list[str]) -> dict:
    """
    يفحص آخر رسائل المحادثة ويصنف آخر رسالة فيها.
    context_messages: قائمة بآخر الرسائل بالترتيب (الأقدم أولاً، الأحدث آخراً)
    يرجع: {"category": "clean"|"debate"|"offtopic", "topic": str|None, "reason": str}
    """
    if not config.AI_MODERATION_ENABLED or not context_messages:
        return {"category": "clean", "topic": None, "reason": "AI moderation disabled"}

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
        category = result.get("category", "clean")
        if category not in ("clean", "debate", "offtopic"):
            category = "clean"
        return {
            "category": category,
            "topic": result.get("topic"),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.warning(f"فشل تحليل Gemini: {e}")
        # في حالة فشل الـ API، منمنعش الرسالة (fail-safe: ما نحذفش بدون تأكد)
        return {"category": "clean", "topic": None, "reason": f"AI error: {e}"}
