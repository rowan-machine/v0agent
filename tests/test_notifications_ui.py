# tests/test_notifications_ui.py
"""
Tests for Notification UI Components including:
- Notification API endpoints (GET/POST)
- Profile page route
- Notification badge count
- Mark read functionality

These tests validate the notification UI system and profile router page.
"""

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    import sys
    sys.path.insert(0, '/Users/rowan/v0agent/src')
    from app.main import app
    return TestClient(app)


@pytest.fixture
def setup_notifications_table(client):
    """Set up notifications table for testing."""
    import sys
    sys.path.insert(0, '/Users/rowan/v0agent/src')
    from app.db import connect
    
    with connect() as conn:
        # Drop and recreate for clean state
        conn.execute("DROP TABLE IF EXISTS notifications")
        conn.execute("""
            CREATE TABLE notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL DEFAULT 'alert',
                title TEXT NOT NULL,
                message TEXT,
                link TEXT,
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    
    yield
    
    # Cleanup - but don't drop table so other tests can still check it exists
    with connect() as conn:
        conn.execute("DELETE FROM notifications")
        conn.commit()


@pytest.fixture
def sample_notifications(setup_notifications_table):
    """Insert sample notifications for testing."""
    import sys
    sys.path.insert(0, '/Users/rowan/v0agent/src')
    from app.db import connect
    
    with connect() as conn:
        notifications = [
            ('action', 'Action Required', 'Complete PR review', '/pr/123', 0),
            ('alert', 'Sprint Ending', 'Sprint ends in 2 days', '/sprint', 0),
            ('coach', 'Coaching Tip', 'Consider breaking down large tasks', None, 1),
            ('mention', 'You were mentioned', 'John mentioned you in standup', '/meeting/5', 0),
        ]
        for n_type, title, message, link, read in notifications:
            conn.execute(
                """INSERT INTO notifications (type, title, message, link, read)
                   VALUES (?, ?, ?, ?, ?)""",
                (n_type, title, message, link, read)
            )
        conn.commit()
    
    return notifications


# =============================================================================
# PROFILE PAGE TESTS
# =============================================================================

class TestProfilePage:
    """Tests for the profile router page."""
    
    def test_profile_page_loads(self, client):
        """Test profile page renders successfully."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
    
    def test_profile_page_contains_career_link(self, client):
        """Test profile page has career profile link."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'Career Profile' in response.text
        assert 'href="/career"' in response.text
    
    def test_profile_page_contains_settings_link(self, client):
        """Test profile page has settings link."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'App Settings' in response.text
        assert 'href="/settings"' in response.text
    
    def test_profile_page_contains_sign_out(self, client):
        """Test profile page has sign out option."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'Sign Out' in response.text
        assert 'href="/logout"' in response.text
    
    def test_profile_page_contains_notifications_link(self, client):
        """Test profile page has notifications link."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'Notifications' in response.text


# =============================================================================
# NOTIFICATION COUNT API TESTS
# =============================================================================

class TestNotificationCountAPI:
    """Tests for notification count endpoint."""
    
    def test_get_count_empty_table(self, client, setup_notifications_table):
        """Test count returns zero when no notifications."""
        response = client.get('/api/notifications/count')
        assert response.status_code == 200
        data = response.json()
        assert data['unread'] == 0
        assert data['total'] == 0
    
    def test_get_count_with_notifications(self, client, sample_notifications):
        """Test count returns correct unread and total."""
        response = client.get('/api/notifications/count')
        assert response.status_code == 200
        data = response.json()
        # 3 unread (one is marked read), 4 total
        assert data['unread'] == 3
        assert data['total'] == 4
    
    def test_get_count_no_table(self, client):
        """Test count returns zero when table doesn't exist."""
        import sys
        sys.path.insert(0, '/Users/rowan/v0agent/src')
        from app.db import connect
        
        # Drop table if exists
        with connect() as conn:
            conn.execute("DROP TABLE IF EXISTS notifications")
            conn.commit()
        
        response = client.get('/api/notifications/count')
        assert response.status_code == 200
        data = response.json()
        assert data['unread'] == 0


# =============================================================================
# NOTIFICATION LIST API TESTS
# =============================================================================

class TestNotificationListAPI:
    """Tests for notification list endpoint."""
    
    def test_get_notifications_empty(self, client, setup_notifications_table):
        """Test list returns empty when no notifications."""
        response = client.get('/api/notifications')
        assert response.status_code == 200
        data = response.json()
        assert data['notifications'] == []
    
    def test_get_notifications_returns_list(self, client, sample_notifications):
        """Test list returns notifications."""
        response = client.get('/api/notifications')
        assert response.status_code == 200
        data = response.json()
        assert len(data['notifications']) == 4
    
    def test_get_notifications_ordered_by_date(self, client, sample_notifications):
        """Test notifications are ordered newest first."""
        response = client.get('/api/notifications')
        assert response.status_code == 200
        notifications = response.json()['notifications']
        
        # Should be in descending order by created_at
        for i in range(len(notifications) - 1):
            assert notifications[i]['created_at'] >= notifications[i + 1]['created_at']
    
    def test_get_notifications_with_limit(self, client, sample_notifications):
        """Test limit parameter restricts results."""
        response = client.get('/api/notifications?limit=2')
        assert response.status_code == 200
        data = response.json()
        assert len(data['notifications']) == 2
    
    def test_get_notifications_includes_required_fields(self, client, sample_notifications):
        """Test each notification has required fields."""
        response = client.get('/api/notifications')
        assert response.status_code == 200
        notifications = response.json()['notifications']
        
        for notif in notifications:
            assert 'id' in notif
            assert 'type' in notif
            assert 'title' in notif
            assert 'read' in notif
            assert 'created_at' in notif


# =============================================================================
# MARK READ API TESTS
# =============================================================================

class TestMarkReadAPI:
    """Tests for marking notifications as read."""
    
    def test_mark_single_notification_read(self, client, sample_notifications):
        """Test marking a single notification as read."""
        # Get first notification ID
        list_response = client.get('/api/notifications')
        notif_id = list_response.json()['notifications'][0]['id']
        
        # Mark it as read
        response = client.post(f'/api/notifications/{notif_id}/read')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        
        # Verify it's now read
        count_response = client.get('/api/notifications/count')
        # Should be 2 unread now (was 3)
        assert count_response.json()['unread'] == 2
    
    def test_mark_all_notifications_read(self, client, sample_notifications):
        """Test marking all notifications as read."""
        response = client.post('/api/notifications/read-all')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        
        # Verify all are now read
        count_response = client.get('/api/notifications/count')
        assert count_response.json()['unread'] == 0
    
    def test_mark_nonexistent_notification_read(self, client, setup_notifications_table):
        """Test marking nonexistent notification doesn't error."""
        response = client.post('/api/notifications/99999/read')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'


# =============================================================================
# NOTIFICATION BELL UI TESTS (HTML Structure)
# =============================================================================

class TestNotificationBellUI:
    """Tests for notification bell HTML in base template."""
    
    def test_base_template_has_notification_bell(self, client):
        """Test base template includes notification bell."""
        # Use any page that extends base.html
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'notification-bell' in response.text
    
    def test_base_template_has_notification_dropdown(self, client):
        """Test base template includes notification dropdown."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'notification-dropdown' in response.text
    
    def test_base_template_has_notification_badge(self, client):
        """Test base template includes notification badge."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'notification-badge' in response.text
    
    def test_base_template_has_mark_all_read_button(self, client):
        """Test dropdown has mark all read button."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'markAllNotificationsRead' in response.text


# =============================================================================
# NAV DRAWER UI TESTS
# =============================================================================

class TestNavDrawerUI:
    """Tests for nav drawer structure after reorganization."""
    
    def test_drawer_header_has_user_button(self, client):
        """Test drawer header includes user button."""
        response = client.get('/profile')
        assert response.status_code == 200
        assert 'drawer-user-btn' in response.text
    
    def test_user_button_links_to_profile(self, client):
        """Test user button links to profile page."""
        response = client.get('/profile')
        assert response.status_code == 200
        # Check drawer-user-btn links to /profile
        assert 'href="/profile"' in response.text
    
    def test_career_profile_removed_from_nav(self, client):
        """Test career profile link is removed from nav drawer bottom."""
        response = client.get('/profile')
        assert response.status_code == 200
        # The nav drawer should NOT have career profile in bottom section
        # But it should still exist in the profile page content
        html = response.text
        
        # Career profile should exist in profile-nav (the page content)
        assert 'Career Profile' in html
        
        # But the old nav-bottom-section should only have Settings
        # We can check that kebab-menu is removed
        assert 'kebab-menu' not in html
    
    def test_settings_still_in_nav_bottom(self, client):
        """Test settings link remains in nav drawer."""
        response = client.get('/profile')
        assert response.status_code == 200
        # nav-bottom-section should have settings
        assert 'nav-bottom-section' in response.text


# =============================================================================
# NOTIFICATION TYPES TESTS
# =============================================================================

class TestNotificationTypes:
    """Tests for different notification types."""
    
    def test_action_type_notification(self, client, setup_notifications_table):
        """Test action type notification is stored correctly."""
        import sys
        sys.path.insert(0, '/Users/rowan/v0agent/src')
        from app.db import connect
        
        with connect() as conn:
            conn.execute(
                """INSERT INTO notifications (type, title, message)
                   VALUES ('action', 'Review PR', 'PR #123 needs review')"""
            )
            conn.commit()
        
        response = client.get('/api/notifications')
        notifications = response.json()['notifications']
        assert len(notifications) == 1
        assert notifications[0]['type'] == 'action'
    
    def test_alert_type_notification(self, client, setup_notifications_table):
        """Test alert type notification."""
        import sys
        sys.path.insert(0, '/Users/rowan/v0agent/src')
        from app.db import connect
        
        with connect() as conn:
            conn.execute(
                """INSERT INTO notifications (type, title, message)
                   VALUES ('alert', 'Sprint Ending', 'Sprint ends tomorrow')"""
            )
            conn.commit()
        
        response = client.get('/api/notifications')
        notifications = response.json()['notifications']
        assert notifications[0]['type'] == 'alert'
    
    def test_coach_type_notification(self, client, setup_notifications_table):
        """Test coach type notification."""
        import sys
        sys.path.insert(0, '/Users/rowan/v0agent/src')
        from app.db import connect
        
        with connect() as conn:
            conn.execute(
                """INSERT INTO notifications (type, title, message)
                   VALUES ('coach', 'Tip', 'Break down large tasks')"""
            )
            conn.commit()
        
        response = client.get('/api/notifications')
        notifications = response.json()['notifications']
        assert notifications[0]['type'] == 'coach'
