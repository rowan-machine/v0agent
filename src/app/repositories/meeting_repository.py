# src/app/repositories/meetings.py
"""
Meeting Repository - Ports and Adapters

Port: MeetingRepository (abstract interface)
Adapters: SupabaseMeetingRepository
"""

import json
import logging
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseRepository, QueryOptions

logger = logging.getLogger(__name__)


class MeetingRepository(BaseRepository[Dict[str, Any]]):
    """
    Meeting Repository Port - defines the interface for meeting data access.
    
    Extends BaseRepository with meeting-specific operations.
    """
    
    @abstractmethod
    def get_by_date_range(
        self, start_date: str, end_date: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meetings within a date range."""
        pass
    
    @abstractmethod
    def get_with_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get meetings that have extracted signals."""
        pass
    
    @abstractmethod
    def get_with_signals_by_days(
        self, days: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meetings with signals, optionally filtered by days back."""
        pass
    
    @abstractmethod
    def search(
        self, query: str, include_transcripts: bool = False, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search meetings by text content."""
        pass


# =============================================================================
# SUPABASE ADAPTER
# =============================================================================

class SupabaseMeetingRepository(MeetingRepository):
    """
    Supabase adapter for meeting repository.
    
    Reads and writes meeting data to/from Supabase cloud database.
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
        """Format Supabase row to standard meeting dict."""
        # Handle case where the entire meeting got JSON-encoded in meeting_name
        meeting_name = row.get("meeting_name", "Untitled Meeting")
        if isinstance(meeting_name, str) and meeting_name.startswith('{'):
            try:
                # Try to parse it as JSON
                parsed = json.loads(meeting_name)
                if isinstance(parsed, dict) and "meeting_name" in parsed:
                    # It's the full meeting object encoded - use the parsed version
                    logger.warning("Found full meeting object in meeting_name field - merging data")
                    row.update(parsed)
                    meeting_name = parsed.get("meeting_name", "Untitled Meeting")
            except json.JSONDecodeError:
                pass  # It's just a string that happens to start with {
        
        # Format meeting_date to just the date (no time)
        meeting_date = row.get("meeting_date", "")
        if meeting_date and "T" in str(meeting_date):
            meeting_date = str(meeting_date).split("T")[0]
        
        return {
            "id": row.get("id"),
            "meeting_name": str(meeting_name) if meeting_name else "Untitled Meeting",
            "meeting_date": meeting_date,
            "synthesized_notes": str(row.get("synthesized_notes", "")) if row.get("synthesized_notes") else "",
            "signals_json": json.dumps(row.get("signals", {})) if row.get("signals") else None,
            "signals": row.get("signals", {}),
            "raw_text": str(row.get("raw_text", "")) if row.get("raw_text") else "",
            "pocket_ai_summary": str(row.get("pocket_ai_summary", "")) if row.get("pocket_ai_summary") else "",
            "pocket_mind_map": str(row.get("pocket_mind_map", "")) if row.get("pocket_mind_map") else "",
            "pocket_recording_id": row.get("pocket_recording_id"),  # Unique ID for idempotency
            "import_source": row.get("import_source"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
    
    def get_all(self, options: Optional[QueryOptions] = None) -> List[Dict[str, Any]]:
        """Get all meetings from Supabase."""
        if not self.client:
            logger.warning("Supabase not available")
            return []
        
        options = options or QueryOptions()
        
        try:
            query = self.client.table("meetings").select("*")
            
            # Apply ordering
            query = query.order(options.order_by, desc=options.order_desc)
            
            # Apply pagination
            if options.offset:
                query = query.range(options.offset, options.offset + options.limit - 1)
            else:
                query = query.limit(options.limit)
            
            result = query.execute()
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get meetings: {e}")
            return []
    
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single meeting by ID."""
        if not self.client:
            return None
        
        try:
            result = self.client.table("meetings").select("*").eq("id", entity_id).single().execute()
            return self._format_row(result.data) if result.data else None
        except Exception as e:
            logger.error(f"Failed to get meeting {entity_id}: {e}")
            return None
    
    def get_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get count of meetings."""
        if not self.client:
            return 0
        
        try:
            result = self.client.table("meetings").select("id", count="exact").execute()
            return result.count or 0
        except Exception as e:
            logger.error(f"Failed to get meeting count: {e}")
            return 0
    
    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new meeting."""
        if not self.client:
            return None
        
        try:
            # Convert signals_json to signals object if present
            if "signals_json" in data and data["signals_json"]:
                signals_value = data["signals_json"]
                # Handle both string and dict formats
                if isinstance(signals_value, str):
                    data["signals"] = json.loads(signals_value)
                else:
                    data["signals"] = signals_value
                del data["signals_json"]
            
            result = self.client.table("meetings").insert(data).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to create meeting: {e}")
            return None
    
    def update(self, entity_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing meeting."""
        if not self.client:
            return None
        
        try:
            # Convert signals_json to signals object if present
            if "signals_json" in data and data["signals_json"]:
                signals_value = data["signals_json"]
                # Handle both string and dict formats
                if isinstance(signals_value, str):
                    data["signals"] = json.loads(signals_value)
                else:
                    data["signals"] = signals_value
                del data["signals_json"]
            
            data["updated_at"] = datetime.utcnow().isoformat()
            result = self.client.table("meetings").update(data).eq("id", entity_id).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to update meeting {entity_id}: {e}")
            return None
    
    def delete(self, entity_id: str) -> bool:
        """Delete a meeting."""
        if not self.client:
            return False
        
        try:
            self.client.table("meetings").delete().eq("id", entity_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete meeting {entity_id}: {e}")
            return False
    
    def get_by_date_range(
        self, start_date: str, end_date: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meetings within a date range."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("meetings").select("*").gte(
                "meeting_date", start_date
            ).lte(
                "meeting_date", end_date
            ).order("meeting_date", desc=True).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get meetings by date range: {e}")
            return []
    
    def get_with_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get meetings that have signals extracted."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("meetings").select("*").not_.is_(
                "signals", "null"
            ).order("meeting_date", desc=True).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get meetings with signals: {e}")
            return []
    
    def get_with_signals_by_days(
        self, days: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meetings with signals, optionally filtered by days back."""
        if not self.client:
            return []
        
        try:
            from datetime import timedelta
            
            query = self.client.table("meetings").select(
                "id, meeting_name, meeting_date, signals"
            ).not_.is_("signals", "null").neq("signals", "{}")
            
            if days:
                cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                query = query.gte("meeting_date", cutoff_date)
            
            result = query.order("meeting_date", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get meetings with signals by days: {e}")
            return []
    
    def search(
        self, query: str, include_transcripts: bool = False, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search meetings by text content."""
        if not self.client:
            return []
        
        # For Supabase, we do client-side filtering (could use full-text search in future)
        all_meetings = self.get_all(QueryOptions(limit=200))
        query_lower = query.lower()
        
        results = []
        for m in all_meetings:
            match = False
            notes = (m.get("synthesized_notes") or "").lower()
            name = (m.get("meeting_name") or "").lower()
            raw = (m.get("raw_text") or "").lower() if include_transcripts else ""
            
            if query_lower in notes or query_lower in name or query_lower in raw:
                match = True
            
            if match:
                results.append(m)
                if len(results) >= limit:
                    break
        
        return results
