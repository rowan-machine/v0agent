"""
Meetings Service - Supabase Direct Reads

This module provides meeting operations that read directly from Supabase,
eliminating the need for SQLite sync and enabling real-time data access.

NOTE: This module is now a thin wrapper around the repository layer.
For new code, prefer importing from src.app.repositories directly.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..repositories import get_meeting_repository
from ..repositories.base import QueryOptions

logger = logging.getLogger(__name__)

# Get repository singleton (default Supabase backend)
_repo = None

def _get_repo():
    """Get or create the repository singleton."""
    global _repo
    if _repo is None:
        _repo = get_meeting_repository()
    return _repo


def get_supabase_client():
    """Get Supabase client from infrastructure - DEPRECATED, use repository."""
    from ..infrastructure.supabase_client import get_supabase_client as _get_client
    return _get_client()


def get_all_meetings(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all meetings from Supabase.
    
    Returns:
        List of meeting dictionaries with id, meeting_name, meeting_date, signals, etc.
    """
    return _get_repo().get_all(QueryOptions(limit=limit))


def get_meeting_by_id(meeting_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single meeting by ID from Supabase.
    
    Args:
        meeting_id: UUID of the meeting
        
    Returns:
        Meeting dictionary or None if not found
    """
    return _get_repo().get_by_id(meeting_id)


def get_meeting_by_pocket_recording_id(pocket_recording_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a meeting by its Pocket recording ID.
    
    Args:
        pocket_recording_id: The unique Pocket recording UUID
        
    Returns:
        Meeting dictionary or None if not found
    """
    client = get_supabase_client()
    if not client or not pocket_recording_id:
        return None
    
    try:
        result = client.table("meetings").select("*").eq(
            "pocket_recording_id", pocket_recording_id
        ).limit(1).execute()
        
        if result.data:
            return _get_repo()._format_row(result.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to get meeting by pocket_recording_id: {e}")
        return None


def get_meetings_count() -> int:
    """
    Get total count of meetings in Supabase.
    
    Returns:
        Number of meetings
    """
    return _get_repo().get_count()


def get_recent_meetings(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent meetings.
    
    Returns:
        List of recent meetings with id, meeting_name, meeting_date
    """
    return _get_repo().get_recent(limit)


def get_meetings_with_signals(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all meetings that have signals data.
    
    Returns:
        List of meetings with id, meeting_name, signals
    """
    return _get_repo().get_with_signals(limit)


def get_meeting_signals(meeting_id: str) -> Optional[Dict[str, Any]]:
    """
    Get signals for a specific meeting.
    
    Args:
        meeting_id: UUID of the meeting
        
    Returns:
        Signals dictionary or None
    """
    meeting = _get_repo().get_by_id(meeting_id)
    if meeting:
        return meeting.get("signals")
    return None


def get_meetings_with_signals_in_range(days: int = 30) -> List[Dict[str, Any]]:
    """
    Get meetings with signals from the last N days.
    
    Args:
        days: Number of days to look back
        
    Returns:
        List of meetings with signals
    """
    from datetime import timedelta
    cutoff_start = (datetime.now() - timedelta(days=days)).isoformat()[:10]
    cutoff_end = datetime.now().isoformat()[:10]
    
    meetings = _get_repo().get_by_date_range(cutoff_start, cutoff_end, limit=200)
    # Filter to only those with signals
    return [m for m in meetings if m.get("signals")]


# =============================================================================
# LEGACY FUNCTIONS - Keep for backward compatibility, delegate to repository
# =============================================================================

def create_meeting(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new meeting in Supabase."""
    return _get_repo().create(data)


def update_meeting(meeting_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an existing meeting in Supabase."""
    return _get_repo().update(meeting_id, data)


def delete_meeting(meeting_id: str) -> bool:
    """Delete a meeting from Supabase."""
    return _get_repo().delete(meeting_id)


# Keep old function that does direct client access for specific use cases
def get_supabase_direct():
    """Get direct Supabase client for advanced operations."""
    return get_supabase_client()


def get_dashboard_stats() -> Dict[str, Any]:
    """
    Get meeting stats for the dashboard.
    
    Returns:
        Dict with meetings_count, signals_count, meetings_with_signals
    """
    client = get_supabase_client()
    if not client:
        return {"meetings_count": 0, "signals_count": 0, "meetings_with_signals": []}
    
    try:
        # Get meetings count
        count_result = client.table("meetings").select("id", count="exact").execute()
        meetings_count = count_result.count or 0
        
        # Get meetings with signals for stats
        meetings_with_signals = get_meetings_with_signals(limit=100)
        
        # Count total signals
        signals_count = 0
        for m in meetings_with_signals:
            signals = m.get("signals", {})
            for key in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                items = signals.get(key, [])
                if isinstance(items, list):
                    signals_count += len(items)
        
        return {
            "meetings_count": meetings_count,
            "signals_count": signals_count,
            "meetings_with_signals": meetings_with_signals,
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        return {"meetings_count": 0, "signals_count": 0, "meetings_with_signals": []}


def get_meeting_name(meeting_id: str) -> Optional[str]:
    """
    Get just the meeting name by ID.
    
    Args:
        meeting_id: UUID of the meeting
        
    Returns:
        Meeting name or None
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        result = client.table("meetings").select("meeting_name").eq("id", meeting_id).single().execute()
        if result.data:
            return result.data.get("meeting_name", "Unknown Meeting")
        return None
    except Exception as e:
        logger.error(f"Failed to get meeting name {meeting_id}: {e}")
        return None


def search_meetings(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search meetings by name or content.
    
    Args:
        query: Search query
        limit: Max results
        
    Returns:
        List of matching meetings
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        # Use ilike for case-insensitive search
        result = client.table("meetings").select("*").or_(
            f"meeting_name.ilike.%{query}%,synthesized_notes.ilike.%{query}%"
        ).limit(limit).execute()
        
        return [
            {
                "id": row.get("id"),
                "meeting_name": row.get("meeting_name"),
                "meeting_date": row.get("meeting_date"),
                "synthesized_notes": row.get("synthesized_notes", ""),
                "signals": row.get("signals", {}),
            }
            for row in result.data
        ]
    except Exception as e:
        logger.error(f"Failed to search meetings: {e}")
        return []


def create_meeting(
    meeting_name: str,
    synthesized_notes: str = "",
    meeting_date: Optional[str] = None,
    signals: Optional[Dict] = None,
    raw_text: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a new meeting in Supabase.
    
    Returns:
        Created meeting or None on failure
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        data = {
            "meeting_name": meeting_name,
            "synthesized_notes": synthesized_notes,
            "meeting_date": meeting_date or datetime.now().date().isoformat(),
            "signals": signals or {},
            "raw_text": raw_text,
        }
        
        result = client.table("meetings").insert(data).execute()
        
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to create meeting: {e}")
        return None


def update_meeting(meeting_id: str, updates: Dict[str, Any]) -> bool:
    """
    Update a meeting in Supabase.
    
    Args:
        meeting_id: UUID of the meeting
        updates: Dictionary of fields to update
        
    Returns:
        True if successful
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("meetings").update(updates).eq("id", meeting_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update meeting {meeting_id}: {e}")
        return False


def delete_meeting(meeting_id: str) -> bool:
    """
    Delete a meeting from Supabase.
    
    Args:
        meeting_id: UUID of the meeting
        
    Returns:
        True if successful
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("meetings").delete().eq("id", meeting_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete meeting {meeting_id}: {e}")
        return False


def update_meeting_signals(meeting_id: str, signals: Dict[str, Any]) -> bool:
    """
    Update signals for a specific meeting.
    
    Args:
        meeting_id: UUID of the meeting
        signals: Updated signals dictionary
        
    Returns:
        True if successful
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("meetings").update({"signals": signals}).eq("id", meeting_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update signals for meeting {meeting_id}: {e}")
        return False


def get_or_create_personal_meeting() -> Optional[Dict[str, Any]]:
    """
    Get the personal action items meeting, or create it if it doesn't exist.
    
    Returns:
        The personal meeting record or None on failure
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        result = client.table("meetings").select("id, signals").eq(
            "meeting_name", "Personal Action Items"
        ).execute()
        
        if result.data:
            return result.data[0]
        
        # Create the personal meeting
        new_meeting = {
            "meeting_name": "Personal Action Items",
            "meeting_type": "personal",
            "meeting_date": datetime.now().isoformat()[:10],
            "signals": {"action_items": []}
        }
        create_result = client.table("meetings").insert(new_meeting).execute()
        return create_result.data[0] if create_result.data else None
    except Exception as e:
        logger.error(f"Failed to get/create personal meeting: {e}")
        return None


def get_meetings_for_action_items(
    filter_type: str = "all", 
    sort_by: str = "date"
) -> List[Dict[str, Any]]:
    """
    Get meetings for the action items page with their signals.
    
    Args:
        filter_type: Filter type ('all', 'incomplete', 'blockers')
        sort_by: Sort field ('date', 'priority')
        
    Returns:
        List of meetings with action items
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        # Get meetings with signals, ordered by meeting date
        result = client.table("meetings").select(
            "id, meeting_name, meeting_date, signals"
        ).not_.is_("signals", "null").order(
            "meeting_date", desc=(sort_by == "date")
        ).execute()
        
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get meetings for action items: {e}")
        return []
