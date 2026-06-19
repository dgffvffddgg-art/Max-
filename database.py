"""
قاعدة بيانات بسيطة (SQLite) لتخزين عدد إنذارات كل عضو في كل جروب
بتفضل البيانات محفوظة حتى لو البوت اتقفل وفتح تاني
"""
import sqlite3
from contextlib import contextmanager

DB_PATH = "warnings.db"


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS warnings (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )
        # يتتبع نشاط كل عضو في كل يوم: هل اتكلم؟ هل خالف؟
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_activity (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                activity_date TEXT NOT NULL,
                violated INTEGER NOT NULL DEFAULT 0,
                message_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id, activity_date)
            )
            """
        )
        # سياق آخر الرسائل لكل جروب (يستخدم لتحليل الـ AI للجدال)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def get_warning_count(chat_id: int, user_id: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        row = cur.fetchone()
        return row[0] if row else 0


def increment_warning(chat_id: int, user_id: int) -> int:
    """يزود عداد الإنذارات بواحد ويرجع العدد الجديد"""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO warnings (chat_id, user_id, count)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET count = count + 1
            """,
            (chat_id, user_id),
        )
        conn.commit()
        cur = conn.execute(
            "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        return cur.fetchone()[0]


def reset_warnings(chat_id: int, user_id: int):
    """يصفّر عداد الإنذارات (بعد الكتم أو يدوياً من الأدمن)"""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        conn.commit()


# ===== تتبع النشاط اليومي (للتهنئة اليومية) =====

def record_activity(chat_id: int, user_id: int, user_name: str, activity_date: str):
    """يسجل إن العضو اتكلم النهاردة (من غير ما يعتبرها مخالفة بشكل افتراضي)"""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_activity (chat_id, user_id, user_name, activity_date, violated, message_count)
            VALUES (?, ?, ?, ?, 0, 1)
            ON CONFLICT(chat_id, user_id, activity_date)
            DO UPDATE SET message_count = message_count + 1, user_name = excluded.user_name
            """,
            (chat_id, user_id, user_name, activity_date),
        )
        conn.commit()


def mark_violation_today(chat_id: int, user_id: int, user_name: str, activity_date: str):
    """يعلّم إن العضو خالف القوانين النهاردة (يستبعده من تهنئة الالتزام)"""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_activity (chat_id, user_id, user_name, activity_date, violated, message_count)
            VALUES (?, ?, ?, ?, 1, 1)
            ON CONFLICT(chat_id, user_id, activity_date)
            DO UPDATE SET violated = 1, user_name = excluded.user_name
            """,
            (chat_id, user_id, user_name, activity_date),
        )
        conn.commit()


def get_compliant_members(chat_id: int, activity_date: str) -> list[tuple[int, str]]:
    """يرجع قائمة (user_id, user_name) لكل عضو اتكلم النهاردة من غير أي مخالفة"""
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT user_id, user_name FROM daily_activity
            WHERE chat_id = ? AND activity_date = ? AND violated = 0
            """,
            (chat_id, activity_date),
        )
        return cur.fetchall()


def get_active_chats_for_date(activity_date: str) -> list[int]:
    """يرجع كل الجروبات اللي فيها نشاط في تاريخ معين"""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT DISTINCT chat_id FROM daily_activity WHERE activity_date = ?",
            (activity_date,),
        )
        return [row[0] for row in cur.fetchall()]


# ===== سياق الرسائل (لتحليل الـ AI) =====

def add_message_to_context(chat_id: int, user_name: str, text: str, created_at: str):
    """يضيف رسالة لسياق المحادثة، ويحتفظ بآخر N رسالة فقط لكل جروب"""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO message_context (chat_id, user_name, text, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, user_name, text, created_at),
        )
        # تنضيف: نسيب آخر 50 رسالة بس لكل جروب عشان الجدول مايكبرش بلا داعي
        conn.execute(
            """
            DELETE FROM message_context
            WHERE chat_id = ? AND id NOT IN (
                SELECT id FROM message_context WHERE chat_id = ?
                ORDER BY id DESC LIMIT 50
            )
            """,
            (chat_id, chat_id),
        )
        conn.commit()


def get_recent_context(chat_id: int, limit: int) -> list[str]:
    """يرجع آخر N رسالة في الجروب (الأقدم أولاً) كنصوص جاهزة للتحليل"""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT user_name, text FROM message_context WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        )
        rows = cur.fetchall()
    rows.reverse()
    return [f"{name}: {text}" for name, text in rows]
