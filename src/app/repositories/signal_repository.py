# src/app/repositories/signal_repository.py
"""
Signal Repository - Data Access for Signal Feedback and Status

Handles all signal-related persistence:
- Signal feedback (thumbs up/down)
- Signal status (approved/rejected/archived/completed)
- Signal conversions to tickets/DIKW
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseRepository


@dataclass
class SignalFeedback:
    """Signal feedback entity."""
    meeting_id: str
    signal_type: str
    signal_text: str
    feedback: Optional[str]  # 'up', 'down', or None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class SignalStatus:
    """Signal status entity."""
    meeting_id: str
    signal_type: str
    signal_text: str
    status: str  # pending, approved, rejected, archived, completed
    notes: Optional[str] = None
    converted_to: Optional[str] = None  # 'ticket', 'dikw'
    converted_ref_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    id: Optional[int] = None


class SignalRepository(ABC):
    """
    Abstract interface (Port) for signal data access.
    
    Defines all signal-related operations without implementation details.
    """
    
    # --- Feedback Operations ---
    
    @abstractmethod
    def get_all_feedback(self) -> List[Dict[str, Any]]:
        """Get all signal feedback records."""
        pass
    
    @abstractmethod
    def get_feedback(
        self, meeting_id: str, signal_type: str, signal_text: str
    ) -> Optional[Dict[str, Any]]:
        """Get feedback for a specific signal."""
        pass
    
    @abstractmethod
    def upsert_feedback(
        self, meeting_id: str, signal_type: str, signal_text: str, feedback: str
    ) -> bool:
        """Create or update feedback for a signal."""
        pass
    
    @abstractmethod
    def delete_feedback(
        self, meeting_id: str, signal_type: str, signal_text: str
    ) -> bool:
        """Remove feedback for a signal."""
        pass
    
    @abstractmethod
    def get_feedback_by_date_range(
        self, 
        days: int = 90, 
        user_id: Optional[str] = None,
        fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get feedback records within a date range.
        
        Args:
            days: Number of days to look back
            user_id: Optional user ID to filter by
            fields: Optional list of fields to select (default: all)
            
        Returns:
            List of feedback records matching criteria
        """
        pass
    
    # --- Status Operations ---
    
    @abstractmethod
    def get_status_for_meetings(
        self, meeting_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get signal statuses for multiple meetings.
        
        Returns:
            Dict keyed by "meeting_id:signal_type:signal_text"
        """
        pass
    
    @abstractmethod
    def get_unreviewed_count(self) -> int:
        """Get count of signals with pending or null status."""
        pass
    
    @abstractmethod
    def upsert_status(
        self,
        meeting_id: str,
        signal_type: str,
        signal_text: str,
        status: str,
        notes: str = "",
        converted_to: Optional[str] = None,
        converted_ref_id: Optional[str] = None,
    ) -> bool:
        """Create or update status for a signal."""
        pass
    
    @abstractmethod
    def get_converted_signals(self, converted_to: str) -> List[Dict[str, Any]]:
        """Get all signals converted to a specific type (ticket, dikw)."""
        pass
    
    @abstractmethod
    def get_by_id(self, signal_id: int) -> Optional[SignalStatus]:
        """Get a signal status by ID."""
        pass


class SupabaseSignalRepository(SignalRepository):
    """
    Supabase implementation (Adapter) for signal data access.
    """
    
    def __init__(self):
        from ..infrastructure.supabase_client import get_supabase_client
        self._supabase = get_supabase_client()
    
    # --- Feedback Operations ---
    
    def get_all_feedback(self) -> List[Dict[str, Any]]:
        """Get all signal feedback records."""
        try:
            result = self._supabase.table("signal_feedback").select(
                "meeting_id, signal_type, signal_text, feedback"
            ).execute()
            return result.data or []
        except Exception:
            return []
    
    def get_feedback(
        self, meeting_id: str, signal_type: str, signal_text: str
    ) -> Optional[Dict[str, Any]]:
        """Get feedback for a specific signal."""
        try:
            result = self._supabase.table("signal_feedback").select("*").eq(
                "meeting_id", meeting_id
            ).eq("signal_type", signal_type).eq("signal_text", signal_text).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None
    
    def upsert_feedback(
        self, meeting_id: str, signal_type: str, signal_text: str, feedback: str
    ) -> bool:
        """Create or update feedback for a signal."""
        try:
            self._supabase.table("signal_feedback").upsert(
                {
                    "meeting_id": meeting_id,
                    "signal_type": signal_type,
                    "signal_text": signal_text,
                    "feedback": feedback,
                },
                on_conflict="meeting_id,signal_type,signal_text",
            ).execute()
            return True
        except Exception:
            return False
    
    def delete_feedback(
        self, meeting_id: str, signal_type: str, signal_text: str
    ) -> bool:
        """Remove feedback for a signal."""
        try:
            self._supabase.table("signal_feedback").delete().eq(
                "meeting_id", meeting_id
            ).eq("signal_type", signal_type).eq("signal_text", signal_text).execute()
            return True
        except Exception:
            return False
    
    def get_feedback_by_date_range(
        self, 
        days: int = 90, 
        user_id: Optional[str] = None,
        fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Get feedback records within a date range."""
        from datetime import timedelta
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            select_fields = ", ".join(fields) if fields else "*"
            
            query = self._supabase.table("signal_feedback").select(
                select_fields
            ).gte("created_at", cutoff_date)
            
            if user_id:
                query = query.eq("user_id", user_id)
            
            result = query.execute()
            return result.data or []
        except Exception:
            return []
    
    # --- Status Operations ---
    
    def get_status_for_meetings(
        self, meeting_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get signal statuses for multiple meetings."""
        if not meeting_ids:
            return {}
        try:
            result = self._supabase.table("signal_status").select(
                "meeting_id, signal_type, signal_text, status"
            ).in_("meeting_id", meeting_ids).execute()
            
            status_map = {}
            for s in result.data or []:
                key = f"{s['meeting_id']}:{s['signal_type']}:{s['signal_text']}"
                status_map[key] = s
            return status_map
        except Exception:
            return {}
    
    def get_unreviewed_count(self) -> int:
        """Get count of signals with pending or null status."""
        try:
            result = self._supabase.table("signal_status").select(
                "id", count="exact"
            ).or_("status.eq.pending,status.is.null").execute()
            return result.count or 0
        except Exception:
            return 0
    
    def upsert_status(
        self,
        meeting_id: str,
        signal_type: str,
        signal_text: str,
        status: str,
        notes: str = "",
        converted_to: Optional[str] = None,
        converted_ref_id: Optional[str] = None,
    ) -> bool:
        """Create or update status for a signal."""
        try:
            data = {
                "meeting_id": meeting_id,
                "signal_type": signal_type,
                "signal_text": signal_text,
                "status": status,
                "notes": notes,
            }
            if converted_to:
                data["converted_to"] = converted_to
            if converted_ref_id:
                data["converted_ref_id"] = converted_ref_id
            
            self._supabase.table("signal_status").upsert(
                data, on_conflict="meeting_id,signal_type,signal_text"
            ).execute()
            return True
        except Exception:
            return False
    
    def get_converted_signals(self, converted_to: str) -> List[Dict[str, Any]]:
        """Get all signals converted to a specific type."""
        try:
            result = self._supabase.table("signal_status").select(
                "meeting_id, signal_type, signal_text"
            ).eq("converted_to", converted_to).execute()
            return result.data or []
        except Exception:
            return []

    def get_by_id(self, signal_id: int) -> Optional[SignalStatus]:
        """Get a signal status by ID."""
        if not self._supabase:
            return None
        try:
            result = self._supabase.table("signal_status").select(
                "id, meeting_id, signal_type, signal_text, status, notes, converted_to, converted_ref_id, created_at, updated_at"
            ).eq("id", signal_id).execute()
            if result.data:
                row = result.data[0]
                return SignalStatus(
                    meeting_id=row.get("meeting_id"),
                    signal_type=row.get("signal_type"),
                    signal_text=row.get("signal_text"),
                    status=row.get("status", "pending"),
                    notes=row.get("notes"),
                    converted_to=row.get("converted_to"),
                    converted_ref_id=row.get("converted_ref_id"),
                    created_at=row.get("created_at"),
                    updated_at=row.get("updated_at"),
                )
            return None
        except Exception:
            return None


# Factory function
_signal_repository: Optional[SignalRepository] = None


def get_signal_repository() -> SignalRepository:
    """Get or create the signal repository singleton."""
    global _signal_repository
    if _signal_repository is None:
        _signal_repository = SupabaseSignalRepository()
    return _signal_repository
