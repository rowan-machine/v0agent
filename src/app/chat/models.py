# src/app/chat/models.py

from ..db import connect

def store_conversation_mindmap(conversation_id: int, mindmap_data: dict):
    """Store mindmap data for a conversation.
    
    Called when a conversation's mindmap is generated or updated.
    Triggers synthesis update if configured.
    
    Args:
        conversation_id: ID of the conversation
        mindmap_data: Dict with 'nodes' and 'edges' keys
    """
    try:
        from ..services.mindmap_synthesis import MindmapSynthesizer
        # Store the mindmap with hierarchy information
        mindmap_id = MindmapSynthesizer.store_conversation_mindmap(
            conversation_id, 
            mindmap_data
        )
        if mindmap_id:
            # Could trigger synthesis update here later
            # await MindmapSynthesizer.generate_synthesis(force=False)
            pass
    except Exception as e:
        # Don't fail conversation on mindmap storage error
        import logging
        logging.error(f"Error storing conversation mindmap: {e}")


def init_chat_tables():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            title TEXT,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,   -- 'user' | 'assistant'
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)
        
        # Add columns if they don't exist (migration for existing DBs)
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN summary TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
        except:
            pass
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN archived INTEGER DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN meeting_id INTEGER")
        except:
            pass
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN document_id INTEGER")
        except:
            pass


def create_conversation(title: str = None, meeting_id: int = None, document_id: int = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, meeting_id, document_id) VALUES (?, ?, ?)",
            (title, meeting_id, document_id)
        )
        return cur.lastrowid


def update_conversation_title(conversation_id: int, title: str):
    with connect() as conn:
        # Check if updated_at column exists
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "updated_at" in cols:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (title, conversation_id)
            )
        else:
            conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (title, conversation_id)
            )


def update_conversation_summary(conversation_id: int, summary: str):
    with connect() as conn:
        # Check if updated_at column exists
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "updated_at" in cols:
            conn.execute(
                "UPDATE conversations SET summary = ?, updated_at = datetime('now') WHERE id = ?",
                (summary, conversation_id)
            )
        else:
            conn.execute(
                "UPDATE conversations SET summary = ? WHERE id = ?",
                (summary, conversation_id)
            )


def get_all_conversations(limit: int = 50, include_archived: bool = False):
    """Get all conversations with their first message preview."""
    with connect() as conn:
        # Check which columns exist
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        has_title = "title" in cols
        has_summary = "summary" in cols
        has_updated_at = "updated_at" in cols
        has_archived = "archived" in cols
        
        # Build query based on available columns
        select_cols = ["c.id", "c.created_at"]
        if has_title:
            select_cols.append("c.title")
        if has_summary:
            select_cols.append("c.summary")
        if has_updated_at:
            select_cols.append("c.updated_at")
            order_by = "COALESCE(c.updated_at, c.created_at)"
        else:
            order_by = "c.created_at"
        if has_archived:
            select_cols.append("c.archived")
        
        # Build WHERE clause
        where_clause = ""
        if has_archived and not include_archived:
            where_clause = "WHERE (c.archived IS NULL OR c.archived = 0)"
        
        rows = conn.execute(
            f"""
            SELECT 
                {', '.join(select_cols)},
                (SELECT content FROM messages WHERE conversation_id = c.id AND role = 'user' ORDER BY created_at ASC LIMIT 1) as first_message,
                (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count
            FROM conversations c
            {where_clause}
            ORDER BY {order_by} DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
    return rows


def get_conversation(conversation_id: int):
    """Get a single conversation by ID."""
    with connect() as conn:
        # Check which columns exist
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        has_title = "title" in cols
        has_summary = "summary" in cols
        has_updated_at = "updated_at" in cols
        has_meeting_id = "meeting_id" in cols
        has_document_id = "document_id" in cols
        
        select_cols = ["id", "created_at"]
        if has_title:
            select_cols.append("title")
        if has_summary:
            select_cols.append("summary")
        if has_updated_at:
            select_cols.append("updated_at")
        if has_meeting_id:
            select_cols.append("meeting_id")
        if has_document_id:
            select_cols.append("document_id")
        
        row = conn.execute(
            f"""
            SELECT {', '.join(select_cols)}
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,)
        ).fetchone()
    return row


def add_message(conversation_id: int, role: str, content: str):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            (conversation_id, role, content),
        )
        # Update conversation updated_at if column exists
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "updated_at" in cols:
            conn.execute(
                "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                (conversation_id,)
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

    # Convert Row objects to dicts for JSON serialization in templates
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def archive_conversation(conversation_id: int):
    """Archive a conversation (soft delete)."""
    with connect() as conn:
        conn.execute(
            "UPDATE conversations SET archived = 1, updated_at = datetime('now') WHERE id = ?",
            (conversation_id,)
        )


def unarchive_conversation(conversation_id: int):
    """Restore an archived conversation."""
    with connect() as conn:
        conn.execute(
            "UPDATE conversations SET archived = 0, updated_at = datetime('now') WHERE id = ?",
            (conversation_id,)
        )


def delete_conversation(conversation_id: int):
    """Delete a conversation and all its messages permanently."""
    with connect() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


def update_conversation_context(conversation_id: int, meeting_id: int = None, document_id: int = None):
    """Update the meeting and document context for a conversation."""
    with connect() as conn:
        conn.execute(
            "UPDATE conversations SET meeting_id = ?, document_id = ?, updated_at = datetime('now') WHERE id = ?",
            (meeting_id, document_id, conversation_id)
        )
