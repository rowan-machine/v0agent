# src/app/repositories/documents.py
"""
Document Repository - Ports and Adapters

Port: DocumentRepository (abstract interface)
Adapters: SupabaseDocumentRepository
"""

import logging
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseRepository, QueryOptions

logger = logging.getLogger(__name__)


class DocumentRepository(BaseRepository[Dict[str, Any]]):
    """
    Document Repository Port - defines the interface for document data access.
    
    Extends BaseRepository with document-specific operations.
    """
    
    @abstractmethod
    def get_by_meeting_id(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get all documents associated with a meeting."""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search documents by text content."""
        pass


# =============================================================================
# SUPABASE ADAPTER
# =============================================================================

class SupabaseDocumentRepository(DocumentRepository):
    """
    Supabase adapter for document repository.
    """
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from ..infrastructure.supabase_client import get_supabase_client
            self._client = get_supabase_client()
        return self._client
    
    def _format_row(self, row: Dict) -> Dict[str, Any]:
        """Format Supabase row to standard document dict."""
        return {
            "id": row.get("id"),
            "source": row.get("source", "Untitled Document"),
            "content": row.get("content", ""),
            "document_date": row.get("document_date"),
            "meeting_id": row.get("meeting_id"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
    
    def get_all(self, options: Optional[QueryOptions] = None) -> List[Dict[str, Any]]:
        """Get all documents from Supabase."""
        if not self.client:
            logger.warning("Supabase not available")
            return []
        
        options = options or QueryOptions()
        # Documents use document_date, not meeting_date
        order_col = "document_date" if options.order_by == "meeting_date" else options.order_by
        
        try:
            query = self.client.table("documents").select("*")
            query = query.order(order_col, desc=options.order_desc)
            
            if options.offset:
                query = query.range(options.offset, options.offset + options.limit - 1)
            else:
                query = query.limit(options.limit)
            
            result = query.execute()
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            return []
    
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single document by ID."""
        if not self.client:
            return None
        
        try:
            result = self.client.table("documents").select("*").eq("id", entity_id).single().execute()
            return self._format_row(result.data) if result.data else None
        except Exception as e:
            logger.error(f"Failed to get document {entity_id}: {e}")
            return None
    
    def get_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get count of documents."""
        if not self.client:
            return 0
        
        try:
            result = self.client.table("documents").select("id", count="exact").execute()
            return result.count or 0
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0
    
    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new document."""
        if not self.client:
            return None
        
        try:
            result = self.client.table("documents").insert(data).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            return None
    
    def update(self, entity_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing document."""
        if not self.client:
            return None
        
        try:
            data["updated_at"] = datetime.utcnow().isoformat()
            result = self.client.table("documents").update(data).eq("id", entity_id).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to update document {entity_id}: {e}")
            return None
    
    def delete(self, entity_id: str) -> bool:
        """Delete a document."""
        if not self.client:
            return False
        
        try:
            self.client.table("documents").delete().eq("id", entity_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {entity_id}: {e}")
            return False
    
    def get_by_meeting_id(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get all documents associated with a meeting."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("documents").select("*").eq(
                "meeting_id", meeting_id
            ).order("created_at", desc=True).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get documents for meeting {meeting_id}: {e}")
            return []
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search documents by text content."""
        if not self.client:
            return []
        
        # Client-side filtering (could use full-text search later)
        all_docs = self.get_all(QueryOptions(limit=200))
        query_lower = query.lower()
        
        results = []
        for d in all_docs:
            content = (d.get("content") or "").lower()
            source = (d.get("source") or "").lower()
            
            if query_lower in content or query_lower in source:
                results.append(d)
                if len(results) >= limit:
                    break
        
        return results
