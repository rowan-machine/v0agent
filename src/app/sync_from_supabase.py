"""
Sync data from Supabase to SQLite on startup.

This module handles pulling data from Supabase into the local SQLite database
for production deployments where Supabase is the source of truth.

Uses direct HTTP requests to avoid supabase-py library version conflicts.
"""

import hashlib
import json
import logging
import os
from typing import Dict, List, Optional

import httpx

from .db import connect, table_exists

logger = logging.getLogger(__name__)


def _uuid_to_int(uuid_str: str) -> int:
    """
    Convert a UUID string to a stable integer for SQLite PRIMARY KEY.
    Uses hash to create a consistent integer from UUID.
    
    Args:
        uuid_str: UUID string like "21f66c92-a495-4279-9a32-164b496f4c9d"
        
    Returns:
        Positive integer derived from UUID
    """
    # Use MD5 hash and take first 8 bytes as integer
    hash_bytes = hashlib.md5(uuid_str.encode()).digest()[:8]
    return int.from_bytes(hash_bytes, byteorder='big') & 0x7FFFFFFFFFFFFFFF  # Ensure positive


def _get_supabase_rest_client() -> Optional[httpx.Client]:
    """
    Create a simple HTTP client for Supabase REST API.
    Bypasses supabase-py library to avoid version conflicts.
    
    Returns:
        httpx.Client configured for Supabase, or None if not configured
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.warning("⚠️ SUPABASE_URL or SUPABASE_KEY not configured")
        return None
    
    # Create client with Supabase headers
    client = httpx.Client(
        base_url=f"{supabase_url}/rest/v1",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        },
        timeout=30.0
    )
    
    return client


def _fetch_from_supabase(table: str, order_by: str = "created_at", limit: int = 100) -> List[Dict]:
    """
    Fetch data from a Supabase table using direct REST API.
    
    Args:
        table: Table name
        order_by: Column to order by (descending)
        limit: Max rows to fetch
        
    Returns:
        List of row dictionaries
    """
    client = _get_supabase_rest_client()
    if not client:
        return []
    
    try:
        response = client.get(
            f"/{table}",
            params={
                "order": f"{order_by}.desc",
                "limit": str(limit)
            }
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"❌ Failed to fetch from {table}: {e}")
        return []
    finally:
        client.close()


def sync_meetings_from_supabase() -> int:
    """
    Pull meetings from Supabase and insert into local SQLite.
    
    Returns:
        Number of meetings synced
    """
    meetings = _fetch_from_supabase("meetings", "created_at", 100)
    
    if not meetings:
        logger.info("No meetings found in Supabase or failed to fetch")
        return 0
    
    synced = 0
    with connect() as conn:
        for meeting in meetings:
            # Convert UUID to integer for SQLite PRIMARY KEY
            meeting_id = _uuid_to_int(meeting["id"])
            
            # Convert signals JSONB to JSON string
            signals = meeting.get("signals", {})
            signals_json = json.dumps(signals) if signals else None
            
            # Check if already exists
            existing = conn.execute(
                "SELECT id FROM meeting_summaries WHERE id = ?",
                (meeting_id,)
            ).fetchone()
            
            if existing:
                continue
            
            # Map Supabase meeting to SQLite schema
            try:
                conn.execute("""
                    INSERT INTO meeting_summaries 
                    (id, meeting_name, synthesized_notes, meeting_date, signals_json, raw_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    meeting_id,
                    meeting.get("meeting_name", "Untitled Meeting"),
                    meeting.get("synthesized_notes", ""),
                    meeting.get("meeting_date"),
                    signals_json,
                    meeting.get("raw_text"),
                    meeting.get("created_at"),
                ))
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync meeting {meeting.get('id')}: {e}")
        
        conn.commit()
    
    logger.info(f"✅ Synced {synced} meetings from Supabase to SQLite")
    return synced


def sync_documents_from_supabase() -> int:
    """
    Pull documents from Supabase and insert into local SQLite.
    
    Returns:
        Number of documents synced
    """
    documents = _fetch_from_supabase("documents", "created_at", 100)
    
    if not documents:
        logger.info("No documents found in Supabase or failed to fetch")
        return 0
    
    synced = 0
    with connect() as conn:
        for doc in documents:
            # Convert UUID to integer for SQLite PRIMARY KEY
            doc_id = _uuid_to_int(doc["id"])
            
            # Check if already exists
            existing = conn.execute(
                "SELECT id FROM docs WHERE id = ?",
                (doc_id,)
            ).fetchone()
            
            if existing:
                continue
            
            # Map Supabase document to SQLite schema
            try:
                conn.execute("""
                    INSERT INTO docs 
                    (id, source, content, document_date, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    doc_id,
                    doc.get("source", "Untitled Document"),
                    doc.get("content", ""),
                    doc.get("document_date"),
                    doc.get("created_at"),
                ))
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync document {doc.get('id')}: {e}")
        
        conn.commit()
    
    logger.info(f"✅ Synced {synced} documents from Supabase to SQLite")
    return synced


def sync_tickets_from_supabase() -> int:
    """
    Pull tickets from Supabase and insert into local SQLite.
    
    Returns:
        Number of tickets synced
    """
    tickets = _fetch_from_supabase("tickets", "created_at", 100)
    
    if not tickets:
        return 0
    
    synced = 0
    with connect() as conn:
        for ticket in tickets:
            existing = conn.execute(
                "SELECT id FROM tickets WHERE ticket_id = ?",
                (ticket.get("ticket_id"),)
            ).fetchone()
            
            if existing:
                continue
            
            try:
                conn.execute("""
                    INSERT INTO tickets 
                    (ticket_id, title, description, status, priority, sprint_points, 
                     in_sprint, ai_summary, implementation_plan, task_decomposition, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket.get("ticket_id"),
                    ticket.get("title", ""),
                    ticket.get("description"),
                    ticket.get("status", "backlog"),
                    ticket.get("priority"),
                    ticket.get("sprint_points", 0),
                    1 if ticket.get("in_sprint") else 0,
                    ticket.get("ai_summary"),
                    ticket.get("implementation_plan"),
                    json.dumps(ticket.get("task_decomposition")) if ticket.get("task_decomposition") else None,
                    ticket.get("created_at"),
                ))
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync ticket {ticket.get('ticket_id')}: {e}")
        
        conn.commit()
    
    logger.info(f"✅ Synced {synced} tickets from Supabase to SQLite")
    return synced


def sync_dikw_from_supabase() -> int:
    """
    Pull DIKW items from Supabase and insert into local SQLite.
    
    Returns:
        Number of items synced
    """
    items = _fetch_from_supabase("dikw_items", "created_at", 200)
    
    if not items:
        return 0
    
    synced = 0
    with connect() as conn:
        # Ensure table exists
        if not table_exists(conn, "dikw_items"):
            logger.warning("dikw_items table not found in SQLite")
            return 0
        
        for item in items:
            # Convert UUID to integer for SQLite PRIMARY KEY
            item_id = _uuid_to_int(item["id"])
            meeting_id = _uuid_to_int(item["meeting_id"]) if item.get("meeting_id") else None
            
            existing = conn.execute(
                "SELECT id FROM dikw_items WHERE id = ?",
                (item_id,)
            ).fetchone()
            
            if existing:
                continue
            
            try:
                tags = item.get("tags", [])
                tags_json = json.dumps(tags) if tags else None
                
                conn.execute("""
                    INSERT INTO dikw_items 
                    (id, level, content, summary, source_type, meeting_id, 
                     tags, confidence, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_id,
                    item.get("level", "data"),
                    item.get("content", ""),
                    item.get("summary"),
                    item.get("source_type"),
                    meeting_id,
                    tags_json,
                    item.get("confidence", 0.5),
                    item.get("status", "active"),
                    item.get("created_at"),
                ))
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync DIKW item {item.get('id')}: {e}")
        
        conn.commit()
    
    logger.info(f"✅ Synced {synced} DIKW items from Supabase to SQLite")
    return synced


def sync_signal_status_from_supabase() -> int:
    """
    Pull signal status from Supabase and insert into local SQLite.
    
    Returns:
        Number of items synced
    """
    items = _fetch_from_supabase("signal_status", "created_at", 200)
    
    if not items:
        return 0
    
    synced = 0
    with connect() as conn:
        if not table_exists(conn, "signal_status"):
            logger.warning("signal_status table not found in SQLite")
            return 0
        
        for status in items:
            # Convert UUIDs to integers for SQLite PRIMARY KEY
            status_id = _uuid_to_int(status["id"])
            meeting_id = _uuid_to_int(status["meeting_id"]) if status.get("meeting_id") else None
            
            existing = conn.execute(
                "SELECT id FROM signal_status WHERE id = ?",
                (status_id,)
            ).fetchone()
            
            if existing:
                continue
            
            try:
                conn.execute("""
                    INSERT INTO signal_status 
                    (id, meeting_id, signal_type, signal_text, status, 
                     converted_to, converted_ref_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    status_id,
                    meeting_id,
                    status.get("signal_type"),
                    status.get("signal_text"),
                    status.get("status", "pending"),
                    status.get("converted_to"),
                    status.get("converted_ref_id"),
                    status.get("created_at"),
                ))
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync signal status {status.get('id')}: {e}")
        
        conn.commit()
    
    logger.info(f"✅ Synced {synced} signal statuses from Supabase to SQLite")
    return synced


def sync_conversations_from_supabase() -> int:
    """
    Sync conversations and messages from Supabase to SQLite.
    
    Returns:
        Number of conversations synced
    """
    # Fetch conversations
    conversations = _fetch_from_supabase("conversations", order_by="updated_at", limit=200)
    
    if not conversations:
        logger.info("No conversations found in Supabase to sync")
        return 0
    
    synced = 0
    
    with connect() as conn:
        # Ensure tables exist
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            title TEXT,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            archived INTEGER DEFAULT 0,
            meeting_id INTEGER,
            document_id INTEGER,
            supabase_id TEXT UNIQUE
        );
        
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            run_id TEXT,
            supabase_id TEXT UNIQUE
        );
        """)
        
        # Add supabase_id column if missing
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN supabase_id TEXT UNIQUE")
        except:
            pass
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN supabase_id TEXT UNIQUE")
        except:
            pass
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN run_id TEXT")
        except:
            pass
        
        for conv in conversations:
            try:
                supabase_id = conv.get("id")
                
                # Check if conversation already exists
                existing = conn.execute(
                    "SELECT id FROM conversations WHERE supabase_id = ?",
                    (supabase_id,)
                ).fetchone()
                
                if existing:
                    # Update existing
                    conn.execute("""
                        UPDATE conversations SET
                            title = ?,
                            summary = ?,
                            updated_at = ?,
                            archived = ?
                        WHERE supabase_id = ?
                    """, (
                        conv.get("title"),
                        conv.get("summary"),
                        conv.get("updated_at"),
                        1 if conv.get("archived") else 0,
                        supabase_id
                    ))
                    conversation_id = existing[0]
                else:
                    # Insert new
                    cur = conn.execute("""
                        INSERT INTO conversations (title, summary, created_at, updated_at, archived, supabase_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        conv.get("title"),
                        conv.get("summary"),
                        conv.get("created_at"),
                        conv.get("updated_at"),
                        1 if conv.get("archived") else 0,
                        supabase_id
                    ))
                    conversation_id = cur.lastrowid
                
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync conversation {conv.get('id')}: {e}")
        
        conn.commit()
    
    # Now sync messages for these conversations
    messages_synced = _sync_messages_from_supabase()
    
    logger.info(f"✅ Synced {synced} conversations and {messages_synced} messages from Supabase to SQLite")
    return synced


def _sync_messages_from_supabase() -> int:
    """
    Sync messages for all conversations from Supabase.
    
    Returns:
        Number of messages synced
    """
    # Fetch recent messages (limit 1000 for recent conversations)
    messages = _fetch_from_supabase("messages", order_by="created_at", limit=1000)
    
    if not messages:
        return 0
    
    synced = 0
    
    with connect() as conn:
        # Build mapping of supabase_id to local conversation_id
        conv_mapping = {}
        rows = conn.execute("SELECT id, supabase_id FROM conversations WHERE supabase_id IS NOT NULL").fetchall()
        for row in rows:
            conv_mapping[row[1]] = row[0]
        
        for msg in messages:
            try:
                supabase_conv_id = msg.get("conversation_id")
                local_conv_id = conv_mapping.get(supabase_conv_id)
                
                if not local_conv_id:
                    # Skip messages for conversations we don't have
                    continue
                
                supabase_id = msg.get("id")
                
                # Check if message already exists
                existing = conn.execute(
                    "SELECT id FROM messages WHERE supabase_id = ?",
                    (supabase_id,)
                ).fetchone()
                
                if not existing:
                    conn.execute("""
                        INSERT INTO messages (conversation_id, role, content, created_at, run_id, supabase_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        local_conv_id,
                        msg.get("role"),
                        msg.get("content"),
                        msg.get("created_at"),
                        msg.get("run_id"),
                        supabase_id
                    ))
                    synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync message {msg.get('id')}: {e}")
        
        conn.commit()
    
    return synced


def sync_all_from_supabase() -> Dict[str, int]:
    """
    Sync all data from Supabase to SQLite.
    
    Returns:
        Dict of table names to number of items synced
    """
    results = {}
    
    # Only sync in production or if explicitly enabled
    env = os.environ.get("ENVIRONMENT", "development")
    force_sync = os.environ.get("FORCE_SUPABASE_SYNC", "").lower() == "true"
    
    if env != "production" and not force_sync:
        logger.info("Skipping Supabase→SQLite sync (not in production)")
        return results
    
    logger.info("🔄 Starting Supabase → SQLite sync...")
    
    results["meetings"] = sync_meetings_from_supabase()
    results["documents"] = sync_documents_from_supabase()
    results["tickets"] = sync_tickets_from_supabase()
    results["dikw_items"] = sync_dikw_from_supabase()
    results["signal_status"] = sync_signal_status_from_supabase()
    results["conversations"] = sync_conversations_from_supabase()
    
    total = sum(results.values())
    logger.info(f"✅ Sync complete: {total} items synced from Supabase")
    
    return results