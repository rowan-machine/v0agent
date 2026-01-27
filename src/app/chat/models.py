# src/app/chat/models.py
"""
Chat models - Supabase-only implementation.
All conversation and message data is stored in Supabase.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def _get_supabase():
    """Get Supabase client, raises if unavailable."""
    from ..infrastructure.supabase_client import get_supabase_client
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not available")
    return client


def store_conversation_mindmap(conversation_id: int, mindmap_data: dict):
    """Store mindmap data for a conversation.
    
    Called when a conversation's mindmap is generated or updated.
    
    Args:
        conversation_id: ID of the conversation
        mindmap_data: Dict with 'nodes' and 'edges' keys
    """
    try:
        from ..services.mindmap_synthesis import MindmapSynthesizer
        mindmap_id = MindmapSynthesizer.store_conversation_mindmap(
            conversation_id, 
            mindmap_data
        )
        if mindmap_id:
            logger.debug(f"Stored mindmap {mindmap_id} for conversation {conversation_id}")
    except Exception as e:
        logger.error(f"Error storing conversation mindmap: {e}")


def init_chat_tables():
    """No-op for Supabase - tables are managed via migrations."""
    logger.info("Chat tables managed in Supabase (no local init needed)")


def create_conversation(title: str = None, meeting_id: int = None, document_id: int = None) -> int:
    """Create a new conversation in Supabase."""
    sb = _get_supabase()
    
    data = {
        "title": title,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "archived": False,
    }
    if meeting_id:
        data["meeting_id"] = meeting_id
    if document_id:
        data["document_id"] = document_id
    
    result = sb.table("conversations").insert(data).execute()
    if not result.data:
        raise RuntimeError("Failed to create conversation in Supabase")
    
    conversation_id = result.data[0]["id"]
    logger.info(f"Created conversation {conversation_id}")
    return conversation_id


def update_conversation_title(conversation_id: int, title: str):
    """Update conversation title."""
    sb = _get_supabase()
    sb.table("conversations").update({
        "title": title,
        "updated_at": datetime.now().isoformat()
    }).eq("id", conversation_id).execute()


def update_conversation_summary(conversation_id: int, summary: str):
    """Update conversation summary."""
    sb = _get_supabase()
    sb.table("conversations").update({
        "summary": summary,
        "updated_at": datetime.now().isoformat()
    }).eq("id", conversation_id).execute()


def get_all_conversations(limit: int = 50, include_archived: bool = False) -> List[Dict[str, Any]]:
    """Get all conversations with message counts."""
    sb = _get_supabase()
    
    query = sb.table("conversations").select("*")
    
    if not include_archived:
        query = query.or_("archived.is.null,archived.eq.false")
    
    result = query.order("updated_at", desc=True).limit(limit).execute()
    
    conversations = []
    for conv in result.data or []:
        # Get first message and message count
        messages_result = sb.table("messages").select("content, role").eq(
            "conversation_id", conv["id"]
        ).order("created_at").execute()
        
        messages = messages_result.data or []
        first_user_msg = next((m for m in messages if m["role"] == "user"), None)
        
        conversations.append({
            "id": conv["id"],
            "title": conv.get("title"),
            "summary": conv.get("summary"),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
            "archived": conv.get("archived", False),
            "first_message": first_user_msg["content"] if first_user_msg else None,
            "message_count": len(messages),
        })
    
    return conversations


def get_conversation(conversation_id: int) -> Optional[Dict[str, Any]]:
    """Get a single conversation by ID."""
    sb = _get_supabase()
    
    result = sb.table("conversations").select("*").eq("id", conversation_id).execute()
    
    if not result.data:
        return None
    
    return dict(result.data[0])


def add_message(conversation_id: int, role: str, content: str, run_id: str = None):
    """Add a message to a conversation."""
    sb = _get_supabase()
    
    data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": datetime.now().isoformat(),
    }
    if run_id:
        data["run_id"] = run_id
    
    sb.table("messages").insert(data).execute()
    
    # Update conversation's updated_at
    sb.table("conversations").update({
        "updated_at": datetime.now().isoformat()
    }).eq("id", conversation_id).execute()
    
    logger.debug(f"Added {role} message to conversation {conversation_id}")


def get_recent_messages(conversation_id: int, limit: int = 50) -> List[Dict[str, str]]:
    """Get recent messages from a conversation."""
    sb = _get_supabase()
    
    result = sb.table("messages").select("role, content, created_at").eq(
        "conversation_id", conversation_id
    ).order("created_at", desc=True).limit(limit).execute()
    
    # Return in chronological order (oldest first)
    messages = result.data or []
    return [{"role": m["role"], "content": m["content"]} for m in reversed(messages)]


def archive_conversation(conversation_id: int):
    """Archive a conversation (soft delete)."""
    sb = _get_supabase()
    sb.table("conversations").update({
        "archived": True,
        "updated_at": datetime.now().isoformat()
    }).eq("id", conversation_id).execute()


def unarchive_conversation(conversation_id: int):
    """Restore an archived conversation."""
    sb = _get_supabase()
    sb.table("conversations").update({
        "archived": False,
        "updated_at": datetime.now().isoformat()
    }).eq("id", conversation_id).execute()


def delete_conversation(conversation_id: int):
    """Delete a conversation and all its messages permanently."""
    sb = _get_supabase()
    
    # Delete messages first (foreign key constraint)
    sb.table("messages").delete().eq("conversation_id", conversation_id).execute()
    # Delete conversation
    sb.table("conversations").delete().eq("id", conversation_id).execute()
    
    logger.info(f"Deleted conversation {conversation_id}")


def update_conversation_context(conversation_id: int, meeting_id: int = None, document_id: int = None):
    """Update the meeting and document context for a conversation."""
    sb = _get_supabase()
    
    update_data = {"updated_at": datetime.now().isoformat()}
    if meeting_id is not None:
        update_data["meeting_id"] = meeting_id
    if document_id is not None:
        update_data["document_id"] = document_id
    
    sb.table("conversations").update(update_data).eq("id", conversation_id).execute()
