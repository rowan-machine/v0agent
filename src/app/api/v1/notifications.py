# src/app/api/v1/notifications.py
"""
Notification API - Phase F3

REST endpoints for the notification system:
- GET /notifications - List pending notifications
- GET /notifications/unread-count - Badge count for UI
- PATCH /notifications/{id}/read - Mark as read
- POST /notifications/{id}/action - Approve/reject/dismiss
- DELETE /notifications/{id} - Remove notification

Connects to existing NotificationQueue service.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

from ...services.notification_queue import (
    NotificationQueue,
    NotificationType,
    NotificationPriority,
    Notification,
)

router = APIRouter()

# Initialize the queue
_queue: Optional[NotificationQueue] = None


def get_queue() -> NotificationQueue:
    """Get or create the notification queue singleton."""
    global _queue
    if _queue is None:
        _queue = NotificationQueue()
    return _queue


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class NotificationResponse(BaseModel):
    """Notification response model."""
    id: str
    type: str
    title: str
    body: str
    data: dict
    priority: str
    read: bool
    actioned: bool
    action_taken: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None

    @classmethod
    def from_notification(cls, n: Notification) -> "NotificationResponse":
        return cls(
            id=n.id,
            type=n.notification_type.value,
            title=n.title,
            body=n.body,
            data=n.data,
            priority=n.priority.value,
            read=n.read,
            actioned=n.actioned,
            action_taken=n.action_taken,
            created_at=n.created_at.isoformat(),
            expires_at=n.expires_at.isoformat() if n.expires_at else None,
        )


class UnreadCountResponse(BaseModel):
    """Unread count response."""
    count: int


class ActionRequest(BaseModel):
    """Request to take action on a notification."""
    action: str  # 'approve', 'reject', 'dismiss'
    feedback: Optional[str] = None


class ActionResponse(BaseModel):
    """Response after taking action."""
    success: bool
    notification_id: str
    action: str
    message: str


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    type: Optional[str] = Query(None, description="Filter by notification type"),
    unread_only: bool = Query(False, description="Only show unread notifications"),
    limit: int = Query(20, ge=1, le=100, description="Maximum notifications to return"),
):
    """
    List notifications for the current user.
    
    Returns pending (unactioned) notifications by default, ordered by priority and date.
    """
    queue = get_queue()
    
    # Convert type string to enum if provided
    notification_type = None
    if type:
        try:
            notification_type = NotificationType(type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid notification type: {type}. Valid types: {[t.value for t in NotificationType]}"
            )
    
    notifications = queue.get_pending(
        notification_type=notification_type,
        limit=limit
    )
    
    # Filter by read status if requested
    if unread_only:
        notifications = [n for n in notifications if not n.read]
    
    return [NotificationResponse.from_notification(n) for n in notifications]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count():
    """
    Get count of unread notifications.
    
    Used for the notification bell badge in the UI.
    """
    queue = get_queue()
    count = queue.get_unread_count()
    return UnreadCountResponse(count=count)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: str):
    """
    Get a single notification by ID.
    """
    queue = get_queue()
    notification = queue.get_by_id(notification_id)
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return NotificationResponse.from_notification(notification)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(notification_id: str):
    """
    Mark a notification as read.
    
    This removes it from the unread count but keeps it in the list.
    """
    queue = get_queue()
    
    # Mark as read
    queue.mark_read(notification_id)
    
    # Return updated notification
    notification = queue.get_by_id(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return NotificationResponse.from_notification(notification)


@router.post("/{notification_id}/action", response_model=ActionResponse)
async def take_action(notification_id: str, request: ActionRequest):
    """
    Take action on a notification (approve, reject, or dismiss).
    
    - **approve**: Accept the AI suggestion/signal
    - **reject**: Reject with optional feedback for AI learning
    - **dismiss**: Remove without taking action
    """
    queue = get_queue()
    
    valid_actions = ['approve', 'reject', 'dismiss']
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action: {request.action}. Valid actions: {valid_actions}"
        )
    
    # Get notification first to check it exists
    notification = queue.get_by_id(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Take action based on type
    if request.action == 'approve':
        queue.approve(notification_id, feedback=request.feedback)
        message = "Notification approved"
    elif request.action == 'reject':
        queue.reject(notification_id, reason=request.feedback)
        message = "Notification rejected"
    else:  # dismiss
        queue.dismiss(notification_id)
        message = "Notification dismissed"
    
    return ActionResponse(
        success=True,
        notification_id=notification_id,
        action=request.action,
        message=message
    )


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    """
    Delete a notification permanently.
    """
    queue = get_queue()
    
    notification = queue.get_by_id(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    queue.delete(notification_id)
    
    return {"success": True, "message": "Notification deleted"}


@router.post("/mark-all-read")
async def mark_all_read():
    """
    Mark all notifications as read.
    """
    queue = get_queue()
    count = queue.mark_all_read()
    
    return {"success": True, "marked_read": count}


# =============================================================================
# NOTIFICATION TYPE REFERENCE
# =============================================================================

@router.get("/types/list")
async def list_notification_types():
    """
    List all available notification types.
    
    Useful for UI filtering and documentation.
    """
    return {
        "types": [
            {
                "value": t.value,
                "name": t.name,
                "description": _get_type_description(t)
            }
            for t in NotificationType
        ]
    }


def _get_type_description(t: NotificationType) -> str:
    """Get human-readable description for notification type."""
    descriptions = {
        NotificationType.SIGNAL_REVIEW: "AI-extracted signal needs your approval",
        NotificationType.ACTION_DUE: "Action item approaching or past deadline",
        NotificationType.TRANSCRIPT_MATCH: "Meeting transcript matched to a ticket",
        NotificationType.MISSED_CRITERIA: "Items discussed in meeting not in ticket",
        NotificationType.MENTION: "You were mentioned in a meeting",
        NotificationType.COACH_RECOMMENDATION: "Career growth suggestion",
        NotificationType.AI_SUGGESTION: "General AI recommendation",
        NotificationType.DIKW_SYNTHESIS: "Knowledge synthesis ready for review",
    }
    return descriptions.get(t, "Notification")
