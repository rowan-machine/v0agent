# tests/unit/test_sdk_client.py
"""
Unit tests for SignalFlow SDK client.

Tests the SDK client functionality for external integrations.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json


class TestSignalFlowClient:
    """Tests for the main SignalFlow SDK client."""
    
    def test_client_initialization_with_environment(self):
        """Client should initialize with environment."""
        from sdk.signalflow.client import SignalFlowClient
        
        with patch("sdk.signalflow.client.httpx.Client") as mock_http:
            client = SignalFlowClient(environment="local")
            
            assert client._env.name == "local"
            assert "localhost" in client._env.api_url
    
    def test_client_initialization_with_custom_url(self):
        """Client should accept custom API URL."""
        from sdk.signalflow.client import SignalFlowClient
        
        with patch("sdk.signalflow.client.httpx.Client") as mock_http:
            client = SignalFlowClient(api_url="http://custom:8000")
            
            assert client._env.api_url == "http://custom:8000"
    
    def test_client_has_sub_clients(self):
        """Client should have meetings, signals, tickets, knowledge clients."""
        from sdk.signalflow.client import SignalFlowClient
        
        with patch("sdk.signalflow.client.httpx.Client") as mock_http:
            client = SignalFlowClient(environment="local")
            
            assert hasattr(client, 'meetings')
            assert hasattr(client, 'signals')
            assert hasattr(client, 'tickets')
            assert hasattr(client, 'knowledge')
            assert hasattr(client, 'career')
    
    def test_client_context_manager(self):
        """Client should work as context manager."""
        from sdk.signalflow.client import SignalFlowClient
        
        with patch("sdk.signalflow.client.httpx.Client") as mock_http:
            with SignalFlowClient(environment="local") as client:
                assert client is not None


class TestMeetingsClient:
    """Tests for the Meetings sub-client."""
    
    def test_list_meetings(self):
        """Should list meetings with pagination."""
        from sdk.signalflow.client import MeetingsClient
        
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "meetings": [
                {"id": "1", "meeting_name": "Standup", "meeting_date": "2024-01-15"}
            ],
            "count": 1
        }
        mock_http.get.return_value = mock_response
        
        client = MeetingsClient(mock_http)
        result = client.list(limit=10, offset=0)
        
        assert result.count == 1
        assert len(result.meetings) == 1
        assert result.meetings[0].meeting_name == "Standup"
    
    def test_get_meeting(self):
        """Should get single meeting by ID."""
        from sdk.signalflow.client import MeetingsClient
        
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "1",
            "meeting_name": "Sprint Planning",
            "meeting_date": "2024-01-15"
        }
        mock_http.get.return_value = mock_response
        
        client = MeetingsClient(mock_http)
        meeting = client.get("1")
        
        assert meeting is not None
        assert meeting.meeting_name == "Sprint Planning"
    
    def test_get_meeting_not_found(self):
        """Should return None for missing meeting."""
        from sdk.signalflow.client import MeetingsClient
        
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http.get.return_value = mock_response
        
        client = MeetingsClient(mock_http)
        meeting = client.get("999")
        
        assert meeting is None


class TestSignalsClient:
    """Tests for the Signals sub-client."""
    
    def test_search_signals(self):
        """Should search signals with query."""
        from sdk.signalflow.client import SignalsClient
        from sdk.signalflow.models import SignalType
        
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "signals": [
                {"id": 1, "meeting_id": "1", "signal_type": "decision", "content": "Use Python", "confidence": 0.8}
            ],
            "count": 1
        }
        mock_http.get.return_value = mock_response
        
        client = SignalsClient(mock_http)
        result = client.search("Python", signal_type=SignalType.DECISION)
        
        assert result.count == 1
        assert len(result.signals) == 1


class TestKnowledgeClient:
    """Tests for the Knowledge sub-client."""
    
    def test_get_pyramid(self):
        """Should get DIKW pyramid stats."""
        from sdk.signalflow.client import KnowledgeClient
        
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "pyramid": {
                "data": [{"id": 1, "level": "data", "content": "raw data", "confidence": 0.5}],
                "information": [{"id": 2, "level": "information", "content": "insight", "confidence": 0.7}],
                "knowledge": [{"id": 3, "level": "knowledge", "content": "pattern", "confidence": 0.85}],
                "wisdom": []
            },
            "counts": {"data": 1, "information": 1, "knowledge": 1, "wisdom": 0}
        }
        mock_http.get.return_value = mock_response
        
        client = KnowledgeClient(mock_http)
        result = client.get_pyramid()
        
        assert len(result.pyramid["knowledge"]) == 1
    
    def test_search_knowledge(self):
        """Should search knowledge items."""
        from sdk.signalflow.client import KnowledgeClient
        from sdk.signalflow.models import DIKWLevel
        
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"id": 1, "level": "knowledge", "content": "Python best practices"}
            ],
            "count": 1
        }
        mock_http.get.return_value = mock_response
        
        client = KnowledgeClient(mock_http)
        result = client.search("Python", level=DIKWLevel.KNOWLEDGE)
        
        assert result.count == 1


class TestSDKModels:
    """Tests for SDK data models."""
    
    def test_meeting_model(self):
        """Meeting model should have expected fields."""
        from sdk.signalflow.models import Meeting
        
        meeting = Meeting(
            id="mtg-1",
            meeting_name="Test Meeting",
            meeting_date="2024-01-15"
        )
        
        assert meeting.id == "mtg-1"
        assert meeting.meeting_name == "Test Meeting"
    
    def test_signal_model(self):
        """Signal model should have expected fields."""
        from sdk.signalflow.models import Signal, SignalType
        
        signal = Signal(
            id=1,
            meeting_id="mtg-1",
            signal_type=SignalType.DECISION,
            content="Decided to use Python",
            confidence=0.85
        )
        
        assert signal.signal_type == SignalType.DECISION
        assert signal.confidence == 0.85
    
    def test_ticket_model(self):
        """Ticket model should have expected fields."""
        from sdk.signalflow.models import Ticket, TicketStatus, TicketPriority
        
        ticket = Ticket(
            id=1,
            ticket_id="TEST-001",
            title="Test Ticket",
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.HIGH
        )
        
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert ticket.priority == TicketPriority.HIGH
    
    def test_dikw_level_enum(self):
        """DIKW level enum should have all values."""
        from sdk.signalflow.models import DIKWLevel
        
        assert DIKWLevel.DATA.value == "data"
        assert DIKWLevel.INFORMATION.value == "information"
        assert DIKWLevel.KNOWLEDGE.value == "knowledge"
        assert DIKWLevel.WISDOM.value == "wisdom"
