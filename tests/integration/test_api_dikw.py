# tests/integration/test_api_dikw.py
"""
Integration tests for DIKW API endpoints.

Tests the API v1 DIKW endpoints with database operations.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    with patch("src.app.api.v1.dikw.get_supabase_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


class TestDIKWListEndpoint:
    """Tests for GET /api/v1/dikw endpoint."""
    
    def test_list_dikw_items_empty(self, client, mock_supabase):
        """Should return empty list when no items exist."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = []
        
        response = client.get("/api/v1/dikw")
        
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
    
    def test_list_dikw_items_with_data(self, client, mock_supabase):
        """Should return DIKW items from database."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = [
            {"id": 1, "level": "information", "content": "Test insight", "confidence": 0.8},
            {"id": 2, "level": "knowledge", "content": "Another insight", "confidence": 0.9}
        ]
        
        response = client.get("/api/v1/dikw")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
    
    def test_list_dikw_filter_by_level(self, client, mock_supabase):
        """Should filter items by DIKW level."""
        mock_result = MagicMock()
        mock_result.data = [
            {"id": 1, "level": "knowledge", "content": "Knowledge item", "confidence": 0.85}
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        
        response = client.get("/api/v1/dikw?level=knowledge")
        
        assert response.status_code == 200


class TestDIKWCreateEndpoint:
    """Tests for POST /api/v1/dikw endpoint."""
    
    def test_create_dikw_item(self, client, mock_supabase):
        """Should create new DIKW item."""
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": 1, "level": "information", "content": "New insight", "confidence": 0.75}
        ]
        
        response = client.post("/api/v1/dikw", json={
            "level": "information",
            "content": "New insight from meeting",
            "confidence": 0.75,
            "source_type": "meeting"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
    
    def test_create_dikw_validation_error(self, client):
        """Should reject invalid DIKW level."""
        response = client.post("/api/v1/dikw", json={
            "level": "invalid_level",
            "content": "Test"
        })
        
        assert response.status_code == 422  # Validation error


class TestDIKWPromoteEndpoint:
    """Tests for POST /api/v1/dikw/{id}/promote endpoint."""
    
    def test_promote_dikw_item(self, client, mock_supabase):
        """Should promote item to next DIKW level."""
        # Mock getting current item
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": 1, "level": "information", "content": "Test", "confidence": 0.85
        }
        
        # Mock update
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {"id": 1, "level": "knowledge", "content": "Test", "confidence": 0.85}
        ]
        
        response = client.post("/api/v1/dikw/1/promote")
        
        assert response.status_code == 200
    
    def test_promote_wisdom_fails(self, client, mock_supabase):
        """Should not promote wisdom level items."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": 1, "level": "wisdom", "content": "Peak insight", "confidence": 0.95
        }
        
        response = client.post("/api/v1/dikw/1/promote")
        
        assert response.status_code == 400  # Cannot promote wisdom


class TestDIKWSynthesizeEndpoint:
    """Tests for POST /api/v1/dikw/synthesize endpoint."""
    
    def test_synthesize_dikw_from_signals(self, client, mock_supabase):
        """Should synthesize DIKW items from meeting signals."""
        # Mock signals retrieval
        mock_supabase.table.return_value.select.return_value.gte.return_value.execute.return_value.data = [
            {"id": 1, "signal_text": "Decision to use Python", "signal_type": "decision", "confidence": 0.8},
            {"id": 2, "signal_text": "Risk: timeline is tight", "signal_type": "risk", "confidence": 0.7}
        ]
        
        response = client.post("/api/v1/dikw/synthesize", json={
            "source": "signals",
            "days_back": 7
        })
        
        assert response.status_code in [200, 201, 202]  # Async processing


class TestDIKWStatsEndpoint:
    """Tests for GET /api/v1/dikw/stats endpoint."""
    
    def test_get_dikw_stats(self, client, mock_supabase):
        """Should return DIKW statistics."""
        mock_supabase.rpc.return_value.execute.return_value.data = {
            "data_count": 10,
            "information_count": 25,
            "knowledge_count": 8,
            "wisdom_count": 2,
            "avg_confidence": 0.78
        }
        
        response = client.get("/api/v1/dikw/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "data_count" in data or "stats" in data
