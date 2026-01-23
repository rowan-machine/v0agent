# tests/test_notifications_api.py
"""
Tests for F3: Notification API Routes

Tests the /api/v1/notifications endpoints:
- GET /notifications - List notifications
- GET /notifications/unread-count - Badge count
- PATCH /notifications/{id}/read - Mark read
- POST /notifications/{id}/action - Approve/reject/dismiss
- DELETE /notifications/{id} - Delete
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

from fastapi.testclient import TestClient


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_notification():
    """Create a mock notification object."""
    from src.app.services.notification_queue import (
        Notification,
        NotificationType,
        NotificationPriority,
    )
    return Notification(
        id="test-notification-123",
        notification_type=NotificationType.ACTION_DUE,
        title="Action Due Today",
        body="Review PR by end of day",
        data={"meeting_id": 1, "action_text": "Review PR"},
        priority=NotificationPriority.HIGH,
        created_at=datetime.now(),
        read=False,
        actioned=False,
        expires_at=datetime.now() + timedelta(days=7),
    )


@pytest.fixture
def mock_queue(mock_notification):
    """Create a mock NotificationQueue."""
    queue = MagicMock()
    queue.get_pending.return_value = [mock_notification]
    queue.get_unread_count.return_value = 3
    queue.get_by_id.return_value = mock_notification
    queue.mark_read.return_value = None
    queue.approve.return_value = True
    queue.reject.return_value = True
    queue.dismiss.return_value = True
    queue.delete.return_value = True
    queue.mark_all_read.return_value = 5
    return queue


@pytest.fixture
def client(mock_queue):
    """Create test client with mocked queue."""
    from fastapi import FastAPI
    from src.app.api.v1.notifications import router, get_queue
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/notifications")
    
    # Override the queue dependency
    with patch('src.app.api.v1.notifications.get_queue', return_value=mock_queue):
        yield TestClient(app)


# =============================================================================
# LIST NOTIFICATIONS TESTS
# =============================================================================

class TestListNotifications:
    """Tests for GET /notifications endpoint."""
    
    def test_list_notifications_returns_list(self, client, mock_queue):
        """Should return list of notifications."""
        response = client.get("/api/v1/notifications")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "test-notification-123"
    
    def test_list_notifications_with_type_filter(self, client, mock_queue):
        """Should filter by notification type."""
        response = client.get("/api/v1/notifications?type=action_due")
        
        assert response.status_code == 200
        mock_queue.get_pending.assert_called()
    
    def test_list_notifications_invalid_type(self, client, mock_queue):
        """Should return 400 for invalid type."""
        response = client.get("/api/v1/notifications?type=invalid_type")
        
        assert response.status_code == 400
        assert "Invalid notification type" in response.json()["detail"]
    
    def test_list_notifications_with_limit(self, client, mock_queue):
        """Should respect limit parameter."""
        response = client.get("/api/v1/notifications?limit=5")
        
        assert response.status_code == 200
        mock_queue.get_pending.assert_called_with(notification_type=None, limit=5)
    
    def test_list_notifications_unread_only(self, client, mock_queue, mock_notification):
        """Should filter unread only when requested."""
        # Add a read notification
        mock_notification.read = False
        mock_queue.get_pending.return_value = [mock_notification]
        
        response = client.get("/api/v1/notifications?unread_only=true")
        
        assert response.status_code == 200


# =============================================================================
# UNREAD COUNT TESTS
# =============================================================================

class TestUnreadCount:
    """Tests for GET /notifications/unread-count endpoint."""
    
    def test_unread_count_returns_count(self, client, mock_queue):
        """Should return unread count."""
        response = client.get("/api/v1/notifications/unread-count")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
    
    def test_unread_count_zero(self, client, mock_queue):
        """Should return zero when no unread."""
        mock_queue.get_unread_count.return_value = 0
        
        response = client.get("/api/v1/notifications/unread-count")
        
        assert response.status_code == 200
        assert response.json()["count"] == 0


# =============================================================================
# GET SINGLE NOTIFICATION TESTS
# =============================================================================

class TestGetNotification:
    """Tests for GET /notifications/{id} endpoint."""
    
    def test_get_notification_exists(self, client, mock_queue):
        """Should return notification by ID."""
        response = client.get("/api/v1/notifications/test-notification-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-notification-123"
        assert data["title"] == "Action Due Today"
    
    def test_get_notification_not_found(self, client, mock_queue):
        """Should return 404 for missing notification."""
        mock_queue.get_by_id.return_value = None
        
        response = client.get("/api/v1/notifications/nonexistent-id")
        
        assert response.status_code == 404


# =============================================================================
# MARK READ TESTS
# =============================================================================

class TestMarkRead:
    """Tests for PATCH /notifications/{id}/read endpoint."""
    
    def test_mark_read_success(self, client, mock_queue, mock_notification):
        """Should mark notification as read."""
        mock_notification.read = True
        mock_queue.get_by_id.return_value = mock_notification
        
        response = client.patch("/api/v1/notifications/test-notification-123/read")
        
        assert response.status_code == 200
        mock_queue.mark_read.assert_called_with("test-notification-123")
    
    def test_mark_read_not_found(self, client, mock_queue):
        """Should return 404 for missing notification."""
        mock_queue.get_by_id.return_value = None
        
        response = client.patch("/api/v1/notifications/nonexistent-id/read")
        
        assert response.status_code == 404


# =============================================================================
# ACTION TESTS
# =============================================================================

class TestTakeAction:
    """Tests for POST /notifications/{id}/action endpoint."""
    
    def test_approve_action(self, client, mock_queue):
        """Should approve notification."""
        response = client.post(
            "/api/v1/notifications/test-notification-123/action",
            json={"action": "approve", "feedback": "Good signal"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "approve"
        mock_queue.approve.assert_called_with("test-notification-123", feedback="Good signal")
    
    def test_reject_action(self, client, mock_queue):
        """Should reject notification with reason."""
        response = client.post(
            "/api/v1/notifications/test-notification-123/action",
            json={"action": "reject", "feedback": "Too vague"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "reject"
        mock_queue.reject.assert_called_with("test-notification-123", reason="Too vague")
    
    def test_dismiss_action(self, client, mock_queue):
        """Should dismiss notification."""
        response = client.post(
            "/api/v1/notifications/test-notification-123/action",
            json={"action": "dismiss"}
        )
        
        assert response.status_code == 200
        mock_queue.dismiss.assert_called_with("test-notification-123")
    
    def test_invalid_action(self, client, mock_queue):
        """Should return 400 for invalid action."""
        response = client.post(
            "/api/v1/notifications/test-notification-123/action",
            json={"action": "invalid_action"}
        )
        
        assert response.status_code == 400
        assert "Invalid action" in response.json()["detail"]
    
    def test_action_not_found(self, client, mock_queue):
        """Should return 404 for missing notification."""
        mock_queue.get_by_id.return_value = None
        
        response = client.post(
            "/api/v1/notifications/nonexistent-id/action",
            json={"action": "approve"}
        )
        
        assert response.status_code == 404


# =============================================================================
# DELETE TESTS
# =============================================================================

class TestDeleteNotification:
    """Tests for DELETE /notifications/{id} endpoint."""
    
    def test_delete_success(self, client, mock_queue):
        """Should delete notification."""
        response = client.delete("/api/v1/notifications/test-notification-123")
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_queue.delete.assert_called_with("test-notification-123")
    
    def test_delete_not_found(self, client, mock_queue):
        """Should return 404 for missing notification."""
        mock_queue.get_by_id.return_value = None
        
        response = client.delete("/api/v1/notifications/nonexistent-id")
        
        assert response.status_code == 404


# =============================================================================
# MARK ALL READ TESTS
# =============================================================================

class TestMarkAllRead:
    """Tests for POST /notifications/mark-all-read endpoint."""
    
    def test_mark_all_read_success(self, client, mock_queue):
        """Should mark all notifications as read."""
        response = client.post("/api/v1/notifications/mark-all-read")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["marked_read"] == 5
        mock_queue.mark_all_read.assert_called_once()


# =============================================================================
# NOTIFICATION TYPES TESTS
# =============================================================================

class TestListTypes:
    """Tests for GET /notifications/types/list endpoint."""
    
    def test_list_types_returns_all(self, client, mock_queue):
        """Should return all notification types."""
        response = client.get("/api/v1/notifications/types/list")
        
        assert response.status_code == 200
        data = response.json()
        assert "types" in data
        assert len(data["types"]) > 0
        
        # Check structure
        first_type = data["types"][0]
        assert "value" in first_type
        assert "name" in first_type
        assert "description" in first_type


# =============================================================================
# RESPONSE FORMAT TESTS
# =============================================================================

class TestResponseFormat:
    """Tests for response format consistency."""
    
    def test_notification_response_has_all_fields(self, client, mock_queue):
        """Should include all required fields in response."""
        response = client.get("/api/v1/notifications")
        
        assert response.status_code == 200
        notification = response.json()[0]
        
        required_fields = [
            "id", "type", "title", "body", "data",
            "priority", "read", "actioned", "created_at"
        ]
        
        for field in required_fields:
            assert field in notification, f"Missing field: {field}"
    
    def test_notification_data_is_dict(self, client, mock_queue):
        """Should return data as dict, not string."""
        response = client.get("/api/v1/notifications")
        
        data = response.json()[0]["data"]
        assert isinstance(data, dict)
