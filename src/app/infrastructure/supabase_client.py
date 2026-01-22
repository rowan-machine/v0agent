# src/app/infrastructure/supabase_client.py
"""
Supabase Client - Phase 5.1

Provides Supabase client for cloud database operations including:
- Data sync between SQLite and Supabase
- Embedding storage with pgvector
- Real-time subscriptions

Usage:
    from .supabase_client import get_supabase_client
    
    # Get client
    client = get_supabase_client()
    
    # Query data
    result = client.table("meetings").select("*").execute()
    
    # Insert with embedding
    client.table("embeddings").insert({
        "ref_type": "meeting",
        "ref_id": "uuid-here",
        "embedding": [0.1, 0.2, ...],
    }).execute()
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Singleton client
_supabase_client = None


def get_supabase_client():
    """
    Get the Supabase client singleton.
    
    Returns:
        Supabase client or None if not configured
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    # Get credentials from environment
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        logger.warning("⚠️ Supabase not configured (missing SUPABASE_URL or SUPABASE_KEY)")
        return None
    
    try:
        from supabase import create_client, Client
        
        _supabase_client = create_client(supabase_url, supabase_key)
        logger.info(f"✅ Connected to Supabase: {supabase_url}")
        return _supabase_client
    except ImportError:
        logger.warning("⚠️ supabase package not installed")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to connect to Supabase: {e}")
        return None


class SupabaseSync:
    """
    Utilities for syncing data between SQLite and Supabase.
    """
    
    def __init__(self, client=None):
        """
        Initialize sync utilities.
        
        Args:
            client: Supabase client (or None to auto-create)
        """
        self._client = client or get_supabase_client()
    
    @property
    def is_available(self) -> bool:
        """Check if Supabase is available."""
        return self._client is not None
    
    async def sync_meeting(self, meeting: Dict[str, Any]) -> Optional[str]:
        """
        Sync a meeting to Supabase.
        
        Args:
            meeting: Meeting dict from SQLite
            
        Returns:
            Supabase UUID or None on failure
        """
        if not self._client:
            return None
        
        try:
            # Map SQLite fields to Supabase schema
            data = {
                "meeting_name": meeting.get("meeting_name") or meeting.get("name"),
                "synthesized_notes": meeting.get("synthesized_notes") or meeting.get("notes", ""),
                "meeting_date": meeting.get("meeting_date") or meeting.get("date"),
                "raw_text": meeting.get("raw_text"),
                "signals": meeting.get("signals", {}),
            }
            
            result = self._client.table("meetings").insert(data).execute()
            
            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Failed to sync meeting: {e}")
            return None
    
    async def sync_document(self, doc: Dict[str, Any], meeting_uuid: Optional[str] = None) -> Optional[str]:
        """
        Sync a document to Supabase.
        
        Args:
            doc: Document dict from SQLite
            meeting_uuid: Optional Supabase meeting UUID to link
            
        Returns:
            Supabase UUID or None on failure
        """
        if not self._client:
            return None
        
        try:
            data = {
                "source": doc.get("source") or doc.get("filename", "unknown"),
                "content": doc.get("content") or doc.get("text", ""),
                "document_date": doc.get("document_date") or doc.get("date"),
            }
            
            if meeting_uuid:
                data["meeting_id"] = meeting_uuid
            
            result = self._client.table("documents").insert(data).execute()
            
            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Failed to sync document: {e}")
            return None
    
    async def sync_ticket(self, ticket: Dict[str, Any]) -> Optional[str]:
        """
        Sync a ticket to Supabase.
        
        Args:
            ticket: Ticket dict from SQLite
            
        Returns:
            Supabase UUID or None on failure
        """
        if not self._client:
            return None
        
        try:
            data = {
                "ticket_id": ticket.get("ticket_id"),
                "title": ticket.get("title", ""),
                "description": ticket.get("description"),
                "status": ticket.get("status", "backlog"),
                "priority": ticket.get("priority"),
                "sprint_points": ticket.get("sprint_points", 0),
                "in_sprint": ticket.get("in_sprint", True),
                "ai_summary": ticket.get("ai_summary"),
                "implementation_plan": ticket.get("implementation_plan"),
                "task_decomposition": ticket.get("task_decomposition"),
                "tags": ticket.get("tags", []),
            }
            
            result = self._client.table("tickets").insert(data).execute()
            
            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Failed to sync ticket: {e}")
            return None
    
    async def sync_dikw_item(self, item: Dict[str, Any], meeting_uuid: Optional[str] = None) -> Optional[str]:
        """
        Sync a DIKW item to Supabase.
        
        Args:
            item: DIKW item dict from SQLite
            meeting_uuid: Optional Supabase meeting UUID to link
            
        Returns:
            Supabase UUID or None on failure
        """
        if not self._client:
            return None
        
        try:
            data = {
                "level": item.get("level", "data"),
                "content": item.get("content", ""),
                "summary": item.get("summary"),
                "source_type": item.get("source_type"),
                "original_signal_type": item.get("original_signal_type"),
                "tags": item.get("tags", []),
                "confidence": item.get("confidence", 0.5),
                "validation_count": item.get("validation_count", 0),
                "status": item.get("status", "active"),
            }
            
            if meeting_uuid:
                data["meeting_id"] = meeting_uuid
            
            result = self._client.table("dikw_items").insert(data).execute()
            
            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Failed to sync DIKW item: {e}")
            return None
    
    async def sync_embedding(
        self,
        ref_type: str,
        ref_uuid: str,
        embedding: List[float],
        model: str = "text-embedding-3-small",
        content_hash: Optional[str] = None,
    ) -> Optional[str]:
        """
        Sync an embedding to Supabase pgvector.
        
        Args:
            ref_type: Type of referenced item (meeting, document, dikw_item)
            ref_uuid: UUID of the referenced item
            embedding: Vector embedding (1536 dimensions for OpenAI)
            model: Embedding model name
            content_hash: Hash of content for cache invalidation
            
        Returns:
            Supabase UUID or None on failure
        """
        if not self._client:
            return None
        
        try:
            data = {
                "ref_type": ref_type,
                "ref_id": ref_uuid,
                "embedding": embedding,
                "model": model,
                "content_hash": content_hash,
            }
            
            result = self._client.table("embeddings").insert(data).execute()
            
            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Failed to sync embedding: {e}")
            return None
    
    async def semantic_search(
        self,
        query_embedding: List[float],
        ref_type: Optional[str] = None,
        match_count: int = 10,
        match_threshold: float = 0.78,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using pgvector.
        
        Args:
            query_embedding: Query vector embedding
            ref_type: Optional filter by reference type
            match_count: Maximum results to return
            match_threshold: Minimum similarity threshold
            
        Returns:
            List of matching items with similarity scores
        """
        if not self._client:
            return []
        
        try:
            # Call the match_embeddings RPC function
            result = self._client.rpc(
                "match_embeddings",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": match_threshold,
                    "match_count": match_count,
                }
            ).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []


def get_supabase_sync() -> SupabaseSync:
    """Get the Supabase sync utilities."""
    return SupabaseSync()
