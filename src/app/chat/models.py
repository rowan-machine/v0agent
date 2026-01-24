# src/app/chat/models.py

import asyncio
import logging
from datetime import datetime

from ..db import connect

logger = logging.getLogger(__name__)


def _sync_conversation_to_supabase(conversation_id: int):
    """Background sync conversation to Supabase."""
    try:
        from ..infrastructure.supabase_client import get_supabase_sync
        
        with connect() as conn:
            conv = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,)
            ).fetchone()
            
            if conv:
                sync = get_supabase_sync()
                if sync.is_available:
                    # Run sync in background
                    async def do_sync():
                        supabase_id = await sync.sync_conversation(dict(conv))
                        if supabase_id and not conv["supabase_id"]:
                            # Update local with supabase_id
                            with connect() as c:
                                c.execute(
                                    "UPDATE conversations SET supabase_id = ? WHERE id = ?",
                                    (supabase_id, conversation_id)
                                )
                    
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(do_sync())
                        else:
                            loop.run_until_complete(do_sync())
                    except RuntimeError:
                        # No event loop, run synchronously
                        asyncio.run(do_sync())
    except Exception as e:
        logger.warning(f"Failed to sync conversation to Supabase: {e}")


def _sync_message_to_supabase(conversation_id: int, role: str, content: str, run_id: str = None):
    """Background sync message to Supabase."""
    try:
        from ..infrastructure.supabase_client import get_supabase_sync
        
        with connect() as conn:
            # Get conversation's supabase_id
            conv = conn.execute(
                "SELECT supabase_id FROM conversations WHERE id = ?",
                (conversation_id,)
            ).fetchone()
            
            if conv and conv["supabase_id"]:
                sync = get_supabase_sync()
                if sync.is_available:
                    message = {
                        "role": role,
                        "content": content,
                        "run_id": run_id,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    async def do_sync():
                        await sync.sync_message(message, conv["supabase_id"])
                    
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(do_sync())
                        else:
                            loop.run_until_complete(do_sync())
                    except RuntimeError:
                        asyncio.run(do_sync())
    except Exception as e:
        logger.warning(f"Failed to sync message to Supabase: {e}")

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
            updated_at TEXT DEFAULT (datetime('now')),
            supabase_id TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,   -- 'user' | 'assistant'
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            run_id TEXT,
            supabase_id TEXT UNIQUE
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
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN supabase_id TEXT UNIQUE")
        except:
            pass
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN run_id TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN supabase_id TEXT UNIQUE")
        except:
            pass


def create_conversation(title: str = None, meeting_id: int = None, document_id: int = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, meeting_id, document_id) VALUES (?, ?, ?)",
            (title, meeting_id, document_id)
        )
        conversation_id = cur.lastrowid
    
    # Sync to Supabase in background
    _sync_conversation_to_supabase(conversation_id)
    
    return conversation_id


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


def add_message(conversation_id: int, role: str, content: str, run_id: str = None):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, run_id)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, run_id),
        )
        # Update conversation updated_at if column exists
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "updated_at" in cols:
            conn.execute(
                "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                (conversation_id,)
            )
    
    # Sync to Supabase in background
    _sync_message_to_supabase(conversation_id, role, content, run_id)


def get_recent_messages(conversation_id: int, limit: int = 6):
    """Get recent messages from a conversation.
    
    Tries Supabase first (for Railway where SQLite is ephemeral),
    falls back to SQLite for local development.
    """
    # Try Supabase first
    try:
        from ..infrastructure.supabase_client import get_supabase_client
        sb = get_supabase_client()
        if sb:
            # First, need to get the supabase_id for this conversation
            # Try to look it up from local DB first
            supabase_conv_id = None
            try:
                with connect() as conn:
                    row = conn.execute(
                        "SELECT supabase_id FROM conversations WHERE id = ?",
                        (conversation_id,)
                    ).fetchone()
                    if row and row["supabase_id"]:
                        supabase_conv_id = row["supabase_id"]
            except:
                pass
            
            # If we have a supabase_id, fetch messages from Supabase
            if supabase_conv_id:
                result = sb.table("messages").select("role, content").eq(
                    "conversation_id", supabase_conv_id
                ).order("created_at", desc=True).limit(limit).execute()
                
                if result.data:
                    logger.debug(f"Got {len(result.data)} messages from Supabase")
                    return [{"role": m["role"], "content": m["content"]} for m in reversed(result.data)]
    except Exception as e:
        logger.debug(f"Supabase messages fetch failed: {e}")
    
    # SQLite fallback
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
