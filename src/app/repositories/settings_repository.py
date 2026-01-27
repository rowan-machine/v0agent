# src/app/repositories/settings_repository.py
"""
Settings Repository - Data Access for Application Settings

Handles persistence for:
- Sprint settings (goals, dates, etc.)
- Mode sessions (timer tracking)
- Mode statistics (analytics)
- User status (current activity)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SprintSettings:
    """Sprint settings entity."""
    id: int = 1
    sprint_number: Optional[int] = None
    sprint_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goals: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ModeSession:
    """Mode timer session entity."""
    id: Optional[str] = None
    mode: str = "implementation"
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    date: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ModeStatistic:
    """Mode analytics statistic entity."""
    mode: str
    stat_type: str  # 'daily', 'weekly'
    period: str  # date string
    total_seconds: int = 0
    session_count: int = 0
    avg_session_seconds: int = 0


@dataclass
class UserStatus:
    """User status entity."""
    id: Optional[str] = None
    status_text: str = ""
    interpreted_mode: Optional[str] = None
    interpreted_activity: Optional[str] = None
    interpreted_context: Optional[str] = None
    is_current: bool = False
    created_at: Optional[datetime] = None


class SettingsRepository(ABC):
    """
    Abstract interface (Port) for settings data access.
    """
    
    # --- Sprint Settings ---
    
    @abstractmethod
    def get_sprint_settings(self) -> Optional[Dict[str, Any]]:
        """Get current sprint settings."""
        pass
    
    @abstractmethod
    def update_sprint_settings(self, data: Dict[str, Any]) -> bool:
        """Update sprint settings."""
        pass
    
    # --- Mode Sessions ---
    
    @abstractmethod
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active (not ended) mode sessions."""
        pass
    
    @abstractmethod
    def get_sessions_for_date(
        self, mode: str, date: str
    ) -> List[Dict[str, Any]]:
        """Get sessions for a specific mode and date."""
        pass
    
    @abstractmethod
    def get_sessions_since_date(
        self, mode: str, start_date: str
    ) -> List[Dict[str, Any]]:
        """Get sessions for a mode since a start date."""
        pass
    
    @abstractmethod
    def start_session(
        self, mode: str, started_at: str, date: str, notes: str = ""
    ) -> Optional[str]:
        """Start a new mode session. Returns session ID."""
        pass
    
    @abstractmethod
    def end_session(
        self, session_id: str, ended_at: str, duration_seconds: int
    ) -> bool:
        """End an active session."""
        pass
    
    # --- Mode Statistics ---
    
    @abstractmethod
    def upsert_statistics(
        self,
        mode: str,
        stat_type: str,
        period: str,
        total_seconds: int,
        session_count: int,
        avg_session_seconds: int,
    ) -> bool:
        """Update or insert mode statistics."""
        pass
    
    # --- User Status ---
    
    @abstractmethod
    def get_current_user_status(self) -> Optional[Dict[str, Any]]:
        """Get the current user status."""
        pass
    
    @abstractmethod
    def set_user_status(
        self,
        status_text: str,
        interpreted_mode: str,
        interpreted_activity: str,
        interpreted_context: str,
    ) -> bool:
        """Set new user status and mark previous as not current."""
        pass

    # --- Key-Value Settings ---
    
    @abstractmethod
    def get_setting(self, key: str) -> Optional[str]:
        """
        Get a setting value by key from the settings table.
        
        Args:
            key: The setting key (e.g., 'workflow_mode', 'current_mode')
            
        Returns:
            The setting value or None if not found
        """
        pass

    @abstractmethod
    def set_setting(self, key: str, value: str) -> bool:
        """
        Set a setting value by key in the settings table.
        
        Args:
            key: The setting key
            value: The setting value
            
        Returns:
            True if successful
        """
        pass


class SupabaseSettingsRepository(SettingsRepository):
    """
    Supabase implementation (Adapter) for settings data access.
    """
    
    def __init__(self):
        from ..infrastructure.supabase_client import get_supabase_client
        self._supabase = get_supabase_client()
    
    # --- Sprint Settings ---
    
    def get_sprint_settings(self) -> Optional[Dict[str, Any]]:
        """Get current sprint settings."""
        try:
            result = self._supabase.table("sprint_settings").select(
                "*"
            ).eq("id", 1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None
    
    def update_sprint_settings(self, data: Dict[str, Any]) -> bool:
        """Update sprint settings."""
        try:
            self._supabase.table("sprint_settings").upsert(
                {"id": 1, **data}, on_conflict="id"
            ).execute()
            return True
        except Exception:
            return False
    
    # --- Mode Sessions ---
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active (not ended) mode sessions."""
        try:
            result = self._supabase.table("mode_sessions").select(
                "id, mode, started_at"
            ).is_("ended_at", "null").execute()
            return result.data or []
        except Exception:
            return []
    
    def get_sessions_for_date(
        self, mode: str, date: str
    ) -> List[Dict[str, Any]]:
        """Get sessions for a specific mode and date."""
        try:
            result = self._supabase.table("mode_sessions").select(
                "duration_seconds"
            ).eq("mode", mode).eq("date", date).not_.is_(
                "duration_seconds", "null"
            ).execute()
            return result.data or []
        except Exception:
            return []
    
    def get_sessions_since_date(
        self, mode: str, start_date: str
    ) -> List[Dict[str, Any]]:
        """Get sessions for a mode since a start date."""
        try:
            result = self._supabase.table("mode_sessions").select(
                "duration_seconds"
            ).eq("mode", mode).gte("date", start_date).not_.is_(
                "duration_seconds", "null"
            ).execute()
            return result.data or []
        except Exception:
            return []
    
    def start_session(
        self, mode: str, started_at: str, date: str, notes: str = ""
    ) -> Optional[str]:
        """Start a new mode session. Returns session ID."""
        try:
            result = self._supabase.table("mode_sessions").insert({
                "mode": mode,
                "started_at": started_at,
                "date": date,
                "notes": notes,
            }).execute()
            return result.data[0]["id"] if result.data else None
        except Exception:
            return None
    
    def end_session(
        self, session_id: str, ended_at: str, duration_seconds: int
    ) -> bool:
        """End an active session."""
        try:
            self._supabase.table("mode_sessions").update({
                "ended_at": ended_at,
                "duration_seconds": duration_seconds,
            }).eq("id", session_id).execute()
            return True
        except Exception:
            return False
    
    # --- Mode Statistics ---
    
    def upsert_statistics(
        self,
        mode: str,
        stat_type: str,
        period: str,
        total_seconds: int,
        session_count: int,
        avg_session_seconds: int,
    ) -> bool:
        """Update or insert mode statistics."""
        try:
            self._supabase.table("mode_statistics").upsert(
                {
                    "mode": mode,
                    "stat_type": stat_type,
                    "period": period,
                    "total_seconds": total_seconds,
                    "session_count": session_count,
                    "avg_session_seconds": avg_session_seconds,
                },
                on_conflict="mode,stat_type,period",
            ).execute()
            return True
        except Exception:
            return False
    
    # --- User Status ---
    
    def get_current_user_status(self) -> Optional[Dict[str, Any]]:
        """Get the current user status."""
        try:
            result = self._supabase.table("user_status").select(
                "*"
            ).eq("is_current", True).order(
                "created_at", desc=True
            ).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None
    
    def set_user_status(
        self,
        status_text: str,
        interpreted_mode: str,
        interpreted_activity: str,
        interpreted_context: str,
    ) -> bool:
        """Set new user status and mark previous as not current."""
        try:
            # Mark all previous statuses as not current
            self._supabase.table("user_status").update(
                {"is_current": False}
            ).eq("is_current", True).execute()
            
            # Insert new status
            self._supabase.table("user_status").insert({
                "status_text": status_text,
                "interpreted_mode": interpreted_mode,
                "interpreted_activity": interpreted_activity,
                "interpreted_context": interpreted_context,
                "is_current": True,
            }).execute()
            return True
        except Exception:
            return False

    # --- Key-Value Settings ---
    
    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value by key from the settings table."""
        try:
            result = self._supabase.table("settings").select(
                "value"
            ).eq("key", key).execute()
            if result.data:
                return result.data[0].get("value")
            return None
        except Exception:
            return None
    
    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value by key in the settings table."""
        try:
            self._supabase.table("settings").upsert(
                {"key": key, "value": value},
                on_conflict="key"
            ).execute()
            return True
        except Exception:
            return False


# Factory function
_settings_repository: Optional[SettingsRepository] = None


def get_settings_repository() -> SettingsRepository:
    """Get or create the settings repository singleton."""
    global _settings_repository
    if _settings_repository is None:
        _settings_repository = SupabaseSettingsRepository()
    return _settings_repository
