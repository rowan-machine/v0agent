# src/app/repositories/notifications_repository.py
"""
Notifications Repository - Data Access for User Notifications

Handles persistence for:
- User notifications (alerts, reminders, coach recommendations)
- Read/unread status tracking
- Action status (actioned/dismissed)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


@dataclass
class NotificationEntity:
    """Notification data entity."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    notification_type: str = "ai_suggestion"
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: str = "normal"
    created_at: Optional[datetime] = None
    read: bool = False
    read_at: Optional[datetime] = None
    actioned: bool = False
    actioned_at: Optional[datetime] = None
    action_taken: Optional[str] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "type": self.notification_type,
            "title": self.title,
            "message": self.body,
            "body": self.body,
            "data": self.data,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read": self.read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "actioned": self.actioned,
            "actioned_at": self.actioned_at.isoformat() if self.actioned_at else None,
            "action_taken": self.action_taken,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class NotificationsRepository(ABC):
    """
    Abstract interface (Port) for notification data access.
    """

    # --- Create ---

    @abstractmethod
    def insert(self, notification: NotificationEntity) -> str:
        """
        Insert a new notification.
        
        Args:
            notification: The notification entity to insert
            
        Returns:
            The ID of the created notification
        """
        pass

    # --- Read ---

    @abstractmethod
    def get_by_id(self, notification_id: str) -> Optional[NotificationEntity]:
        """
        Get a notification by ID.
        
        Args:
            notification_id: The notification ID
            
        Returns:
            The notification entity or None if not found
        """
        pass

    @abstractmethod
    def get_unactioned(
        self,
        notification_type: Optional[str] = None,
        limit: int = 20
    ) -> List[NotificationEntity]:
        """
        Get unactioned notifications (not dismissed/approved/rejected).
        
        Args:
            notification_type: Optional filter by type
            limit: Maximum number of results
            
        Returns:
            List of notification entities
        """
        pass

    @abstractmethod
    def get_unread_count(self) -> int:
        """
        Get count of unread notifications.
        
        Returns:
            Number of unread notifications
        """
        pass

    @abstractmethod
    def get_total_unactioned_count(self) -> int:
        """
        Get count of total unactioned notifications.
        
        Returns:
            Number of unactioned notifications
        """
        pass

    # --- Update ---

    @abstractmethod
    def mark_read(self, notification_id: str) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: The notification ID
            
        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def mark_all_read(self) -> int:
        """
        Mark all unread notifications as read.
        
        Returns:
            Number of notifications marked as read
        """
        pass

    @abstractmethod
    def mark_actioned(
        self,
        notification_id: str,
        action: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Mark a notification as actioned (approved/rejected/dismissed).
        
        Args:
            notification_id: The notification ID
            action: The action taken (approved, rejected, dismissed)
            notes: Optional notes about the action
            
        Returns:
            True if successful
        """
        pass

    # --- Delete ---

    @abstractmethod
    def delete(self, notification_id: str) -> bool:
        """
        Delete a notification.
        
        Args:
            notification_id: The notification ID
            
        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    def delete_expired(self) -> int:
        """
        Delete expired notifications.
        
        Returns:
            Number of notifications deleted
        """
        pass


class SupabaseNotificationsRepository(NotificationsRepository):
    """
    Supabase implementation of NotificationsRepository.
    """

    def __init__(self, client):
        """
        Initialize with Supabase client.
        
        Args:
            client: Supabase client instance
        """
        self._client = client

    def _parse_notification(self, row: Dict[str, Any]) -> NotificationEntity:
        """Parse a database row into a NotificationEntity."""
        data_field = row.get("data") or row.get("metadata") or "{}"
        if isinstance(data_field, str):
            try:
                data_field = json.loads(data_field)
            except json.JSONDecodeError:
                data_field = {}

        def parse_datetime(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(str(val).replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return None

        return NotificationEntity(
            id=str(row.get("id", uuid.uuid4())),
            notification_type=row.get("type") or row.get("notification_type") or "ai_suggestion",
            title=row.get("title", ""),
            body=row.get("body") or row.get("message") or "",
            data=data_field,
            priority=row.get("priority", "normal"),
            created_at=parse_datetime(row.get("created_at")),
            read=row.get("read_at") is not None or bool(row.get("read", False)),
            read_at=parse_datetime(row.get("read_at")),
            actioned=row.get("actioned_at") is not None or bool(row.get("actioned", False)),
            actioned_at=parse_datetime(row.get("actioned_at")),
            action_taken=row.get("action_taken"),
            expires_at=parse_datetime(row.get("expires_at")),
        )

    def insert(self, notification: NotificationEntity) -> str:
        """Insert a new notification."""
        data = {
            "id": notification.id,
            "type": notification.notification_type,
            "title": notification.title,
            "body": notification.body,
            "data": json.dumps(notification.data) if notification.data else None,
            "priority": notification.priority,
            "created_at": (notification.created_at or datetime.now()).isoformat(),
            "expires_at": notification.expires_at.isoformat() if notification.expires_at else None,
        }
        
        result = self._client.table("notifications").insert(data).execute()
        
        if result.data:
            return notification.id
        raise RuntimeError("Failed to insert notification")

    def get_by_id(self, notification_id: str) -> Optional[NotificationEntity]:
        """Get a notification by ID."""
        result = self._client.table("notifications").select("*").eq(
            "id", notification_id
        ).execute()
        
        if result.data:
            return self._parse_notification(result.data[0])
        return None

    def get_unactioned(
        self,
        notification_type: Optional[str] = None,
        limit: int = 20
    ) -> List[NotificationEntity]:
        """Get unactioned notifications."""
        query = self._client.table("notifications").select("*").is_(
            "actioned_at", "null"
        )
        
        if notification_type:
            query = query.eq("type", notification_type)
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        return [self._parse_notification(row) for row in (result.data or [])]

    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        result = self._client.table("notifications").select(
            "id", count="exact"
        ).is_("read_at", "null").execute()
        return result.count or 0

    def get_total_unactioned_count(self) -> int:
        """Get count of total unactioned notifications."""
        result = self._client.table("notifications").select(
            "id", count="exact"
        ).is_("actioned_at", "null").execute()
        return result.count or 0

    def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        from datetime import timezone
        self._client.table("notifications").update({
            "read_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", notification_id).execute()
        return True

    def mark_all_read(self) -> int:
        """Mark all unread notifications as read."""
        from datetime import timezone
        result = self._client.table("notifications").update({
            "read_at": datetime.now(timezone.utc).isoformat()
        }).is_("read_at", "null").execute()
        return len(result.data) if result.data else 0

    def mark_actioned(
        self,
        notification_id: str,
        action: str,
        notes: Optional[str] = None
    ) -> bool:
        """Mark a notification as actioned."""
        from datetime import timezone
        data = {
            "actioned_at": datetime.now(timezone.utc).isoformat(),
            "action_taken": action,
        }
        self._client.table("notifications").update(data).eq(
            "id", notification_id
        ).execute()
        return True

    def delete(self, notification_id: str) -> bool:
        """Delete a notification."""
        self._client.table("notifications").delete().eq(
            "id", notification_id
        ).execute()
        return True

    def delete_expired(self) -> int:
        """Delete expired notifications."""
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()
        result = self._client.table("notifications").delete().lt(
            "expires_at", now
        ).execute()
        return len(result.data) if result.data else 0


# --- Factory Function ---

_notifications_repository: Optional[NotificationsRepository] = None


def get_notifications_repository() -> NotificationsRepository:
    """
    Factory function to get the notifications repository instance.
    Uses lazy initialization with Supabase.
    
    Returns:
        NotificationsRepository instance
    """
    global _notifications_repository
    
    if _notifications_repository is None:
        from ..infrastructure.supabase_client import get_supabase_client
        client = get_supabase_client()
        if client:
            _notifications_repository = SupabaseNotificationsRepository(client)
        else:
            raise RuntimeError("Supabase client not available for NotificationsRepository")
    
    return _notifications_repository


def reset_notifications_repository():
    """Reset the singleton for testing purposes."""
    global _notifications_repository
    _notifications_repository = None
