# sdk/signalflow/tests/test_async_client.py
"""
Unit tests for SignalFlow SDK async client.

Uses pytest-asyncio and respx for async HTTP mocking.
"""

import pytest
import httpx

# Try to import respx for async mocking
try:
    import respx
    RESPX_AVAILABLE = True
except ImportError:
    RESPX_AVAILABLE = False

from signalflow import AsyncSignalFlowClient


# Skip all tests if respx is not available
pytestmark = pytest.mark.skipif(
    not RESPX_AVAILABLE,
    reason="respx library required for async tests"
)


# -------------------------
# Fixtures
# -------------------------

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
# Async Meetings Client Tests
# -------------------------

@pytest.mark.asyncio
class TestAsyncMeetingsClient:
    """Tests for async MeetingsClient."""

    @respx.mock
    async def test_list_meetings(self, mock_meeting):
        """Test listing meetings asynchronously."""
        respx.get("http://localhost:8000/api/v1/meetings").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [mock_meeting],
                    "total": 1,
                    "skip": 0,
                    "limit": 20,
                }
            )
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000",
            api_key="test-api-key"
        ) as client:
            result = await client.meetings.list()
        
        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "Sprint Planning"

    @respx.mock
    async def test_get_meeting(self, mock_meeting):
        """Test getting a single meeting."""
        respx.get("http://localhost:8000/api/v1/meetings/1").mock(
            return_value=httpx.Response(200, json=mock_meeting)
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000",
            api_key="test-api-key"
        ) as client:
            result = await client.meetings.get(1)
        
        assert result["id"] == 1
        assert result["title"] == "Sprint Planning"

    @respx.mock
    async def test_create_meeting(self, mock_meeting):
        """Test creating a meeting."""
        respx.post("http://localhost:8000/api/v1/meetings").mock(
            return_value=httpx.Response(201, json=mock_meeting)
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            result = await client.meetings.create(
                title="Sprint Planning",
                content="Discussed sprint goals and capacity planning."
            )
        
        assert result["title"] == "Sprint Planning"

    @respx.mock
    async def test_update_meeting(self, mock_meeting):
        """Test updating a meeting."""
        updated = {**mock_meeting, "title": "Updated Sprint Planning"}
        respx.put("http://localhost:8000/api/v1/meetings/1").mock(
            return_value=httpx.Response(200, json=updated)
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            result = await client.meetings.update(1, title="Updated Sprint Planning")
        
        assert result["title"] == "Updated Sprint Planning"

    @respx.mock
    async def test_delete_meeting(self):
        """Test deleting a meeting."""
        respx.delete("http://localhost:8000/api/v1/meetings/1").mock(
            return_value=httpx.Response(200, json={"deleted": True})
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            result = await client.meetings.delete(1)
        
        assert result["deleted"] is True


# -------------------------
# Async Signals Client Tests
# -------------------------

@pytest.mark.asyncio
class TestAsyncSignalsClient:
    """Tests for async SignalsClient."""

    @respx.mock
    async def test_list_signals(self, mock_signal):
        """Test listing signals."""
        respx.get("http://localhost:8000/api/v1/signals").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [mock_signal],
                    "total": 1,
                }
            )
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            result = await client.signals.list()
        
        assert len(result["items"]) == 1
        assert result["items"][0]["signal_type"] == "action_item"

    @respx.mock
    async def test_signals_for_meeting(self, mock_signal):
        """Test getting signals for a meeting."""
        respx.get("http://localhost:8000/api/v1/meetings/1/signals").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [mock_signal],
                    "total": 1,
                }
            )
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            result = await client.signals.for_meeting(1)
        
        assert len(result["items"]) == 1


# -------------------------
# Async Tickets Client Tests
# -------------------------

@pytest.mark.asyncio
class TestAsyncTicketsClient:
    """Tests for async TicketsClient."""

    @respx.mock
    async def test_list_tickets(self, mock_ticket):
        """Test listing tickets."""
        respx.get("http://localhost:8000/api/v1/tickets").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [mock_ticket],
                    "total": 1,
                }
            )
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            result = await client.tickets.list()
        
        assert len(result["items"]) == 1

    @respx.mock
    async def test_create_ticket(self, mock_ticket):
        """Test creating a ticket."""
        respx.post("http://localhost:8000/api/v1/tickets").mock(
            return_value=httpx.Response(201, json=mock_ticket)
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            result = await client.tickets.create(
                title="Implement OAuth",
                description="Add OAuth2 flow",
                priority="high"
            )
        
        assert result["title"] == "Implement OAuth"


# -------------------------
# Async Error Handling Tests
# -------------------------

@pytest.mark.asyncio
class TestAsyncErrorHandling:
    """Tests for async error handling."""

    @respx.mock
    async def test_404_error(self):
        """Test handling 404 errors."""
        respx.get("http://localhost:8000/api/v1/meetings/999").mock(
            return_value=httpx.Response(
                404,
                json={"error": "Meeting not found"}
            )
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.meetings.get(999)
            
            assert exc_info.value.response.status_code == 404

    @respx.mock
    async def test_500_error(self):
        """Test handling 500 errors."""
        respx.get("http://localhost:8000/api/v1/meetings").mock(
            return_value=httpx.Response(
                500,
                json={"error": "Internal server error"}
            )
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.meetings.list()
            
            assert exc_info.value.response.status_code == 500


# -------------------------
# Async Context Manager Tests
# -------------------------

@pytest.mark.asyncio
class TestAsyncContextManager:
    """Tests for async context manager behavior."""

    @respx.mock
    async def test_context_manager_cleanup(self):
        """Test that resources are cleaned up properly."""
        respx.get("http://localhost:8000/api/v1/meetings").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )

        client = AsyncSignalFlowClient(base_url="http://localhost:8000")
        
        async with client:
            await client.meetings.list()
        
        # Client should be closed after context exit
        assert client._client.is_closed

    @respx.mock
    async def test_multiple_requests_same_session(self):
        """Test multiple requests reuse the same session."""
        respx.get("http://localhost:8000/api/v1/meetings").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        respx.get("http://localhost:8000/api/v1/signals").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        respx.get("http://localhost:8000/api/v1/tickets").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            await client.meetings.list()
            await client.signals.list()
            await client.tickets.list()
        
        # All requests should have been made
        assert len(respx.calls) == 3


# -------------------------
# Async Concurrent Requests Tests
# -------------------------

@pytest.mark.asyncio
class TestAsyncConcurrency:
    """Tests for concurrent request handling."""

    @respx.mock
    async def test_concurrent_requests(self, mock_meeting, mock_signal, mock_ticket):
        """Test making concurrent requests."""
        import asyncio
        
        respx.get("http://localhost:8000/api/v1/meetings").mock(
            return_value=httpx.Response(
                200,
                json={"items": [mock_meeting], "total": 1}
            )
        )
        respx.get("http://localhost:8000/api/v1/signals").mock(
            return_value=httpx.Response(
                200,
                json={"items": [mock_signal], "total": 1}
            )
        )
        respx.get("http://localhost:8000/api/v1/tickets").mock(
            return_value=httpx.Response(
                200,
                json={"items": [mock_ticket], "total": 1}
            )
        )

        async with AsyncSignalFlowClient(
            base_url="http://localhost:8000"
        ) as client:
            # Make concurrent requests
            results = await asyncio.gather(
                client.meetings.list(),
                client.signals.list(),
                client.tickets.list(),
            )
        
        meetings, signals, tickets = results
        
        assert len(meetings["items"]) == 1
        assert len(signals["items"]) == 1
        assert len(tickets["items"]) == 1
