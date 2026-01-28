# src/app/domains/knowledge_graph/api/helpers.py
"""
Knowledge Graph Helper Functions

Shared utilities for knowledge graph operations.
"""

import logging
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def get_entity_title(entity_type: str, entity_id: int, supabase) -> str:
    """Get the title/name of an entity."""
    try:
        if entity_type == "meeting":
            result = supabase.table("meetings").select("meeting_name").eq("id", entity_id).execute()
            rows = result.data or []
            return rows[0]["meeting_name"] if rows else "Unknown Meeting"
        elif entity_type == "document":
            result = supabase.table("documents").select("source").eq("id", entity_id).execute()
            rows = result.data or []
            return rows[0]["source"] if rows else "Unknown Document"
        elif entity_type == "ticket":
            result = supabase.table("tickets").select("ticket_id, title").eq("id", entity_id).execute()
            rows = result.data or []
            return f"{rows[0]['ticket_id']}: {rows[0]['title']}" if rows else "Unknown Ticket"
        elif entity_type == "dikw":
            result = supabase.table("dikw_items").select("level, content").eq("id", entity_id).execute()
            rows = result.data or []
            if rows:
                return f"[{rows[0]['level'].upper()}] {rows[0]['content'][:50]}..."
            return "Unknown DIKW Item"
        elif entity_type == "signal":
            result = supabase.table("signal_status").select("signal_type, signal_text").eq("id", entity_id).execute()
            rows = result.data or []
            if rows:
                return f"[{rows[0]['signal_type']}] {rows[0]['signal_text'][:50]}..."
            return "Unknown Signal"
        return "Unknown"
    except Exception as e:
        logger.warning(f"Failed to get entity title: {e}")
        return "Unknown"


def get_entity_snippet(entity_type: str, entity_id: int, supabase) -> str:
    """Get a snippet of the entity content."""
    try:
        content = ""
        if entity_type == "meeting":
            result = supabase.table("meetings").select("synthesized_notes").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["synthesized_notes"] if rows else ""
        elif entity_type == "document":
            result = supabase.table("documents").select("content").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["content"] if rows else ""
        elif entity_type == "ticket":
            result = supabase.table("tickets").select("description").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["description"] if rows else ""
        elif entity_type == "dikw":
            result = supabase.table("dikw_items").select("content").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["content"] if rows else ""
        elif entity_type == "signal":
            result = supabase.table("signal_status").select("signal_text").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["signal_text"] if rows else ""
        
        return (content or "")[:200]
    except Exception:
        return ""


def get_embedding(text: str):
    """Generate embedding for search query using OpenAI."""
    try:
        import openai
        client = openai.OpenAI()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"Failed to generate embedding: {e}")
        return None
