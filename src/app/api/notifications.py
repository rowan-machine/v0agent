# src/app/api/notifications.py
"""
Notifications API Routes

Handles user notifications:
- List notifications
- Mark as read
- Delete notifications
- Notification counts
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _get_supabase():
    """Get Supabase client (lazy import for compatibility)."""
    from ..db_supabase import supabase
    return supabase


@router.get("")
async def get_notifications(limit: int = 10):
    """Get user notifications with optional limit."""
    supabase = _get_supabase()
    
    if not supabase:
        return JSONResponse({"notifications": [], "error": "Database unavailable"})
    
    try:
        # Filter for non-actioned notifications (actioned_at is null)
        result = supabase.table("notifications").select("*").is_(
            "actioned_at", "null"
        ).order("created_at", desc=True).limit(limit).execute()
        
        notifications = []
        for row in result.data or []:
            n_dict = {
                "id": row.get("id"),
                "type": row.get("type") or row.get("notification_type"),
                "title": row.get("title"),
                "message": row.get("body") or row.get("message"),
                "data": row.get("metadata"),
                "read": row.get("read_at") is not None,
                "created_at": row.get("created_at"),
                "actioned": row.get("actioned_at") is not None,
                "action_taken": row.get("action_taken"),
                "expires_at": row.get("expires_at"),
            }
            # Parse action_url from metadata JSON if available
            if n_dict.get('data'):
                try:
                    data = n_dict['data'] if isinstance(n_dict['data'], dict) else json.loads(n_dict['data'])
                    n_dict['action_url'] = data.get('action_url', '')
                except:
                    pass
            notifications.append(n_dict)
        return JSONResponse({"notifications": notifications})
    except Exception as e:
        logger.warning(f"Supabase notifications fetch failed: {e}")
        return JSONResponse({"notifications": [], "error": str(e)})


@router.get("/count")
async def get_notification_count():
    """Get count of unread notifications."""
    supabase = _get_supabase()
    
    if not supabase:
        return JSONResponse({"unread": 0, "total": 0})
    
    try:
        # Count unread (read_at is null)
        unread_result = supabase.table("notifications").select(
            "id", count="exact"
        ).is_("read_at", "null").execute()
        unread = unread_result.count or 0
        
        # Count total non-actioned (actioned_at is null)
        total_result = supabase.table("notifications").select(
            "id", count="exact"
        ).is_("actioned_at", "null").execute()
        total = total_result.count or 0
        
        return JSONResponse({"unread": unread, "total": total})
    except Exception as e:
        logger.warning(f"Supabase notification count failed: {e}")
        return JSONResponse({"unread": 0, "total": 0})


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark a notification as read."""
    supabase = _get_supabase()
    
    if not supabase:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        supabase.table("notifications").update({
            "read_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", notification_id).execute()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.warning(f"Supabase mark read failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/read-all")
async def mark_all_notifications_read():
    """Mark all notifications as read."""
    supabase = _get_supabase()
    
    if not supabase:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        supabase.table("notifications").update({
            "read_at": datetime.now(timezone.utc).isoformat()
        }).is_("read_at", "null").execute()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.warning(f"Supabase mark all read failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete a notification."""
    supabase = _get_supabase()
    
    if not supabase:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        supabase.table("notifications").delete().eq("id", notification_id).execute()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.warning(f"Supabase delete failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("")
async def create_notification(data: dict):
    """Create a new notification."""
    supabase = _get_supabase()
    
    if not supabase:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        result = supabase.table("notifications").insert({
            "type": data.get("type", "info"),
            "title": data.get("title", ""),
            "body": data.get("message", ""),
            "metadata": data.get("data"),
        }).execute()
        
        return JSONResponse({
            "status": "ok",
            "id": result.data[0]["id"] if result.data else None
        })
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
