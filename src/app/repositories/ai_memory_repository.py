# src/app/repositories/ai_memory_repository.py
"""
AI Memory Repository - Data Access for AI Memory Storage

Handles all AI memory-related persistence:
- Memory creation and retrieval
- Memory status management (approved/rejected)
- Importance-based filtering
- Memory search and context retrieval
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AIMemory:
    """AI Memory entity."""
    id: Optional[str] = None
    source_query: str = ""
    content: str = ""
    source_type: str = "manual"  # manual, signal_learning, agent, etc.
    importance: float = 0.5
    status: str = "pending"  # pending, approved, rejected
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AIMemoryRepository(ABC):
    """
    Abstract interface (Port) for AI memory data access.
    """
    
    @abstractmethod
    def create(
        self,
        source_query: str,
        content: str,
        source_type: str = "manual",
        importance: float = 0.5,
        status: str = "pending",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a new memory. Returns memory ID."""
        pass
    
    @abstractmethod
    def get_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a memory by ID."""
        pass
    
    @abstractmethod
    def get_by_source_type(
        self, source_type: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get memories by source type."""
        pass
    
    @abstractmethod
    def get_approved(
        self, min_importance: float = 0.0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get approved memories with minimum importance."""
        pass
    
    @abstractmethod
    def update(self, memory_id: str, data: Dict[str, Any]) -> bool:
        """Update a memory."""
        pass
    
    @abstractmethod
    def update_status(self, memory_id: str, status: str) -> bool:
        """Update memory status (approved/rejected)."""
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        pass
    
    @abstractmethod
    def upsert_by_source(
        self,
        source_type: str,
        source_query: str,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create or update a memory by source type and query."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics by status and source type."""
        pass


class SupabaseAIMemoryRepository(AIMemoryRepository):
    """
    Supabase implementation (Adapter) for AI memory data access.
    """
    
    def __init__(self):
        from ..infrastructure.supabase_client import get_supabase_client
        self._supabase = get_supabase_client()
    
    def create(
        self,
        source_query: str,
        content: str,
        source_type: str = "manual",
        importance: float = 0.5,
        status: str = "pending",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a new memory. Returns memory ID."""
        try:
            data = {
                "source_query": source_query,
                "content": content,
                "source_type": source_type,
                "importance": importance,
                "status": status,
            }
            if metadata:
                data["metadata"] = metadata
            
            result = self._supabase.table("ai_memory").insert(data).execute()
            return result.data[0]["id"] if result.data else None
        except Exception:
            return None
    
    def get_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a memory by ID."""
        try:
            result = self._supabase.table("ai_memory").select("*").eq(
                "id", memory_id
            ).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None
    
    def get_by_source_type(
        self, source_type: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get memories by source type."""
        try:
            result = self._supabase.table("ai_memory").select("*").eq(
                "source_type", source_type
            ).limit(limit).execute()
            return result.data or []
        except Exception:
            return []
    
    def get_approved(
        self, min_importance: float = 0.0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get approved memories with minimum importance."""
        try:
            result = self._supabase.table("ai_memory").select("*").eq(
                "status", "approved"
            ).gte("importance", min_importance).limit(limit).execute()
            return result.data or []
        except Exception:
            return []
    
    def update(self, memory_id: str, data: Dict[str, Any]) -> bool:
        """Update a memory."""
        try:
            self._supabase.table("ai_memory").update(data).eq(
                "id", memory_id
            ).execute()
            return True
        except Exception:
            return False
    
    def update_status(self, memory_id: str, status: str) -> bool:
        """Update memory status (approved/rejected)."""
        return self.update(memory_id, {"status": status})
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        try:
            self._supabase.table("ai_memory").delete().eq(
                "id", memory_id
            ).execute()
            return True
        except Exception:
            return False
    
    def upsert_by_source(
        self,
        source_type: str,
        source_query: str,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create or update a memory by source type and query."""
        try:
            # Check for existing memory
            result = self._supabase.table("ai_memory").select("id").eq(
                "source_type", source_type
            ).eq("source_query", source_query).execute()
            
            if result.data:
                # Update existing
                memory_id = result.data[0]["id"]
                update_data = {
                    "content": content,
                    "importance": importance,
                    "updated_at": datetime.now().isoformat(),
                }
                if metadata:
                    update_data["metadata"] = metadata
                self._supabase.table("ai_memory").update(update_data).eq(
                    "id", memory_id
                ).execute()
                return memory_id
            else:
                # Create new
                return self.create(
                    source_query=source_query,
                    content=content,
                    source_type=source_type,
                    importance=importance,
                    metadata=metadata,
                )
        except Exception:
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics by status and source type."""
        try:
            result = self._supabase.table("ai_memory").select(
                "status, source_type, importance"
            ).execute()
            
            stats = {
                "total": 0,
                "by_status": {"pending": 0, "approved": 0, "rejected": 0},
                "by_source_type": {},
                "avg_importance": 0.0,
            }
            
            if result.data:
                stats["total"] = len(result.data)
                total_importance = 0.0
                
                for row in result.data:
                    status = row.get("status", "pending")
                    source_type = row.get("source_type", "unknown")
                    importance = row.get("importance", 0.5)
                    
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                    stats["by_source_type"][source_type] = stats["by_source_type"].get(
                        source_type, 0
                    ) + 1
                    total_importance += importance
                
                if stats["total"] > 0:
                    stats["avg_importance"] = total_importance / stats["total"]
            
            return stats
        except Exception:
            return {"total": 0, "by_status": {}, "by_source_type": {}, "avg_importance": 0.0}


# Factory function
_ai_memory_repository: Optional[AIMemoryRepository] = None


def get_ai_memory_repository() -> AIMemoryRepository:
    """Get or create the AI memory repository singleton."""
    global _ai_memory_repository
    if _ai_memory_repository is None:
        _ai_memory_repository = SupabaseAIMemoryRepository()
    return _ai_memory_repository
