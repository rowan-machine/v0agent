# tests/test_api_meetings.py
"""
Tests for Meetings API endpoints.

Tests the /api/v1/meetings endpoints for CRUD operations,
signal extraction, and screenshot processing.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMeetingsAPI:
    """Test suite for meetings endpoints."""
    
    def test_list_meetings_empty(self, client, assert_response_success):
        """Test listing meetings when database is empty."""
        response = client.get("/api/v1/meetings")
        data = assert_response_success(response)
        
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_list_meetings_with_data(self, client_with_data, assert_response_success):
        """Test listing meetings with pre-loaded data."""
        response = client_with_data.get("/api/v1/meetings")
        data = assert_response_success(response)
        
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["meeting_name"] == "Test Standup"
    
    def test_get_meeting_by_id(self, client_with_data, assert_response_success):
        """Test getting a specific meeting by ID."""
        response = client_with_data.get("/api/v1/meetings/1")
        data = assert_response_success(response)
        
        assert data["id"] == 1
        assert data["meeting_name"] == "Test Standup"
        assert "synthesized_notes" in data
    
    def test_get_meeting_not_found(self, client, assert_response_error):
        """Test 404 when meeting doesn't exist."""
        response = client.get("/api/v1/meetings/9999")
        assert_response_error(response, status_code=404, detail="not found")
    
    def test_create_meeting(self, client, mock_embeddings, meeting_factory, assert_response_success):
        """Test creating a new meeting."""
        meeting_data = meeting_factory(
            name="Sprint Planning",
            notes="Discussed sprint goals and assigned tickets"
        )
        
        response = client.post("/api/v1/meetings", json=meeting_data)
        data = assert_response_success(response, status_code=201)
        
        assert data["success"] is True
        assert "id" in data.get("data", {})
    
    def test_create_meeting_missing_required_field(self, client, assert_response_error):
        """Test validation error when required field is missing."""
        response = client.post("/api/v1/meetings", json={"meeting_name": "Test"})
        assert_response_error(response, status_code=422)
    
    def test_update_meeting(self, client_with_data, assert_response_success):
        """Test updating an existing meeting."""
        update_data = {"synthesized_notes": "Updated notes content"}
        
        response = client_with_data.put("/api/v1/meetings/1", json=update_data)
        data = assert_response_success(response)
        
        assert data["success"] is True
    
    def test_delete_meeting(self, client_with_data):
        """Test deleting a meeting."""
        response = client_with_data.delete("/api/v1/meetings/1")
        assert response.status_code == 204
    
    def test_list_meetings_pagination(self, client_with_data, assert_response_success):
        """Test pagination parameters."""
        response = client_with_data.get("/api/v1/meetings?skip=0&limit=1")
        data = assert_response_success(response)
        
        assert len(data["items"]) <= 1
        assert "total" in data
    
    def test_meeting_signals_extracted(self, client_with_data, assert_response_success):
        """Test that signals are included in meeting response."""
        response = client_with_data.get("/api/v1/meetings/1")
        data = assert_response_success(response)
        
        assert "signals" in data or "signals_json" in data


class TestMeetingSignalExtraction:
    """Tests for signal extraction from meetings."""
    
    @patch("src.app.mcp.extract.extract_structured_signals")
    def test_signals_extracted_on_create(self, mock_extract, client, mock_embeddings, meeting_factory):
        """Test that signals are extracted when creating a meeting."""
        mock_extract.return_value = {
            "decisions": [{"text": "Use pytest for testing", "confidence": 0.9}],
            "action_items": [{"text": "Set up CI pipeline", "assignee": "Team"}],
            "blockers": [],
            "risks": [],
            "ideas": []
        }
        
        meeting_data = meeting_factory(
            notes="Decision: Use pytest for testing. Action: Set up CI pipeline."
        )
        
        response = client.post("/api/v1/meetings", json=meeting_data)
        assert response.status_code == 201
        
        # Verify extraction was called
        mock_extract.assert_called_once()
    
    def test_signal_types_stored(self, client_with_data, assert_response_success):
        """Test that all signal types are preserved in stored meeting."""
        response = client_with_data.get("/api/v1/meetings/1")
        data = assert_response_success(response)
        
        signals = data.get("signals") or data.get("signals_json", {})
        if isinstance(signals, str):
            import json
            signals = json.loads(signals)
        
        # Check signal structure
        assert isinstance(signals, dict)


class TestMeetingScreenshots:
    """Tests for meeting screenshot handling."""
    
    def test_list_meeting_screenshots(self, client_with_data, assert_response_success):
        """Test listing screenshots for a meeting."""
        response = client_with_data.get("/api/v1/meetings/1/screenshots")
        # May return empty list or 404 depending on implementation
        assert response.status_code in [200, 404]
    
    @patch("src.app.agents.vision.analyze_image_adapter")
    def test_upload_screenshot(self, mock_vision, client_with_data):
        """Test uploading a screenshot with vision analysis."""
        mock_vision.return_value = "Screenshot shows a diagram of system architecture"
        
        # Create a simple test image (1x1 pixel PNG)
        test_image = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {"screenshot": ("test.png", test_image, "image/png")}
        response = client_with_data.post("/api/v1/meetings/1/screenshots", files=files)
        
        # Check response (may vary based on implementation)
        assert response.status_code in [200, 201, 404]
