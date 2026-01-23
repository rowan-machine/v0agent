"""
Human-in-the-Loop Notification Queue Service

Provides a notification system for human review/approval workflows.
Integrates with AgentBus for multi-agent communication.

Features:
- Pending review items queue (signals, AI suggestions, etc.)
- Approval/rejection workflow
- Priority-based notification ordering
- Integration with AgentBus message types
"""

import uuid
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

from ..db import connect

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications for human review."""
    SIGNAL_REVIEW = "signal_review"          # AI-extracted signal needs approval
    ACTION_DUE = "action_due"                # Action item approaching deadline
    TRANSCRIPT_MATCH = "transcript_match"    # Auto-suggested transcript-ticket pairing
    MISSED_CRITERIA = "missed_criteria"      # Items in transcript not in ticket
    MENTION = "mention"                      # User mentioned in transcript
    COACH_RECOMMENDATION = "coach"           # Career coach suggestion
    AI_SUGGESTION = "ai_suggestion"          # General AI recommendation
    DIKW_SYNTHESIS = "dikw_synthesis"        # Knowledge synthesis needs review


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
    action_taken: Optional[str] = None  # 'approved', 'rejected', 'dismissed'
    action_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "notification_type": self.notification_type.value,
            "title": self.title,
            "body": self.body,
            "data": json.dumps(self.data),
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "read": self.read,
            "actioned": self.actioned,
            "action_taken": self.action_taken,
            "action_at": self.action_at.isoformat() if self.action_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Notification":
        """Create from database row."""
        return cls(
            id=data["id"],
            notification_type=NotificationType(data["notification_type"]),
            title=data["title"],
            body=data.get("body") or "",
            data=json.loads(data.get("data") or "{}"),
            priority=NotificationPriority(data.get("priority", "normal")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            read=data.get("read", False),
            actioned=data.get("actioned", False),
            action_taken=data.get("action_taken"),
            action_at=datetime.fromisoformat(data["action_at"]) if data.get("action_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )


class NotificationQueue:
    """
    Human-in-the-loop notification queue.
    
    Usage:
        queue = NotificationQueue()
        
        # Create a notification for signal review
        notification = queue.create_signal_review(
            signal_type="action_item",
            signal_text="Rowan: Update documentation by Friday",
            meeting_id=123
        )
        
        # Get pending notifications
        pending = queue.get_pending(limit=10)
        
        # Process approval/rejection
        queue.approve(notification.id, feedback="Good signal")
        queue.reject(notification.id, reason="Too vague")
    """
    
    def __init__(self):
        """Initialize notification queue."""
        self._initialize_tables()
        logger.info("NotificationQueue initialized")
    
    def _initialize_tables(self):
        """Create notification tables if not exists."""
        with connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    data TEXT DEFAULT '{}',
                    priority TEXT DEFAULT 'normal',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    read INTEGER DEFAULT 0,
                    actioned INTEGER DEFAULT 0,
                    action_taken TEXT,
                    action_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_pending 
                ON notifications(actioned, priority, created_at DESC)
                WHERE actioned = 0
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_type 
                ON notifications(notification_type, created_at DESC)
            """)
            conn.commit()
    
    def create(self, notification: Notification) -> str:
        """Create a new notification.
        
        Args:
            notification: Notification to create
            
        Returns:
            Notification ID
        """
        supabase = get_supabase()
        
        if supabase:
            try:
                result = supabase.table("notifications").insert({
                    "id": notification.id,
                    "type": notification.notification_type.value,
                    "title": notification.title,
                    "body": notification.body,
                    "data": notification.data,
                    "priority": notification.priority.value,
                    "read": notification.read,
                }).execute()
                
                if result.data:
                    logger.info(f"Created notification in Supabase: {notification.id}")
                    return notification.id
            except Exception as e:
                logger.warning(f"Supabase insert failed, falling back to SQLite: {e}")
        
        # SQLite fallback
        with connect() as conn:
            data = notification.to_dict()
            placeholders = ", ".join(["?"] * len(data))
            columns = ", ".join(data.keys())
            
            conn.execute(f"""
                INSERT INTO notifications ({columns})
                VALUES ({placeholders})
            """, tuple(data.values()))
            conn.commit()
        
        logger.info(f"Created notification: {notification.id} ({notification.notification_type.value})")
        return notification.id
    
    def create_signal_review(
        self,
        signal_type: str,
        signal_text: str,
        meeting_id: int,
        confidence: float = 0.8,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Notification:
        """Create a signal review notification.
        
        Args:
            signal_type: Type of signal (action_item, decision, etc.)
            signal_text: The extracted signal text
            meeting_id: Related meeting ID
            confidence: AI confidence score
            priority: Notification priority
            
        Returns:
            Created notification
        """
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
        """Create an action item due notification.
        
        Args:
            action_text: The action item text
            due_date: When the action is due
            meeting_id: Related meeting ID
            owner: Person responsible
            
        Returns:
            Created notification
        """
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
        """Create a coach recommendation notification.
        
        Args:
            recommendation: The coaching recommendation
            category: Category (growth, skills, feedback, etc.)
            related_data: Additional context
            
        Returns:
            Created notification
        """
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
        """Get pending (unactioned) notifications.
        
        Args:
            notification_type: Filter by type (optional)
            limit: Maximum number to return
            
        Returns:
            List of pending notifications
        """
        supabase = get_supabase()
        
        if supabase:
            try:
                query = supabase.table("notifications").select("*").eq("actioned", False)
                
                if notification_type:
                    query = query.eq("type", notification_type.value)
                
                result = query.order("created_at", desc=True).limit(limit).execute()
                
                if result.data:
                    # Map Supabase column names to our model
                    return [Notification.from_dict({
                        **row,
                        "notification_type": row.get("type"),
                    }) for row in result.data]
            except Exception as e:
                logger.warning(f"Supabase query failed, falling back to SQLite: {e}")
        
        # SQLite fallback
        with connect() as conn:
            query = """
                SELECT * FROM notifications
                WHERE actioned = 0
            """
            params = []
            
            if notification_type:
                query += " AND notification_type = ?"
                params.append(notification_type.value)
            
            query += " ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END, created_at DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
        
        return [Notification.from_dict(dict(row)) for row in rows]
    
    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        supabase = get_supabase()
        
        if supabase:
            try:
                result = supabase.table("notifications").select("id", count="exact").eq("read", False).execute()
                return result.count or 0
            except Exception as e:
                logger.warning(f"Supabase count failed: {e}")
        
        with connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM notifications WHERE read = 0").fetchone()
            return result[0] if result else 0
    
    def mark_read(self, notification_id: str):
        """Mark a notification as read.
        
        Args:
            notification_id: Notification ID
        """
        supabase = get_supabase()
        
        if supabase:
            try:
                supabase.table("notifications").update({"read": True}).eq("id", notification_id).execute()
                return
            except Exception as e:
                logger.warning(f"Supabase update failed: {e}")
        
        with connect() as conn:
            conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
            conn.commit()
    
    def approve(self, notification_id: str, feedback: Optional[str] = None) -> bool:
        """Approve a pending notification (e.g., signal review).
        
        Args:
            notification_id: Notification ID
            feedback: Optional approval feedback
            
        Returns:
            True if successful
        """
        return self._action(notification_id, "approved", feedback)
    
    def reject(self, notification_id: str, reason: Optional[str] = None) -> bool:
        """Reject a pending notification.
        
        Args:
            notification_id: Notification ID
            reason: Optional rejection reason
            
        Returns:
            True if successful
        """
        return self._action(notification_id, "rejected", reason)
    
    def dismiss(self, notification_id: str) -> bool:
        """Dismiss a notification without approving/rejecting.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            True if successful
        """
        return self._action(notification_id, "dismissed", None)
    
    def _action(self, notification_id: str, action: str, notes: Optional[str]) -> bool:
        """Process an action on a notification.
        
        Args:
            notification_id: Notification ID
            action: Action taken ('approved', 'rejected', 'dismissed')
            notes: Optional notes about the action
            
        Returns:
            True if successful
        """
        now = datetime.now().isoformat()
        
        supabase = get_supabase()
        
        if supabase:
            try:
                # Get notification first to record feedback
                result = supabase.table("notifications").select("*").eq("id", notification_id).single().execute()
                
                if result.data:
                    data = result.data.get("data", {})
                    if isinstance(data, str):
                        data = json.loads(data)
                    data["action_notes"] = notes
                    
                    supabase.table("notifications").update({
                        "actioned": True,
                        "action_taken": action,
                        "action_at": now,
                        "read": True,
                        "data": data,
                    }).eq("id", notification_id).execute()
                    
                    # If this was a signal review, record feedback for learning
                    if result.data.get("type") == NotificationType.SIGNAL_REVIEW.value:
                        self._record_signal_feedback(result.data, action, notes)
                    
                    logger.info(f"Notification {notification_id} {action}")
                    return True
            except Exception as e:
                logger.warning(f"Supabase action failed: {e}")
        
        # SQLite fallback
        with connect() as conn:
            conn.execute("""
                UPDATE notifications 
                SET actioned = 1, action_taken = ?, action_at = ?, read = 1
                WHERE id = ?
            """, (action, now, notification_id))
            conn.commit()
        
        logger.info(f"Notification {notification_id} {action}")
        return True
    
    def _record_signal_feedback(self, notification_data: dict, action: str, notes: Optional[str]):
        """Record signal feedback for the learning loop.
        
        This feeds into SignalLearningService for AI improvement.
        """
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
            
            supabase = get_supabase()
            if supabase:
                supabase.table("signal_feedback").insert({
                    "meeting_id": meeting_id,
                    "signal_type": signal_type,
                    "signal_text": signal_text,
                    "feedback": feedback,
                    "rejection_reason": notes if action == "rejected" else None,
                }).execute()
            else:
                with connect() as conn:
                    conn.execute("""
                        INSERT INTO signal_feedback 
                        (meeting_id, signal_type, signal_text, feedback, rejection_reason)
                        VALUES (?, ?, ?, ?, ?)
                    """, (meeting_id, signal_type, signal_text, feedback, 
                          notes if action == "rejected" else None))
                    conn.commit()
            
            logger.info(f"Recorded signal feedback: {signal_type} → {feedback}")
        except Exception as e:
            logger.error(f"Failed to record signal feedback: {e}")
    
    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        """Get a notification by ID.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Notification or None if not found
        """
        supabase = get_supabase()
        
        if supabase:
            try:
                result = supabase.table("notifications").select("*").eq("id", notification_id).single().execute()
                if result.data:
                    return Notification.from_dict({
                        **result.data,
                        "notification_type": result.data.get("type"),
                    })
            except Exception as e:
                logger.warning(f"Supabase query failed: {e}")
        
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM notifications WHERE id = ?",
                (notification_id,)
            ).fetchone()
        
        if row:
            return Notification.from_dict(dict(row))
        return None
    
    def delete(self, notification_id: str) -> bool:
        """Delete a notification.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            True if deleted
        """
        supabase = get_supabase()
        
        if supabase:
            try:
                supabase.table("notifications").delete().eq("id", notification_id).execute()
                logger.info(f"Deleted notification {notification_id}")
                return True
            except Exception as e:
                logger.warning(f"Supabase delete failed: {e}")
        
        with connect() as conn:
            conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
            conn.commit()
        
        logger.info(f"Deleted notification {notification_id}")
        return True
    
    def mark_all_read(self) -> int:
        """Mark all notifications as read.
        
        Returns:
            Number of notifications marked read
        """
        supabase = get_supabase()
        
        if supabase:
            try:
                result = supabase.table("notifications").update({"read": True}).eq("read", False).execute()
                count = len(result.data) if result.data else 0
                logger.info(f"Marked {count} notifications as read (Supabase)")
                return count
            except Exception as e:
                logger.warning(f"Supabase update failed: {e}")
        
        with connect() as conn:
            cursor = conn.execute("UPDATE notifications SET read = 1 WHERE read = 0")
            count = cursor.rowcount
            conn.commit()
        
        logger.info(f"Marked {count} notifications as read")
        return count
    
    def cleanup_expired(self) -> int:
        """Remove expired notifications.
        
        Returns:
            Number of notifications cleaned up
        """
        now = datetime.now().isoformat()
        
        supabase = get_supabase()
        
        if supabase:
            try:
                result = supabase.table("notifications").delete().lt("expires_at", now).execute()
                count = len(result.data) if result.data else 0
                logger.info(f"Cleaned up {count} expired notifications (Supabase)")
                return count
            except Exception as e:
                logger.warning(f"Supabase cleanup failed: {e}")
        
        with connect() as conn:
            cursor = conn.execute("""
                DELETE FROM notifications 
                WHERE expires_at IS NOT NULL AND expires_at < ?
            """, (now,))
            count = cursor.rowcount
            conn.commit()
        
        logger.info(f"Cleaned up {count} expired notifications")
        return count


# =============================================================================
# API FUNCTIONS
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
