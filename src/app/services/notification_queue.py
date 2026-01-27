"""
Human-in-the-Loop Notification Queue Service - Supabase Only

Provides a notification system for human review/approval workflows.
All data stored in Supabase.
"""

import uuid
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def _get_supabase():
    """Get Supabase client."""
    from ..infrastructure.supabase_client import get_supabase_client
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not available")
    return client


class NotificationType(Enum):
    """Types of notifications for human review."""
    SIGNAL_REVIEW = "signal_review"
    ACTION_DUE = "action_due"
    TRANSCRIPT_MATCH = "transcript_match"
    MISSED_CRITERIA = "missed_criteria"
    MENTION = "mention"
    COACH_RECOMMENDATION = "coach"
    AI_SUGGESTION = "ai_suggestion"
    DIKW_SYNTHESIS = "dikw_synthesis"


class NotificationPriority(Enum):
    """Priority levels for notifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """A notification for human review."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    notification_type: NotificationType = NotificationType.AI_SUGGESTION
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    read: bool = False
    actioned: bool = False
    action_taken: Optional[str] = None
    action_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "notification_type": self.notification_type.value,
            "title": self.title,
            "body": self.body,
            "data": json.dumps(self.data) if isinstance(self.data, dict) else self.data,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "read": self.read,
            "actioned": self.actioned,
            "action_taken": self.action_taken,
            "action_at": self.action_at.isoformat() if self.action_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Notification":
        """Create from database row."""
        notification_type = data.get("notification_type") or data.get("type", "ai_suggestion")
        data_field = data.get("data") or "{}"
        if isinstance(data_field, str):
            try:
                data_field = json.loads(data_field)
            except:
                data_field = {}
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = datetime.now()
        
        action_at = data.get("action_at") or data.get("actioned_at")
        if isinstance(action_at, str):
            try:
                action_at = datetime.fromisoformat(action_at.replace('Z', '+00:00'))
            except:
                action_at = None
        
        expires_at = data.get("expires_at")
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except:
                expires_at = None
        
        return cls(
            id=str(data.get("id", uuid.uuid4())),
            notification_type=NotificationType(notification_type) if notification_type in [e.value for e in NotificationType] else NotificationType.AI_SUGGESTION,
            title=data.get("title", ""),
            body=data.get("body") or data.get("message") or "",
            data=data_field,
            priority=NotificationPriority(data.get("priority", "normal")),
            created_at=created_at or datetime.now(),
            read=bool(data.get("read", False)),
            actioned=bool(data.get("actioned", False)),
            action_taken=data.get("action_taken"),
            action_at=action_at,
            expires_at=expires_at,
        )


class NotificationQueue:
    """Human-in-the-loop notification queue - Supabase only."""
    
    def __init__(self):
        """Initialize notification queue."""
        logger.info("NotificationQueue initialized (Supabase-only)")
    
    def create(self, notification: Notification) -> str:
        """Create a new notification in Supabase."""
        sb = _get_supabase()
        
        result = sb.table("notifications").insert({
            "id": notification.id,
            "type": notification.notification_type.value,
            "title": notification.title,
            "body": notification.body,
            "data": notification.data,
            "priority": notification.priority.value,
            "read": notification.read,
            "created_at": notification.created_at.isoformat() if isinstance(notification.created_at, datetime) else notification.created_at,
            "expires_at": notification.expires_at.isoformat() if notification.expires_at else None,
        }).execute()
        
        if result.data:
            logger.info(f"Created notification: {notification.id} ({notification.notification_type.value})")
            return notification.id
        
        raise RuntimeError("Failed to create notification")
    
    def create_signal_review(
        self,
        signal_type: str,
        signal_text: str,
        meeting_id: int,
        confidence: float = 0.8,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Notification:
        """Create a signal review notification."""
        notification = Notification(
            notification_type=NotificationType.SIGNAL_REVIEW,
            title=f"Review {signal_type.replace('_', ' ').title()}",
            body=signal_text[:200],
            data={
                "signal_type": signal_type,
                "signal_text": signal_text,
                "meeting_id": meeting_id,
                "confidence": confidence,
            },
            priority=priority,
        )
        self.create(notification)
        return notification
    
    def create_action_due(
        self,
        action_text: str,
        due_date: datetime,
        meeting_id: int,
        owner: Optional[str] = None
    ) -> Notification:
        """Create an action item due notification."""
        days_until = (due_date - datetime.now()).days
        
        if days_until < 0:
            priority = NotificationPriority.URGENT
            title = "⚠️ Overdue Action Item"
        elif days_until == 0:
            priority = NotificationPriority.HIGH
            title = "📢 Action Due Today"
        elif days_until <= 2:
            priority = NotificationPriority.HIGH
            title = f"⏰ Action Due in {days_until} days"
        else:
            priority = NotificationPriority.NORMAL
            title = f"📋 Action Due {due_date.strftime('%b %d')}"
        
        notification = Notification(
            notification_type=NotificationType.ACTION_DUE,
            title=title,
            body=action_text[:200],
            data={
                "action_text": action_text,
                "due_date": due_date.isoformat(),
                "meeting_id": meeting_id,
                "owner": owner,
                "days_until": days_until,
            },
            priority=priority,
            expires_at=due_date + timedelta(days=7),
        )
        self.create(notification)
        return notification
    
    def create_coach_recommendation(
        self,
        recommendation: str,
        category: str,
        related_data: Optional[Dict] = None
    ) -> Notification:
        """Create a coach recommendation notification."""
        notification = Notification(
            notification_type=NotificationType.COACH_RECOMMENDATION,
            title=f"💡 Coach: {category.title()}",
            body=recommendation[:200],
            data={
                "recommendation": recommendation,
                "category": category,
                **(related_data or {}),
            },
            priority=NotificationPriority.NORMAL,
            expires_at=datetime.now() + timedelta(days=14),
        )
        self.create(notification)
        return notification
    
    def get_pending(
        self,
        notification_type: Optional[NotificationType] = None,
        limit: int = 20
    ) -> List[Notification]:
        """Get pending (unactioned) notifications."""
        sb = _get_supabase()
        
        # Build query - get unactioned notifications
        query = sb.table("notifications").select("*").is_("actioned_at", "null")
        
        if notification_type:
            query = query.eq("type", notification_type.value)
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        notifications = []
        for row in result.data or []:
            try:
                notifications.append(Notification.from_dict(row))
            except Exception as e:
                logger.warning(f"Error parsing notification: {e}")
        
        return notifications
    
    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        sb = _get_supabase()
        result = sb.table("notifications").select("id", count="exact").eq("read", False).execute()
        return result.count or 0
    
    def mark_read(self, notification_id: str):
        """Mark a notification as read."""
        sb = _get_supabase()
        sb.table("notifications").update({"read": True}).eq("id", notification_id).execute()
    
    def approve(self, notification_id: str, feedback: Optional[str] = None) -> bool:
        """Approve a pending notification."""
        return self._action(notification_id, "approved", feedback)
    
    def reject(self, notification_id: str, reason: Optional[str] = None) -> bool:
        """Reject a pending notification."""
        return self._action(notification_id, "rejected", reason)
    
    def dismiss(self, notification_id: str) -> bool:
        """Dismiss a notification without approving/rejecting."""
        return self._action(notification_id, "dismissed", None)
    
    def _action(self, notification_id: str, action: str, notes: Optional[str]) -> bool:
        """Process an action on a notification."""
        now = datetime.now().isoformat()
        sb = _get_supabase()
        
        # Get notification first
        result = sb.table("notifications").select("*").eq("id", notification_id).execute()
        
        if not result.data:
            logger.warning(f"Notification {notification_id} not found")
            return False
        
        notification_data = result.data[0]
        data = notification_data.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        data["action_notes"] = notes
        
        sb.table("notifications").update({
            "actioned_at": now,
            "action_taken": action,
            "read": True,
            "data": data,
        }).eq("id", notification_id).execute()
        
        # Record signal feedback if applicable
        if notification_data.get("type") == NotificationType.SIGNAL_REVIEW.value:
            self._record_signal_feedback(notification_data, action, notes)
        
        logger.info(f"Notification {notification_id} {action}")
        return True
    
    def _record_signal_feedback(self, notification_data: dict, action: str, notes: Optional[str]):
        """Record signal feedback for learning loop."""
        try:
            data = notification_data.get("data", {})
            if isinstance(data, str):
                data = json.loads(data)
            
            meeting_id = data.get("meeting_id")
            signal_type = data.get("signal_type")
            signal_text = data.get("signal_text")
            
            if not all([meeting_id, signal_type, signal_text]):
                return
            
            feedback = "up" if action == "approved" else "down"
            
            sb = _get_supabase()
            sb.table("signal_feedback").insert({
                "meeting_id": meeting_id,
                "signal_type": signal_type,
                "signal_text": signal_text,
                "feedback": feedback,
                "rejection_reason": notes if action == "rejected" else None,
            }).execute()
            
            logger.info(f"Recorded signal feedback: {signal_type} → {feedback}")
        except Exception as e:
            logger.error(f"Failed to record signal feedback: {e}")
    
    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        """Get a notification by ID."""
        sb = _get_supabase()
        result = sb.table("notifications").select("*").eq("id", notification_id).execute()
        
        if result.data:
            return Notification.from_dict(result.data[0])
        return None
    
    def delete(self, notification_id: str) -> bool:
        """Delete a notification."""
        sb = _get_supabase()
        sb.table("notifications").delete().eq("id", notification_id).execute()
        logger.info(f"Deleted notification {notification_id}")
        return True
    
    def mark_all_read(self) -> int:
        """Mark all notifications as read."""
        sb = _get_supabase()
        result = sb.table("notifications").update({"read": True}).eq("read", False).execute()
        count = len(result.data) if result.data else 0
        logger.info(f"Marked {count} notifications as read")
        return count
    
    def cleanup_expired(self) -> int:
        """Remove expired notifications."""
        now = datetime.now().isoformat()
        sb = _get_supabase()
        result = sb.table("notifications").delete().lt("expires_at", now).execute()
        count = len(result.data) if result.data else 0
        logger.info(f"Cleaned up {count} expired notifications")
        return count


# =============================================================================
# Singleton and API Functions
# =============================================================================

_notification_queue: Optional[NotificationQueue] = None


def get_notification_queue() -> NotificationQueue:
    """Get the singleton notification queue instance."""
    global _notification_queue
    if _notification_queue is None:
        _notification_queue = NotificationQueue()
    return _notification_queue


def create_signal_review_notification(
    signal_type: str,
    signal_text: str,
    meeting_id: int,
    confidence: float = 0.8
) -> str:
    """Create a signal review notification and return its ID."""
    queue = get_notification_queue()
    notification = queue.create_signal_review(
        signal_type=signal_type,
        signal_text=signal_text,
        meeting_id=meeting_id,
        confidence=confidence,
    )
    return notification.id


def get_pending_reviews(limit: int = 20) -> List[dict]:
    """Get pending notifications as dictionaries for API response."""
    queue = get_notification_queue()
    notifications = queue.get_pending(limit=limit)
    return [n.to_dict() for n in notifications]
