# src/app/sdk/explorers.py
"""
Data Explorers for SignalFlow SDK

Provides specialized explorers for different data domains:
- MeetingsExplorer: Meeting data analysis
- SignalsExplorer: Signal search and categorization
- CareerExplorer: Career development insights
- DIKWExplorer: Knowledge hierarchy exploration
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Meeting:
    """Meeting data object."""
    id: str
    meeting_name: str
    meeting_date: Optional[str]
    created_at: str
    signals_count: int = 0
    has_transcript: bool = False
    has_mind_map: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Meeting":
        return cls(
            id=data.get("id", ""),
            meeting_name=data.get("meeting_name", "Untitled"),
            meeting_date=data.get("meeting_date"),
            created_at=data.get("created_at", ""),
            signals_count=data.get("signals_count", 0),
            has_transcript=bool(data.get("raw_text")),
            has_mind_map=bool(data.get("pocket_mind_map")),
        )


@dataclass
class Signal:
    """Signal data object."""
    id: str
    signal_type: str
    content: str
    confidence: float
    meeting_id: Optional[str]
    meeting_name: Optional[str]
    status: str
    created_at: str
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Signal":
        return cls(
            id=data.get("id", ""),
            signal_type=data.get("signal_type", "unknown"),
            content=data.get("content", ""),
            confidence=data.get("confidence", 0.0),
            meeting_id=data.get("meeting_id"),
            meeting_name=data.get("meeting_name"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
        )


class MeetingsExplorer:
    """
    Explorer for meeting data.
    
    Provides methods to list, search, and analyze meetings.
    
    Example:
        ```python
        explorer = client.meetings
        
        # List recent meetings
        meetings = explorer.list(limit=20)
        
        # Get meeting details
        meeting = explorer.get("meeting-uuid")
        
        # Analyze meeting patterns
        stats = explorer.get_statistics()
        ```
    """
    
    def __init__(self, client):
        self._client = client
    
    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Meeting]:
        """
        List meetings with optional filtering.
        
        Args:
            limit: Max meetings to return
            offset: Pagination offset
            date_from: Filter by start date (ISO format)
            date_to: Filter by end date (ISO format)
        
        Returns:
            List of Meeting objects
        """
        # Try Supabase direct if available
        if self._client.supabase:
            query = self._client.supabase.table("meetings").select("*")
            if date_from:
                query = query.gte("meeting_date", date_from)
            if date_to:
                query = query.lte("meeting_date", date_to)
            result = query.order("created_at", desc=True).limit(limit).execute()
            return [Meeting.from_dict(m) for m in result.data]
        
        # Fall back to API
        params = {"limit": limit, "offset": offset}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        
        try:
            data = self._client.api_get("/api/meetings", params)
            meetings = data.get("meetings", data) if isinstance(data, dict) else data
            return [Meeting.from_dict(m) for m in meetings]
        except Exception as e:
            logger.error(f"Failed to list meetings: {e}")
            return []
    
    def get(self, meeting_id: str) -> Optional[Meeting]:
        """Get a specific meeting by ID."""
        if self._client.supabase:
            result = self._client.supabase.table("meetings").select("*").eq("id", meeting_id).single().execute()
            if result.data:
                return Meeting.from_dict(result.data)
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get meeting statistics.
        
        Returns:
            Dict with counts, averages, and trends
        """
        meetings = self.list(limit=1000)
        
        if not meetings:
            return {"count": 0}
        
        # Basic stats
        total = len(meetings)
        with_transcripts = sum(1 for m in meetings if m.has_transcript)
        with_mind_maps = sum(1 for m in meetings if m.has_mind_map)
        
        # Time distribution
        now = datetime.now()
        last_week = sum(1 for m in meetings if m.created_at and 
                       datetime.fromisoformat(m.created_at.replace("Z", "+00:00")) > now - timedelta(days=7))
        last_month = sum(1 for m in meetings if m.created_at and
                        datetime.fromisoformat(m.created_at.replace("Z", "+00:00")) > now - timedelta(days=30))
        
        return {
            "total_meetings": total,
            "with_transcripts": with_transcripts,
            "with_mind_maps": with_mind_maps,
            "transcript_coverage": with_transcripts / total if total else 0,
            "meetings_last_7_days": last_week,
            "meetings_last_30_days": last_month,
        }
    
    def to_dataframe(self, meetings: Optional[List[Meeting]] = None):
        """
        Convert meetings to pandas DataFrame.
        
        Args:
            meetings: List of meetings (fetches if not provided)
        
        Returns:
            pandas DataFrame
        """
        import pandas as pd
        
        if meetings is None:
            meetings = self.list(limit=1000)
        
        data = [
            {
                "id": m.id,
                "name": m.meeting_name,
                "date": m.meeting_date,
                "created_at": m.created_at,
                "signals_count": m.signals_count,
                "has_transcript": m.has_transcript,
                "has_mind_map": m.has_mind_map,
            }
            for m in meetings
        ]
        
        df = pd.DataFrame(data)
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"])
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        
        return df


class SignalsExplorer:
    """
    Explorer for meeting signals.
    
    Provides methods to search, categorize, and analyze signals
    extracted from meetings (decisions, actions, blockers, risks, ideas).
    """
    
    def __init__(self, client):
        self._client = client
    
    def list(
        self,
        limit: int = 100,
        signal_type: Optional[str] = None,
        status: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> List[Signal]:
        """
        List signals with optional filtering.
        
        Args:
            limit: Max signals to return
            signal_type: Filter by type (decision, action, blocker, risk, idea)
            status: Filter by status (pending, approved, rejected)
            meeting_id: Filter by meeting
        """
        if self._client.supabase:
            query = self._client.supabase.table("signals").select("*")
            if signal_type:
                query = query.eq("signal_type", signal_type)
            if status:
                query = query.eq("status", status)
            if meeting_id:
                query = query.eq("meeting_id", meeting_id)
            result = query.order("created_at", desc=True).limit(limit).execute()
            return [Signal.from_dict(s) for s in result.data]
        
        return []
    
    def search(self, query: str, limit: int = 20) -> List[Signal]:
        """
        Search signals by content.
        
        Uses semantic search if embeddings available, falls back to keyword.
        """
        try:
            data = self._client.api_get("/api/signals/search", {"q": query, "limit": limit})
            signals = data.get("signals", [])
            return [Signal.from_dict(s) for s in signals]
        except Exception as e:
            logger.error(f"Signal search failed: {e}")
            return []
    
    def get_by_type(self) -> Dict[str, int]:
        """Get signal counts grouped by type."""
        signals = self.list(limit=10000)
        counts = {}
        for s in signals:
            counts[s.signal_type] = counts.get(s.signal_type, 0) + 1
        return counts
    
    def to_dataframe(self, signals: Optional[List[Signal]] = None):
        """Convert signals to pandas DataFrame."""
        import pandas as pd
        
        if signals is None:
            signals = self.list(limit=10000)
        
        data = [
            {
                "id": s.id,
                "type": s.signal_type,
                "content": s.content,
                "confidence": s.confidence,
                "status": s.status,
                "meeting_id": s.meeting_id,
                "meeting_name": s.meeting_name,
                "created_at": s.created_at,
            }
            for s in signals
        ]
        
        df = pd.DataFrame(data)
        if "created_at" in df.columns and len(df) > 0:
            df["created_at"] = pd.to_datetime(df["created_at"])
        
        return df


class CareerExplorer:
    """
    Explorer for career development data.
    
    Provides access to standups, suggestions, skills, and career memories.
    """
    
    def __init__(self, client):
        self._client = client
    
    def get_standups(self, limit: int = 30) -> List[Dict]:
        """Get recent standup updates."""
        if self._client.supabase:
            result = self._client.supabase.table("standup_updates").select("*").order("created_at", desc=True).limit(limit).execute()
            return result.data
        return []
    
    def get_suggestions(self, limit: int = 20) -> List[Dict]:
        """Get career suggestions."""
        if self._client.supabase:
            result = self._client.supabase.table("career_suggestions").select("*").order("created_at", desc=True).limit(limit).execute()
            return result.data
        return []
    
    def get_skills(self) -> List[Dict]:
        """Get tracked skills."""
        if self._client.supabase:
            result = self._client.supabase.table("skill_tracker").select("*").execute()
            return result.data
        return []
    
    def get_memories(self, limit: int = 50) -> List[Dict]:
        """Get career memories (AI implementations, learnings)."""
        if self._client.supabase:
            result = self._client.supabase.table("career_memories").select("*").order("created_at", desc=True).limit(limit).execute()
            return result.data
        return []
    
    def to_dataframe(self, data_type: str = "standups"):
        """
        Convert career data to DataFrame.
        
        Args:
            data_type: One of 'standups', 'suggestions', 'skills', 'memories'
        """
        import pandas as pd
        
        if data_type == "standups":
            data = self.get_standups()
        elif data_type == "suggestions":
            data = self.get_suggestions()
        elif data_type == "skills":
            data = self.get_skills()
        elif data_type == "memories":
            data = self.get_memories()
        else:
            raise ValueError(f"Unknown data type: {data_type}")
        
        return pd.DataFrame(data)


class DIKWExplorer:
    """
    Explorer for DIKW knowledge hierarchy.
    
    Provides access to the Data-Information-Knowledge-Wisdom pyramid.
    """
    
    def __init__(self, client):
        self._client = client
    
    def list(
        self,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        List DIKW items.
        
        Args:
            level: Filter by level (data, information, knowledge, wisdom)
            limit: Max items to return
        """
        if self._client.supabase:
            query = self._client.supabase.table("dikw_items").select("*")
            if level:
                query = query.eq("level", level)
            result = query.order("created_at", desc=True).limit(limit).execute()
            return result.data
        return []
    
    def get_by_level(self) -> Dict[str, int]:
        """Get item counts by DIKW level."""
        items = self.list(limit=10000)
        counts = {"data": 0, "information": 0, "knowledge": 0, "wisdom": 0}
        for item in items:
            level = item.get("level", "data")
            counts[level] = counts.get(level, 0) + 1
        return counts
    
    def get_evolution(self, item_id: str) -> List[Dict]:
        """Get evolution history for a DIKW item."""
        if self._client.supabase:
            result = self._client.supabase.table("dikw_evolution").select("*").eq("item_id", item_id).order("created_at", desc=True).execute()
            return result.data
        return []
    
    def to_dataframe(self, items: Optional[List[Dict]] = None):
        """Convert DIKW items to DataFrame."""
        import pandas as pd
        
        if items is None:
            items = self.list(limit=10000)
        
        return pd.DataFrame(items)
