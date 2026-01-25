"""
Tickets Service - Supabase Direct Reads

This module provides ticket operations that read directly from Supabase,
eliminating the need for SQLite sync and enabling real-time data access.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_supabase_client():
    """Get Supabase client from infrastructure."""
    from ..infrastructure.supabase_client import get_supabase_client as _get_client
    return _get_client()


def get_all_tickets(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all tickets from Supabase.
    """
    client = get_supabase_client()
    if not client:
        logger.warning("Supabase not available, returning empty list")
        return []
    
    try:
        result = client.table("tickets").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        return [_format_ticket(row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get tickets from Supabase: {e}")
        return []


def _format_ticket(row: Dict) -> Dict[str, Any]:
    """Format a Supabase ticket row to match expected format."""
    # Handle tags - Supabase stores as array, template expects comma-separated string
    tags = row.get("tags", [])
    if isinstance(tags, list):
        tags = ", ".join(tags) if tags else ""
    elif tags is None:
        tags = ""
    
    return {
        "id": row.get("id"),
        "ticket_id": row.get("ticket_id"),
        "title": row.get("title", ""),
        "description": row.get("description", ""),
        "status": row.get("status", "backlog"),
        "priority": row.get("priority"),
        "sprint_points": row.get("sprint_points", 0),
        "in_sprint": row.get("in_sprint", True),
        "ai_summary": row.get("ai_summary"),
        "implementation_plan": row.get("implementation_plan"),
        "task_decomposition": row.get("task_decomposition"),
        "tags": tags,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single ticket by UUID or ticket_id from Supabase.
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        # Try UUID first
        result = client.table("tickets").select("*").eq("id", ticket_id).execute()
        if result.data:
            return _format_ticket(result.data[0])
        
        # Try ticket_id (e.g., "SIG-1")
        result = client.table("tickets").select("*").eq("ticket_id", ticket_id).execute()
        if result.data:
            return _format_ticket(result.data[0])
        
        return None
    except Exception as e:
        logger.error(f"Failed to get ticket {ticket_id} from Supabase: {e}")
        return None


def get_tickets_count(statuses: Optional[List[str]] = None) -> int:
    """
    Get count of tickets, optionally filtered by status.
    """
    client = get_supabase_client()
    if not client:
        return 0
    
    try:
        query = client.table("tickets").select("id", count="exact")
        if statuses:
            query = query.in_("status", statuses)
        result = query.execute()
        return result.count or 0
    except Exception as e:
        logger.error(f"Failed to get tickets count: {e}")
        return 0


def get_active_tickets(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get tickets with active statuses (todo, in_progress, in_review, blocked).
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("tickets").select("*").in_(
            "status", ["todo", "in_progress", "in_review", "blocked"]
        ).order("updated_at", desc=True).limit(limit).execute()
        
        # Sort by status priority
        tickets = [_format_ticket(row) for row in result.data]
        status_priority = {"in_progress": 1, "blocked": 2, "in_review": 3, "todo": 4}
        tickets.sort(key=lambda t: status_priority.get(t["status"], 5))
        
        return tickets
    except Exception as e:
        logger.error(f"Failed to get active tickets: {e}")
        return []


def get_blocked_tickets(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get blocked tickets.
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("tickets").select("*").eq(
            "status", "blocked"
        ).order("updated_at", desc=True).limit(limit).execute()
        
        return [_format_ticket(row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get blocked tickets: {e}")
        return []


def get_stale_in_progress_tickets(days: int = 3, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get tickets that have been in_progress for more than N days.
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        result = client.table("tickets").select("*").eq(
            "status", "in_progress"
        ).lt("updated_at", cutoff).order("updated_at").limit(limit).execute()
        
        return [_format_ticket(row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get stale tickets: {e}")
        return []


def get_tickets_created_since(cutoff_date: str) -> int:
    """
    Get count of tickets created since a date.
    """
    client = get_supabase_client()
    if not client:
        return 0
    
    try:
        result = client.table("tickets").select("id", count="exact").gte(
            "created_at", cutoff_date
        ).execute()
        return result.count or 0
    except Exception as e:
        logger.error(f"Failed to get tickets count since {cutoff_date}: {e}")
        return 0


def get_tickets_by_status(status: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get tickets filtered by status.
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("tickets").select("*").eq(
            "status", status
        ).order("updated_at", desc=True).limit(limit).execute()
        
        return [_format_ticket(row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get tickets by status {status}: {e}")
        return []


def get_sprint_tickets() -> List[Dict[str, Any]]:
    """
    Get all tickets in the current sprint.
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("tickets").select("*").eq(
            "in_sprint", True
        ).order("status").execute()
        
        return [_format_ticket(row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get sprint tickets: {e}")
        return []


def get_active_sprint_tickets() -> List[Dict[str, Any]]:
    """
    Get active tickets in sprint (not done) for burndown calculation.
    Returns tickets sorted by status priority.
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("tickets").select("*").eq(
            "in_sprint", True
        ).in_(
            "status", ["todo", "in_progress", "in_review", "blocked"]
        ).execute()
        
        tickets = [_format_ticket(row) for row in result.data]
        
        # Sort by status priority
        status_priority = {"blocked": 0, "in_progress": 1, "in_review": 2, "todo": 3}
        tickets.sort(key=lambda t: (
            status_priority.get(t["status"], 5),
            -(t.get("sprint_points") or 0)
        ))
        
        return tickets
    except Exception as e:
        logger.error(f"Failed to get active sprint tickets: {e}")
        return []


def get_all_sprint_tickets_for_burndown() -> List[Dict[str, Any]]:
    """
    Get ALL sprint tickets (active + completed) for burndown chart calculation.
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("tickets").select("*").eq(
            "in_sprint", True
        ).execute()
        
        return [_format_ticket(row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get all sprint tickets: {e}")
        return []


def get_sprint_ticket_stats() -> Dict[str, Dict[str, int]]:
    """
    Get ticket statistics grouped by status for sprint tickets.
    Returns a dict like: {"todo": {"count": 5, "points": 10}, ...}
    """
    client = get_supabase_client()
    if not client:
        return {}
    
    try:
        result = client.table("tickets").select("*").eq(
            "in_sprint", True
        ).execute()
        
        stats = {
            "todo": {"count": 0, "points": 0},
            "in_progress": {"count": 0, "points": 0},
            "in_review": {"count": 0, "points": 0},
            "blocked": {"count": 0, "points": 0},
            "done": {"count": 0, "points": 0},
        }
        
        for row in result.data:
            status = row.get("status", "backlog")
            if status in stats:
                stats[status]["count"] += 1
                stats[status]["points"] += row.get("sprint_points") or 0
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get sprint ticket stats: {e}")
        return {}


def get_blocked_sprint_tickets(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get blocked tickets that are in sprint.
    """
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        result = client.table("tickets").select("*").eq(
            "status", "blocked"
        ).eq("in_sprint", True).limit(limit).execute()
        
        return [_format_ticket(row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get blocked sprint tickets: {e}")
        return []


def get_completed_sprint_points() -> int:
    """
    Get total points from completed sprint tickets.
    """
    client = get_supabase_client()
    if not client:
        return 0
    
    try:
        result = client.table("tickets").select("sprint_points").eq(
            "in_sprint", True
        ).in_("status", ["done", "complete"]).execute()
        
        total = sum(row.get("sprint_points") or 0 for row in result.data)
        return total
    except Exception as e:
        logger.error(f"Failed to get completed sprint points: {e}")
        return 0


def create_ticket(
    ticket_id: str,
    title: str,
    description: str = "",
    status: str = "backlog",
    priority: Optional[str] = None,
    ai_summary: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a new ticket in Supabase.
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        data = {
            "ticket_id": ticket_id,
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "ai_summary": ai_summary,
        }
        
        result = client.table("tickets").insert(data).execute()
        
        if result.data:
            return _format_ticket(result.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to create ticket: {e}")
        return None


def update_ticket(ticket_id: str, updates: Dict[str, Any]) -> bool:
    """
    Update a ticket in Supabase.
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        # Add updated_at timestamp
        updates["updated_at"] = datetime.now().isoformat()
        client.table("tickets").update(updates).eq("id", ticket_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update ticket {ticket_id}: {e}")
        return False


def delete_ticket(ticket_id: str) -> bool:
    """
    Delete a ticket from Supabase.
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("tickets").delete().eq("id", ticket_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete ticket {ticket_id}: {e}")
        return False


def get_next_ticket_number() -> int:
    """
    Get the next ticket number for creating new tickets.
    """
    client = get_supabase_client()
    if not client:
        return 1
    
    try:
        result = client.table("tickets").select("id", count="exact").execute()
        return (result.count or 0) + 1
    except Exception as e:
        logger.error(f"Failed to get next ticket number: {e}")
        return 1
