"""
Meetings Service - Supabase Direct Reads

This module provides meeting operations that read directly from Supabase,
eliminating the need for SQLite sync and enabling real-time data access.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_supabase_client():
    """Get Supabase client from infrastructure."""
    from ..infrastructure.supabase_client import get_supabase_client as _get_client
    return _get_client()


def get_all_meetings(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all meetings from Supabase.
    
    Returns:
        List of meeting dictionaries with id, meeting_name, meeting_date, signals, etc.
    """
    client = get_supabase_client()
    if not client:
        logger.warning("Supabase not available, returning empty list")
        return []
    
    try:
        result = client.table("meetings").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        meetings = []
        for row in result.data:
            meetings.append({
                "id": row.get("id"),
                "meeting_name": row.get("meeting_name", "Untitled Meeting"),
                "meeting_date": row.get("meeting_date"),
                "synthesized_notes": row.get("synthesized_notes", ""),
                "signals_json": json.dumps(row.get("signals", {})) if row.get("signals") else None,
                "signals": row.get("signals", {}),
                "raw_text": row.get("raw_text"),
                "created_at": row.get("created_at"),
            })
        
        return meetings
    except Exception as e:
        logger.error(f"Failed to get meetings from Supabase: {e}")
        return []


def get_meeting_by_id(meeting_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single meeting by ID from Supabase.
    
    Args:
        meeting_id: UUID of the meeting
        
    Returns:
        Meeting dictionary or None if not found
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        result = client.table("meetings").select("*").eq("id", meeting_id).single().execute()
        
        if result.data:
            row = result.data
            return {
                "id": row.get("id"),
                "meeting_name": row.get("meeting_name", "Untitled Meeting"),
                "meeting_date": row.get("meeting_date"),
                "synthesized_notes": row.get("synthesized_notes", ""),
                "signals_json": json.dumps(row.get("signals", {})) if row.get("signals") else None,
                "signals": row.get("signals", {}),
                "raw_text": row.get("raw_text"),
                "created_at": row.get("created_at"),
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get meeting {meeting_id} from Supabase: {e}")
        return None


def get_meetings_count() -> int:
    """
    Get total count of meetings in Supabase.
    
    Returns:
        Number of meetings
    """
    client = get_supabase_client()
    if not client:
        return 0
    
    try:
        result = client.table("meetings").select("id", count="exact").execute()
        return result.count or 0
    except Exception as e:
        logger.error(f"Failed to get meetings count: {e}")
        return 0


def get_recent_meetings(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent meetings.
    
    Returns:
        List of recent meetings with id, meeting_name, meeting_date
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("meetings").select(
            "id, meeting_name, meeting_date, created_at"
        ).order("meeting_date", desc=True, nullsfirst=False).limit(limit).execute()
        
        return [
            {
                "id": row.get("id"),
                "meeting_name": row.get("meeting_name", "Untitled Meeting"),
                "meeting_date": row.get("meeting_date"),
            }
            for row in result.data
        ]
    except Exception as e:
        logger.error(f"Failed to get recent meetings: {e}")
        return []


def get_meetings_with_signals(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all meetings that have signals data.
    
    Returns:
        List of meetings with id, meeting_name, signals
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("meetings").select(
            "id, meeting_name, signals, meeting_date, created_at"
        ).not_.is_("signals", "null").order(
            "meeting_date", desc=True, nullsfirst=False
        ).limit(limit).execute()
        
        meetings = []
        for row in result.data:
            signals = row.get("signals", {})
            if signals:  # Only include if signals is not empty
                meetings.append({
                    "id": row.get("id"),
                    "meeting_name": row.get("meeting_name", "Untitled Meeting"),
                    "meeting_date": row.get("meeting_date"),
                    "created_at": row.get("created_at"),
                    "signals_json": json.dumps(signals),
                    "signals": signals,
                })
        
        return meetings
    except Exception as e:
        logger.error(f"Failed to get meetings with signals: {e}")
        return []


def get_meeting_signals(meeting_id: str) -> Optional[Dict[str, Any]]:
    """
    Get signals for a specific meeting.
    
    Args:
        meeting_id: UUID of the meeting
        
    Returns:
        Signals dictionary or None
    """
    meeting = get_meeting_by_id(meeting_id)
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
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        result = client.table("meetings").select(
            "id, meeting_name, signals, meeting_date"
        ).not_.is_("signals", "null").gte("meeting_date", cutoff).execute()
        
        meetings = []
        for row in result.data:
            signals = row.get("signals", {})
            if signals:
                meetings.append({
                    "id": row.get("id"),
                    "meeting_name": row.get("meeting_name"),
                    "signals_json": json.dumps(signals),
                    "signals": signals,
                    "meeting_date": row.get("meeting_date"),
                })
        
        return meetings
    except Exception as e:
        logger.error(f"Failed to get meetings in range: {e}")
        return []


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
