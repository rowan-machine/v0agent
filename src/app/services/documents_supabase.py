"""
Documents Service - Supabase Direct Reads

This module provides document operations that read directly from Supabase,
eliminating the need for SQLite sync and enabling real-time data access.

NOTE: This module is now a thin wrapper around the repository layer.
For new code, prefer importing from src.app.repositories directly.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..repositories import get_document_repository
from ..repositories.base import QueryOptions

logger = logging.getLogger(__name__)

# Get repository singleton (default Supabase backend)
_repo = None

def _get_repo():
    """Get or create the repository singleton."""
    global _repo
    if _repo is None:
        _repo = get_document_repository("supabase")
    return _repo


def get_supabase_client():
    """Get Supabase client from infrastructure - DEPRECATED, use repository."""
    from ..infrastructure.supabase_client import get_supabase_client as _get_client
    return _get_client()


def get_all_documents(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all documents from Supabase.
    
    Returns:
        List of document dictionaries
    """
    return _get_repo().get_all(QueryOptions(limit=limit))


def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single document by ID from Supabase.
    """
    return _get_repo().get_by_id(doc_id)


def get_documents_count() -> int:
    """
    Get total count of documents in Supabase.
    """
    return _get_repo().get_count()


def get_recent_documents(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent documents.
    """
    return _get_repo().get_recent(limit)


def create_document(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new document in Supabase."""
    return _get_repo().create(data)


def update_document(doc_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an existing document in Supabase."""
    return _get_repo().update(doc_id, data)


def delete_document(doc_id: str) -> bool:
    """Delete a document from Supabase."""
    return _get_repo().delete(doc_id)


def search_documents(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search documents by text content."""
    return _get_repo().search(query, limit)

    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("documents").select(
            "id, source, document_date, created_at"
        ).order("document_date", desc=True, nullsfirst=False).limit(limit).execute()
        
        return [
            {
                "id": row.get("id"),
                "source": row.get("source", "Untitled Document"),
                "document_date": row.get("document_date"),
            }
            for row in result.data
        ]
    except Exception as e:
        logger.error(f"Failed to get recent documents: {e}")
        return []


def create_document(
    source: str,
    content: str,
    document_date: Optional[str] = None,
    meeting_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a new document in Supabase.
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        data = {
            "source": source,
            "content": content,
            "document_date": document_date or datetime.now().isoformat(),
            "meeting_id": meeting_id,
        }
        
        result = client.table("documents").insert(data).execute()
        
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to create document: {e}")
        return None


def update_document(doc_id: str, updates: Dict[str, Any]) -> bool:
    """
    Update a document in Supabase.
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("documents").update(updates).eq("id", doc_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update document {doc_id}: {e}")
        return False


def delete_document(doc_id: str) -> bool:
    """
    Delete a document from Supabase.
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("documents").delete().eq("id", doc_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        return False
