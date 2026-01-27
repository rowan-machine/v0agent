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
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _get_repository():
    """Get notifications repository (lazy import)."""
    from ..repositories import get_notifications_repository
    try:
        return get_notifications_repository()
    except RuntimeError:
        return None


@router.get("")
async def get_notifications(limit: int = 10):
    """Get user notifications with optional limit."""
    repo = _get_repository()
    
    if not repo:
        return JSONResponse({"notifications": [], "error": "Database unavailable"})
    
    try:
        notifications = repo.get_unactioned(limit=limit)
        
        result = []
        for n in notifications:
            n_dict = n.to_dict()
            # Parse action_url from data if available
            if n.data and isinstance(n.data, dict):
                n_dict['action_url'] = n.data.get('action_url', '')
            result.append(n_dict)
        
        return JSONResponse({"notifications": result})
    except Exception as e:
        logger.warning(f"Failed to fetch notifications: {e}")
        return JSONResponse({"notifications": [], "error": str(e)})


@router.get("/count")
async def get_notification_count():
    """Get count of unread notifications."""
    repo = _get_repository()
    
    if not repo:
        return JSONResponse({"unread": 0, "total": 0})
    
    try:
        unread = repo.get_unread_count()
        total = repo.get_total_unactioned_count()
        return JSONResponse({"unread": unread, "total": total})
    except Exception as e:
        logger.warning(f"Failed to get notification count: {e}")
        return JSONResponse({"unread": 0, "total": 0})


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark a notification as read."""
    repo = _get_repository()
    
    if not repo:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        repo.mark_read(notification_id)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.warning(f"Failed to mark notification read: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/read-all")
async def mark_all_notifications_read():
    """Mark all notifications as read."""
    repo = _get_repository()
    
    if not repo:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        count = repo.mark_all_read()
        return JSONResponse({"status": "ok", "count": count})
    except Exception as e:
        logger.warning(f"Failed to mark all notifications read: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete a notification."""
    repo = _get_repository()
    
    if not repo:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        repo.delete(notification_id)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.warning(f"Failed to delete notification: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("")
async def create_notification(data: dict):
    """Create a new notification."""
    repo = _get_repository()
    
    if not repo:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
    
    try:
        from ..repositories.notifications_repository import NotificationEntity
        
        notification = NotificationEntity(
            notification_type=data.get("type", "info"),
            title=data.get("title", ""),
            body=data.get("message", ""),
            data=data.get("data", {}),
            priority=data.get("priority", "normal"),
        )
        
        notification_id = repo.insert(notification)
        return JSONResponse({"status": "ok", "id": notification_id})
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
