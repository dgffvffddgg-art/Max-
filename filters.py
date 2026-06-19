"""
منطق كشف الرسائل الضارة: شتايم، سبام إعلاني، فلود، روابط مشبوهة
"""
import re
import time
from collections import defaultdict, deque

import config

# ===== تطبيع النص (إزالة الحيل الشائعة للتحايل على الفلتر) =====
ARABIC_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u0640]")


def normalize_text(text: str) -> str:
    """تنضيف النص من التشكيل والمسافات الزايدة والرموز المستخدمة للتحايل"""
    if not text:
        return ""
    text = ARABIC_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    # إزالة الرموز الفاصلة بين الحروف اللي بيتحايلوا بيها زي (ك.ل.ب)
    text = re.sub(r"[\.\-_\*\+]", "", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def contains_banned_word(text: str) -> str | None:
    """يرجع الكلمة الممنوعة لو لقاها، أو None لو مفيش"""
    normalized = normalize_text(text)
    for word in config.BANNED_WORDS:
        norm_word = normalize_text(word)
        if norm_word and norm_word in normalized:
            return word
    return None


def contains_spam_keyword(text: str) -> str | None:
    """يرجع كلمة السبام لو لقاها"""
    normalized = normalize_text(text)
    for kw in config.SPAM_KEYWORDS:
        if normalize_text(kw) in normalized:
            return kw
    return None


def has_excessive_repeated_chars(text: str) -> bool:
    """يكشف تكرار حرف واحد بشكل مبالغ فيه زي: ههههههههههه"""
    return bool(re.search(r"(.)\1{" + str(config.MAX_REPEATED_CHARS - 1) + ",}", text))


def count_links(text: str) -> int:
    url_pattern = re.compile(
        r"(https?://\S+|www\.\S+|t\.me/\S+|@\w+\.(com|net|org|io))", re.IGNORECASE
    )
    return len(url_pattern.findall(text or ""))


def has_excessive_links(text: str) -> bool:
    return count_links(text) > config.MAX_LINKS_PER_MESSAGE


class FloodTracker:
    """يتتبع تكرار الرسائل والفلود لكل مستخدم في كل جروب"""

    def __init__(self):
        # (chat_id, user_id) -> deque[timestamps]
        self._timestamps: dict[tuple, deque] = defaultdict(deque)
        # (chat_id, user_id) -> deque[last messages text]
        self._last_messages: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=5))

    def register_message(self, chat_id: int, user_id: int, text: str) -> dict:
        """يسجل رسالة جديدة ويرجع نتيجة الفحص: is_flood, is_duplicate_spam"""
        key = (chat_id, user_id)
        now = time.time()

        # فحص الفلود (عدد رسائل كتير في وقت قصير)
        dq = self._timestamps[key]
        dq.append(now)
        while dq and now - dq[0] > config.TIME_WINDOW_SECONDS:
            dq.popleft()
        is_flood = len(dq) > config.MAX_MESSAGES_PER_WINDOW

        # فحص تكرار نفس الرسالة
        msgs = self._last_messages[key]
        normalized = normalize_text(text)
        msgs.append(normalized)
        recent_same = sum(1 for m in msgs if m == normalized and normalized)
        is_duplicate_spam = recent_same >= config.MAX_CONSECUTIVE_DUPLICATE_MSGS

        return {"is_flood": is_flood, "is_duplicate_spam": is_duplicate_spam}


flood_tracker = FloodTracker()


def analyze_message(chat_id: int, user_id: int, text: str) -> dict:
    """
    الدالة الرئيسية لتحليل الرسالة.
    ترجع dict فيه: violation (bool), reason (str | None)
    """
    if not text:
        return {"violation": False, "reason": None}

    banned = contains_banned_word(text)
    if banned:
        return {"violation": True, "reason": "ألفاظ غير لائقة"}

    spam_kw = contains_spam_keyword(text)
    if spam_kw:
        return {"violation": True, "reason": "محتوى إعلاني/سبام"}

    if has_excessive_links(text):
        return {"violation": True, "reason": "عدد روابط مبالغ فيه"}

    if has_excessive_repeated_chars(text):
        return {"violation": True, "reason": "تكرار حروف مبالغ فيه (سبام)"}

    flood_result = flood_tracker.register_message(chat_id, user_id, text)
    if flood_result["is_flood"]:
        return {"violation": True, "reason": "إرسال رسائل بمعدل سريع جداً (فلود)"}
    if flood_result["is_duplicate_spam"]:
        return {"violation": True, "reason": "تكرار نفس الرسالة عدة مرات"}

    return {"violation": False, "reason": None}
