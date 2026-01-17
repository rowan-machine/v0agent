# src/app/chat/models.py

from ..db import connect

def init_chat_tables():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,   -- 'user' | 'assistant'
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)


def create_conversation() -> int:
    with connect() as conn:
        cur = conn.execute("INSERT INTO conversations DEFAULT VALUES")
        return cur.lastrowid


def add_message(conversation_id: int, role: str, content: str):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            (conversation_id, role, content),
        )


def get_recent_messages(conversation_id: int, limit: int = 6):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

    return list(reversed(rows))
