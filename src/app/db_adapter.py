"""
Database Adapter - DEPRECATED

⚠️ DEPRECATED: This module is deprecated and will be removed.

Use the repository pattern instead:
    from src.app.repositories import get_meeting_repository, get_ticket_repository
    
Or use Supabase directly:
    from src.app.infrastructure.supabase_client import get_supabase_client

This module is kept only for backward compatibility with existing code.
All new code should use the repository pattern or direct Supabase access.

Migration guide:
    OLD: db = DualWriteDB(); db.get_career_profile()
    NEW: supabase = get_supabase_client()
         result = supabase.table("career_profiles").select("*").limit(1).execute()
"""

import logging
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

_DEPRECATION_MSG = (
    "DualWriteDB is deprecated. Use get_supabase_client() or repositories instead. "
    "See src/app/db_adapter.py docstring for migration guide."
)


def _emit_deprecation():
    """Emit deprecation warning."""
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=3)


@dataclass
class SyncStatus:
    """Status of a sync operation (deprecated)."""
    success: bool
    sqlite_success: bool  # Always True (deprecated field)
    supabase_success: bool
    error: Optional[str] = None


class DualWriteDB:
    """
    DEPRECATED: Database adapter - now operates in Supabase-only mode.
    
    Use get_supabase_client() or repositories instead.
    """
    
    def __init__(self, user_id: str = None, sync_enabled: bool = True):
        """Initialize database adapter."""
        _emit_deprecation()
        self.user_id = user_id
        self.sync_enabled = True
        self._supabase = None
    
    @property
    def supabase(self):
        """Get Supabase client."""
        if self._supabase is None:
            self._supabase = get_supabase_client()
        return self._supabase
    
    @property
    def use_supabase_reads(self) -> bool:
        """Always returns True in Supabase-only mode."""
        return True
    
    def get_career_profile(self) -> Optional[Dict]:
        """Get career profile from Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return None
            result = supabase.table("career_profiles").select("*").limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to get career profile: {e}")
            return None
    
    async def update_career_profile(self, updates: Dict[str, Any]) -> SyncStatus:
        """Update career profile in Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error="Supabase not available")
            
            updates["updated_at"] = datetime.now().isoformat()
            supabase.table("career_profiles").update(updates).eq("id", 1).execute()
            return SyncStatus(success=True, sqlite_success=True, supabase_success=True)
        except Exception as e:
            logger.error(f"Failed to update career profile: {e}")
            return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error=str(e))
    
    def get_suggestions(self, status: str = None, limit: int = 20) -> List[Dict]:
        """Get career suggestions from Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return []
            
            query = supabase.table("career_suggestions").select("*")
            if status:
                query = query.eq("status", status)
            result = query.order("id", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get suggestions: {e}")
            return []
    
    async def save_suggestion(self, data: Dict[str, Any]) -> SyncStatus:
        """Save career suggestion to Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error="Supabase not available")
            
            data["created_at"] = datetime.now().isoformat()
            supabase.table("career_suggestions").insert(data).execute()
            return SyncStatus(success=True, sqlite_success=True, supabase_success=True)
        except Exception as e:
            logger.error(f"Failed to save suggestion: {e}")
            return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error=str(e))
    
    async def update_suggestion(self, suggestion_id: int, updates: Dict[str, Any]) -> SyncStatus:
        """Update career suggestion in Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error="Supabase not available")
            
            updates["updated_at"] = datetime.now().isoformat()
            supabase.table("career_suggestions").update(updates).eq("id", suggestion_id).execute()
            return SyncStatus(success=True, sqlite_success=True, supabase_success=True)
        except Exception as e:
            logger.error(f"Failed to update suggestion: {e}")
            return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error=str(e))
    
    def get_standups(self, limit: int = 10) -> List[Dict]:
        """Get standup updates from Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return []
            
            result = supabase.table("standup_updates").select("*").order("standup_date", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get standups: {e}")
            return []
    
    async def save_standup(self, data: Dict[str, Any]) -> SyncStatus:
        """Save standup update to Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error="Supabase not available")
            
            data["created_at"] = datetime.now().isoformat()
            supabase.table("standup_updates").insert(data).execute()
            return SyncStatus(success=True, sqlite_success=True, supabase_success=True)
        except Exception as e:
            logger.error(f"Failed to save standup: {e}")
            return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error=str(e))
    
    def get_memories(self, memory_type: str = None, limit: int = 20) -> List[Dict]:
        """Get career memories from Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return []
            
            query = supabase.table("career_memories").select("*")
            if memory_type:
                query = query.eq("memory_type", memory_type)
            result = query.order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []
    
    async def save_memory(self, data: Dict[str, Any]) -> SyncStatus:
        """Save career memory to Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error="Supabase not available")
            
            data["created_at"] = datetime.now().isoformat()
            supabase.table("career_memories").insert(data).execute()
            return SyncStatus(success=True, sqlite_success=True, supabase_success=True)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error=str(e))
    
    def get_skills(self, category: str = None) -> List[Dict]:
        """Get skills from Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return []
            
            query = supabase.table("skill_tracker").select("*")
            if category:
                query = query.eq("category", category)
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get skills: {e}")
            return []
    
    async def update_skill(self, skill_name: str, updates: Dict[str, Any]) -> SyncStatus:
        """Update skill in Supabase."""
        try:
            supabase = self.supabase
            if not supabase:
                return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error="Supabase not available")
            
            updates["updated_at"] = datetime.now().isoformat()
            supabase.table("skill_tracker").upsert({**updates, "skill_name": skill_name}).execute()
            return SyncStatus(success=True, sqlite_success=True, supabase_success=True)
        except Exception as e:
            logger.error(f"Failed to update skill: {e}")
            return SyncStatus(success=False, sqlite_success=True, supabase_success=False, error=str(e))


def get_dual_write_db(user_id: str = None) -> DualWriteDB:
    """Create a DualWriteDB instance. DEPRECATED: Use get_supabase_client() instead."""
    _emit_deprecation()
    return DualWriteDB(user_id=user_id)
