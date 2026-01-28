# sdk/signalflow/tests/test_client.py
"""
Unit tests for SignalFlow SDK sync client.

Uses responses library to mock HTTP requests.
"""

import pytest
import responses
from datetime import datetime

from signalflow import SignalFlowClient
from signalflow.models import (
    Meeting,
    Signal,
    SignalType,
    Ticket,
    TicketStatus,
    TicketPriority,
    DIKWItem,
    DIKWLevel,
)


# -------------------------
# Fixtures
# -------------------------

@pytest.fixture
def client():
    """Create a test client."""
    return SignalFlowClient(
        base_url="http://localhost:8000",
        api_key="test-api-key"
    )


@pytest.fixture
def mock_meeting():
    """Sample meeting data."""
    return {
        "id": 1,
        "title": "Sprint Planning",
        "content": "Discussed sprint goals and capacity planning.",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:30:00Z",
        "signals": [],
        "tags": ["planning", "sprint"],
    }


@pytest.fixture
def mock_signal():
    """Sample signal data."""
    return {
        "id": 1,
        "meeting_id": 1,
        "signal_type": "action_item",
        "content": "Create API documentation",
        "status": "active",
        "priority": 1,
        "assignee": "John",
        "created_at": "2024-01-15T10:15:00Z",
    }


@pytest.fixture
def mock_ticket():
    """Sample ticket data."""
    return {
        "id": 1,
        "title": "Implement OAuth",
        "description": "Add OAuth2 authentication flow",
        "status": "in_progress",
        "priority": "high",
        "assignee": "Jane",
        "sprint_id": 5,
        "created_at": "2024-01-10T09:00:00Z",
        "updated_at": "2024-01-15T11:00:00Z",
    }


# -------------------------
# Meetings Client Tests
# -------------------------

class TestMeetingsClient:
    """Tests for MeetingsClient."""

    @responses.activate
    def test_list_meetings(self, client, mock_meeting):
        """Test listing meetings."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings",
            json={
                "items": [mock_meeting],
                "total": 1,
                "skip": 0,
                "limit": 20,
            },
            status=200,
        )

        result = client.meetings.list()
        
        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "Sprint Planning"
        assert result["total"] == 1

    @responses.activate
    def test_get_meeting(self, client, mock_meeting):
        """Test getting a single meeting."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings/1",
            json=mock_meeting,
            status=200,
        )

        result = client.meetings.get(1)
        
        assert result["id"] == 1
        assert result["title"] == "Sprint Planning"

    @responses.activate
    def test_create_meeting(self, client, mock_meeting):
        """Test creating a meeting."""
        responses.add(
            responses.POST,
            "http://localhost:8000/api/v1/meetings",
            json=mock_meeting,
            status=201,
        )

        result = client.meetings.create(
            title="Sprint Planning",
            content="Discussed sprint goals and capacity planning."
        )
        
        assert result["title"] == "Sprint Planning"

    @responses.activate
    def test_update_meeting(self, client, mock_meeting):
        """Test updating a meeting."""
        updated_meeting = {**mock_meeting, "title": "Updated Sprint Planning"}
        responses.add(
            responses.PUT,
            "http://localhost:8000/api/v1/meetings/1",
            json=updated_meeting,
            status=200,
        )

        result = client.meetings.update(1, title="Updated Sprint Planning")
        
        assert result["title"] == "Updated Sprint Planning"

    @responses.activate
    def test_delete_meeting(self, client):
        """Test deleting a meeting."""
        responses.add(
            responses.DELETE,
            "http://localhost:8000/api/v1/meetings/1",
            json={"deleted": True},
            status=200,
        )

        result = client.meetings.delete(1)
        
        assert result["deleted"] is True

    @responses.activate
    def test_meeting_not_found(self, client):
        """Test 404 handling."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings/999",
            json={"error": "Meeting not found"},
            status=404,
        )

        with pytest.raises(Exception) as exc_info:
            client.meetings.get(999)
        
        assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


# -------------------------
# Signals Client Tests
# -------------------------

class TestSignalsClient:
    """Tests for SignalsClient."""

    @responses.activate
    def test_list_signals(self, client, mock_signal):
        """Test listing signals."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/signals",
            json={
                "items": [mock_signal],
                "total": 1,
                "skip": 0,
                "limit": 20,
            },
            status=200,
        )

        result = client.signals.list()
        
        assert len(result["items"]) == 1
        assert result["items"][0]["signal_type"] == "action_item"

    @responses.activate
    def test_list_signals_by_type(self, client, mock_signal):
        """Test listing signals filtered by type."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/signals",
            json={
                "items": [mock_signal],
                "total": 1,
            },
            status=200,
        )

        result = client.signals.list(signal_type="action_item")
        
        assert len(result["items"]) == 1

    @responses.activate
    def test_signals_for_meeting(self, client, mock_signal):
        """Test getting signals for a specific meeting."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings/1/signals",
            json={
                "items": [mock_signal],
                "total": 1,
            },
            status=200,
        )

        result = client.signals.for_meeting(1)
        
        assert len(result["items"]) == 1
        assert result["items"][0]["meeting_id"] == 1


# -------------------------
# Tickets Client Tests
# -------------------------

class TestTicketsClient:
    """Tests for TicketsClient."""

    @responses.activate
    def test_list_tickets(self, client, mock_ticket):
        """Test listing tickets."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/tickets",
            json={
                "items": [mock_ticket],
                "total": 1,
            },
            status=200,
        )

        result = client.tickets.list()
        
        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "Implement OAuth"

    @responses.activate
    def test_create_ticket(self, client, mock_ticket):
        """Test creating a ticket."""
        responses.add(
            responses.POST,
            "http://localhost:8000/api/v1/tickets",
            json=mock_ticket,
            status=201,
        )

        result = client.tickets.create(
            title="Implement OAuth",
            description="Add OAuth2 authentication flow",
            priority="high"
        )
        
        assert result["title"] == "Implement OAuth"

    @responses.activate
    def test_update_ticket_status(self, client, mock_ticket):
        """Test updating ticket status."""
        updated = {**mock_ticket, "status": "done"}
        responses.add(
            responses.PUT,
            "http://localhost:8000/api/v1/tickets/1",
            json=updated,
            status=200,
        )

        result = client.tickets.update(1, status="done")
        
        assert result["status"] == "done"


# -------------------------
# Knowledge Client Tests
# -------------------------

class TestKnowledgeClient:
    """Tests for KnowledgeClient (DIKW)."""

    @responses.activate
    def test_list_knowledge_items(self, client):
        """Test listing DIKW items."""
        mock_item = {
            "id": 1,
            "level": "knowledge",
            "title": "Best Practices Guide",
            "content": "Documentation standards...",
            "confidence_score": 0.85,
            "created_at": "2024-01-01T00:00:00Z",
        }
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/dikw",
            json={
                "items": [mock_item],
                "total": 1,
            },
            status=200,
        )

        result = client.knowledge.list()
        
        assert len(result["items"]) == 1
        assert result["items"][0]["level"] == "knowledge"

    @responses.activate
    def test_promote_item(self, client):
        """Test promoting a DIKW item."""
        mock_promoted = {
            "id": 1,
            "level": "wisdom",
            "title": "Best Practices Guide",
            "confidence_score": 0.92,
        }
        responses.add(
            responses.POST,
            "http://localhost:8000/api/v1/dikw/1/promote",
            json=mock_promoted,
            status=200,
        )

        result = client.knowledge.promote(1, target_level="wisdom")
        
        assert result["level"] == "wisdom"


# -------------------------
# Career Client Tests
# -------------------------

class TestCareerClient:
    """Tests for CareerClient."""

    @responses.activate
    def test_get_profile(self, client):
        """Test getting career profile."""
        mock_profile = {
            "id": 1,
            "role_current": "Senior Developer",
            "role_target": "Tech Lead",
            "strengths": ["Python", "System Design"],
            "skills": {"python": 4, "leadership": 3},
        }
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/career/profile",
            json=mock_profile,
            status=200,
        )

        result = client.career.get_profile()
        
        assert result["role_current"] == "Senior Developer"

    @responses.activate
    def test_get_suggestions(self, client):
        """Test getting career suggestions."""
        mock_suggestions = [
            {
                "id": 1,
                "type": "stretch",
                "title": "Lead a cross-team project",
                "rationale": "Develop leadership skills",
            }
        ]
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/career/suggestions",
            json={"items": mock_suggestions},
            status=200,
        )

        result = client.career.get_suggestions()
        
        assert len(result["items"]) == 1


# -------------------------
# Error Handling Tests
# -------------------------

class TestErrorHandling:
    """Tests for error handling."""

    @responses.activate
    def test_401_unauthorized(self, client):
        """Test handling of 401 errors."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings",
            json={"error": "Unauthorized"},
            status=401,
        )

        with pytest.raises(Exception) as exc_info:
            client.meetings.list()
        
        assert "401" in str(exc_info.value) or "unauthorized" in str(exc_info.value).lower()

    @responses.activate
    def test_500_server_error(self, client):
        """Test handling of 500 errors."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings",
            json={"error": "Internal server error"},
            status=500,
        )

        with pytest.raises(Exception) as exc_info:
            client.meetings.list()
        
        assert "500" in str(exc_info.value) or "server" in str(exc_info.value).lower()

    @responses.activate
    def test_timeout(self, client):
        """Test handling of timeout errors."""
        import requests.exceptions
        
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings",
            body=requests.exceptions.Timeout("Connection timed out"),
        )

        with pytest.raises(Exception):
            client.meetings.list()


# -------------------------
# Authentication Tests
# -------------------------

class TestAuthentication:
    """Tests for authentication handling."""

    @responses.activate
    def test_api_key_header(self, client):
        """Test that API key is sent in header."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings",
            json={"items": [], "total": 0},
            status=200,
        )

        client.meetings.list()
        
        # Check that the Authorization header was sent
        assert len(responses.calls) == 1
        auth_header = responses.calls[0].request.headers.get("Authorization")
        assert auth_header == "Bearer test-api-key"

    def test_client_without_api_key(self):
        """Test client initialization without API key."""
        client = SignalFlowClient(base_url="http://localhost:8000")
        
        assert client._session.headers.get("Authorization") is None


# -------------------------
# Pagination Tests
# -------------------------

class TestPagination:
    """Tests for pagination handling."""

    @responses.activate
    def test_paginated_list(self, client, mock_meeting):
        """Test paginated list requests."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings",
            json={
                "items": [mock_meeting],
                "total": 100,
                "skip": 0,
                "limit": 20,
                "has_more": True,
            },
            status=200,
        )

        result = client.meetings.list(skip=0, limit=20)
        
        assert result["total"] == 100
        assert result["has_more"] is True

    @responses.activate
    def test_pagination_params(self, client):
        """Test that pagination params are sent correctly."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/meetings",
            json={"items": [], "total": 0},
            status=200,
        )

        client.meetings.list(skip=40, limit=10)
        
        # Check query params
        request = responses.calls[0].request
        assert "skip=40" in request.url
        assert "limit=10" in request.url
