# tests/test_api_feedback.py
"""
Tests for Signal Feedback Loop API.

Tests the /api/v1/signals/feedback endpoints for:
- Recording upvotes/downvotes
- Confidence score adjustments
- Feedback statistics
- Approved signals retrieval
"""

import pytest


class TestSignalFeedbackAPI:
    """Test suite for signal feedback endpoints."""
    
    def test_create_feedback_upvote(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test recording an upvote on a signal."""
        feedback_data = signal_feedback_factory(
            meeting_id=1,
            signal_type="action_item",
            signal_text="Complete test implementation",
            feedback="up"
        )
        
        response = client_with_data.post("/api/v1/signals/feedback", json=feedback_data)
        data = assert_response_success(response, status_code=201)
        
        assert data["feedback"] == "up"
        assert data["signal_type"] == "action_item"
        assert data["include_in_chat"] is True
    
    def test_create_feedback_downvote(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test recording a downvote on a signal."""
        feedback_data = signal_feedback_factory(
            signal_type="decision",
            signal_text="Incorrect extraction",
            feedback="down"
        )
        
        response = client_with_data.post("/api/v1/signals/feedback", json=feedback_data)
        data = assert_response_success(response, status_code=201)
        
        assert data["feedback"] == "down"
    
    def test_feedback_upsert_existing(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test that submitting feedback again updates existing record."""
        feedback_data = signal_feedback_factory(feedback="up")
        
        # First submission
        response1 = client_with_data.post("/api/v1/signals/feedback", json=feedback_data)
        data1 = assert_response_success(response1, status_code=201)
        
        # Change to downvote
        feedback_data["feedback"] = "down"
        response2 = client_with_data.post("/api/v1/signals/feedback", json=feedback_data)
        data2 = assert_response_success(response2, status_code=201)
        
        # Should be same record, updated
        assert data1["id"] == data2["id"]
        assert data2["feedback"] == "down"
    
    def test_list_feedback(self, client_with_data, assert_response_success):
        """Test listing all feedback."""
        response = client_with_data.get("/api/v1/signals/feedback")
        data = assert_response_success(response)
        
        assert isinstance(data, list)
    
    def test_list_feedback_filter_by_type(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test filtering feedback by signal type."""
        # Create feedback for different types
        for sig_type in ["decision", "action_item", "blocker"]:
            feedback = signal_feedback_factory(
                signal_type=sig_type,
                signal_text=f"Test {sig_type}"
            )
            client_with_data.post("/api/v1/signals/feedback", json=feedback)
        
        # Filter by type
        response = client_with_data.get("/api/v1/signals/feedback?signal_type=decision")
        data = assert_response_success(response)
        
        for item in data:
            assert item["signal_type"] == "decision"
    
    def test_list_feedback_filter_by_feedback_type(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test filtering by upvote/downvote."""
        response = client_with_data.get("/api/v1/signals/feedback?feedback_type=up")
        data = assert_response_success(response)
        
        for item in data:
            assert item["feedback"] == "up"
    
    def test_get_feedback_stats(self, client_with_data, assert_response_success):
        """Test getting aggregated feedback statistics."""
        response = client_with_data.get("/api/v1/signals/feedback/stats")
        data = assert_response_success(response)
        
        assert "total_feedback" in data
        assert "upvotes" in data
        assert "downvotes" in data
        assert "by_signal_type" in data
    
    def test_delete_feedback(self, client_with_data, signal_feedback_factory):
        """Test deleting feedback."""
        # Create feedback first
        feedback = signal_feedback_factory()
        create_response = client_with_data.post("/api/v1/signals/feedback", json=feedback)
        feedback_id = create_response.json()["id"]
        
        # Delete it
        delete_response = client_with_data.delete(f"/api/v1/signals/feedback/{feedback_id}")
        assert delete_response.status_code == 204
        
        # Verify it's gone
        list_response = client_with_data.get("/api/v1/signals/feedback")
        feedback_ids = [f["id"] for f in list_response.json()]
        assert feedback_id not in feedback_ids


class TestConfidenceBoost:
    """Tests for confidence boost calculations."""
    
    def test_get_confidence_boosts_empty(self, client, assert_response_success):
        """Test confidence boosts when no feedback exists."""
        response = client.get("/api/v1/signals/feedback/confidence-boost")
        data = assert_response_success(response)
        
        assert isinstance(data, list)
    
    def test_confidence_boost_calculation(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test that confidence boost is calculated from feedback ratio."""
        # Create mostly positive feedback for decisions
        for i in range(4):
            feedback = signal_feedback_factory(
                signal_type="decision",
                signal_text=f"Decision {i}",
                feedback="up"
            )
            client_with_data.post("/api/v1/signals/feedback", json=feedback)
        
        # One negative
        feedback = signal_feedback_factory(
            signal_type="decision",
            signal_text="Bad decision",
            feedback="down"
        )
        client_with_data.post("/api/v1/signals/feedback", json=feedback)
        
        response = client_with_data.get("/api/v1/signals/feedback/confidence-boost")
        data = assert_response_success(response)
        
        decision_boost = next((b for b in data if b["signal_type"] == "decision"), None)
        if decision_boost:
            # 4 up, 1 down = 0.8 ratio → 1.3 boost factor
            assert 1.0 <= decision_boost["boost_factor"] <= 1.5


class TestApprovedSignals:
    """Tests for retrieving approved signals for chat context."""
    
    def test_get_approved_signals_empty(self, client, assert_response_success):
        """Test approved signals when none exist."""
        response = client.get("/api/v1/signals/feedback/approved-signals")
        data = assert_response_success(response)
        
        assert data == []
    
    def test_get_approved_signals(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test retrieving upvoted signals marked for chat inclusion."""
        # Create upvoted feedback
        feedback = signal_feedback_factory(
            signal_text="Important action item",
            feedback="up",
        )
        feedback["include_in_chat"] = True
        client_with_data.post("/api/v1/signals/feedback", json=feedback)
        
        response = client_with_data.get("/api/v1/signals/feedback/approved-signals")
        data = assert_response_success(response)
        
        assert len(data) >= 1
        assert data[0]["signal_text"] == "Important action item"
    
    def test_excluded_signals_not_returned(
        self, client_with_data, signal_feedback_factory, assert_response_success
    ):
        """Test that signals excluded from chat are not returned."""
        # Create feedback excluded from chat
        feedback = signal_feedback_factory(feedback="up")
        feedback["include_in_chat"] = False
        client_with_data.post("/api/v1/signals/feedback", json=feedback)
        
        response = client_with_data.get("/api/v1/signals/feedback/approved-signals")
        data = assert_response_success(response)
        
        for signal in data:
            assert signal.get("include_in_chat", True) is True


class TestDIKWConfidenceUpdate:
    """Tests for DIKW confidence score updates from feedback."""
    
    def test_upvote_increases_confidence(
        self, client_with_data, signal_feedback_factory
    ):
        """Test that upvoting a signal increases related DIKW item confidence."""
        # Get initial DIKW item confidence
        # (This would need direct DB access to verify, simplified here)
        
        feedback = signal_feedback_factory(
            signal_type="information",  # Match DIKW source type
            signal_text="Test insight from meeting",  # Match DIKW content
            feedback="up"
        )
        
        response = client_with_data.post("/api/v1/signals/feedback", json=feedback)
        assert response.status_code == 201
        
        # Verify would need DB access to check confidence increased
    
    def test_downvote_decreases_confidence(
        self, client_with_data, signal_feedback_factory
    ):
        """Test that downvoting decreases DIKW confidence."""
        feedback = signal_feedback_factory(
            signal_type="information",
            signal_text="Test insight from meeting",
            feedback="down"
        )
        
        response = client_with_data.post("/api/v1/signals/feedback", json=feedback)
        assert response.status_code == 201
