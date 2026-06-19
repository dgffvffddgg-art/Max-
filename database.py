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
