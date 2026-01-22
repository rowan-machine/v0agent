# tests/test_signal_learning.py
"""
Tests for Signal Learning Service (PC-1 Implementation)

Verifies the feedback → AI learning loop for signal extraction.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestSignalLearningService:
    """Test suite for SignalLearningService."""
    
    @pytest.fixture
    def mock_feedback_data(self):
        """Sample feedback data for testing."""
        return [
            {"signal_type": "action", "feedback": "up", "signal_text": "John: Update documentation by Friday"},
            {"signal_type": "action", "feedback": "up", "signal_text": "Sarah: Review PR #123"},
            {"signal_type": "action", "feedback": "down", "signal_text": "stuff"},
            {"signal_type": "decision", "feedback": "up", "signal_text": "Decided to use React for frontend"},
            {"signal_type": "decision", "feedback": "up", "signal_text": "Approved budget for Q4"},
            {"signal_type": "risk", "feedback": "down", "signal_text": "something might happen"},
            {"signal_type": "risk", "feedback": "down", "signal_text": "various risks"},
            {"signal_type": "blocker", "feedback": "up", "signal_text": "Waiting on API credentials from DevOps"},
        ]
    
    def test_service_initialization(self):
        """Test service can be initialized."""
        from src.app.services.signal_learning import SignalLearningService
        
        service = SignalLearningService()
        assert service is not None
        assert service.user_id is None
        
        service_with_user = SignalLearningService(user_id="test-user-123")
        assert service_with_user.user_id == "test-user-123"
    
    def test_build_summary_with_data(self, mock_feedback_data):
        """Test summary building with feedback data."""
        from src.app.services.signal_learning import SignalLearningService
        
        service = SignalLearningService()
        
        # Convert to expected format
        type_counts = [
            {"signal_type": "action", "feedback": "up", "count": 2},
            {"signal_type": "action", "feedback": "down", "count": 1},
            {"signal_type": "decision", "feedback": "up", "count": 2},
            {"signal_type": "risk", "feedback": "down", "count": 2},
            {"signal_type": "blocker", "feedback": "up", "count": 1},
        ]
        
        rejected = [
            {"signal_type": "action", "signal_text": "stuff"},
            {"signal_type": "risk", "signal_text": "something might happen"},
            {"signal_type": "risk", "signal_text": "various risks"},
        ]
        
        approved = [
            {"signal_type": "action", "signal_text": "John: Update documentation by Friday"},
            {"signal_type": "action", "signal_text": "Sarah: Review PR #123"},
            {"signal_type": "decision", "signal_text": "Decided to use React for frontend"},
            {"signal_type": "blocker", "signal_text": "Waiting on API credentials from DevOps"},
        ]
        
        summary = service._build_summary(type_counts, rejected, approved)
        
        assert "by_type" in summary
        assert "acceptance_rates" in summary
        assert "rejection_patterns" in summary
        assert "approval_patterns" in summary
        
        # Check acceptance rates
        assert summary["acceptance_rates"]["action"] == pytest.approx(66.7, 0.1)
        assert summary["acceptance_rates"]["decision"] == 100.0
        assert summary["acceptance_rates"]["risk"] == 0.0
    
    def test_analyze_rejection_patterns(self):
        """Test rejection pattern analysis."""
        from src.app.services.signal_learning import SignalLearningService
        
        service = SignalLearningService()
        
        rejected = [
            {"signal_type": "action", "signal_text": "stuff"},
            {"signal_type": "risk", "signal_text": "something"},
            {"signal_type": "idea", "signal_text": "x"},
            {"signal_type": "action", "signal_text": "y"},
            {"signal_type": "risk", "signal_text": "various things"},
        ]
        
        patterns = service._analyze_rejection_patterns(rejected)
        
        # Should identify short signals
        assert any("short" in p.lower() for p in patterns)
        # Should identify vague language
        assert any("vague" in p.lower() for p in patterns)
    
    def test_analyze_approval_patterns(self):
        """Test approval pattern analysis."""
        from src.app.services.signal_learning import SignalLearningService
        
        service = SignalLearningService()
        
        approved = [
            {"signal_type": "action", "signal_text": "John will update the docs by Friday"},
            {"signal_type": "action", "signal_text": "Team should review the proposal by EOD"},
            {"signal_type": "action", "signal_text": "Owner: Sarah - need to fix bug in auth module"},
            {"signal_type": "decision", "signal_text": "We decided to postpone the release until testing is complete"},
        ]
        
        patterns = service._analyze_approval_patterns(approved)
        
        # Should identify actionable language preference
        assert any("actionable" in p.lower() or "owner" in p.lower() for p in patterns)
    
    def test_generate_learning_context_empty(self):
        """Test learning context generation with no feedback."""
        from src.app.services.signal_learning import SignalLearningService
        
        service = SignalLearningService()
        
        # Mock empty feedback
        with patch.object(service, 'get_feedback_summary', return_value={"total_feedback": 0}):
            context = service.generate_learning_context()
            assert context == ""
    
    def test_generate_learning_context_with_data(self):
        """Test learning context generation with sufficient feedback."""
        from src.app.services.signal_learning import SignalLearningService
        
        service = SignalLearningService()
        
        mock_summary = {
            "total_feedback": 20,
            "acceptance_rates": {
                "action": 80.0,
                "decision": 90.0,
                "risk": 40.0,
            },
            "rejection_patterns": [
                "Avoid extracting very short signals",
                "Avoid vague language"
            ],
            "approval_patterns": [
                "User prefers detailed signals",
                "Most valued signal types: decision, action"
            ]
        }
        
        with patch.object(service, 'get_feedback_summary', return_value=mock_summary):
            context = service.generate_learning_context()
            
            assert "Signal Quality Guidelines" in context
            assert "action" in context or "decision" in context
    
    def test_get_signal_quality_hints(self):
        """Test getting quality hints for specific signal type."""
        from src.app.services.signal_learning import SignalLearningService
        
        service = SignalLearningService()
        
        mock_summary = {
            "acceptance_rates": {"action": 75.0},
            "rejection_patterns": ["Be selective when extracting 'action' signals"],
            "approval_patterns": ["action items with clear ownership are valued"],
        }
        
        with patch.object(service, 'get_feedback_summary', return_value=mock_summary):
            hints = service.get_signal_quality_hints("action")
            
            assert hints["signal_type"] == "action"
            assert hints["acceptance_rate"] == 75.0
            assert hints["has_feedback"] is True


class TestSignalLearningIntegration:
    """Integration tests for signal learning with MeetingAnalyzerAgent."""
    
    def test_learning_context_integration(self):
        """Test that learning context can be retrieved for extraction."""
        from src.app.services.signal_learning import get_learning_context_for_extraction
        
        # This should not raise even with no data
        context = get_learning_context_for_extraction()
        assert isinstance(context, str)
    
    def test_refresh_learnings(self):
        """Test refresh_signal_learnings function."""
        from src.app.services.signal_learning import refresh_signal_learnings
        
        # Should return False when no feedback data
        with patch('src.app.services.signal_learning.get_signal_learning_service') as mock:
            mock_service = MagicMock()
            mock_service.store_learning_in_memory.return_value = None
            mock.return_value = mock_service
            
            result = refresh_signal_learnings()
            assert result is False


class TestSignalLearningAPI:
    """Test API endpoints for signal learning."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from src.app.main import app
        return TestClient(app)
    
    def test_feedback_learn_endpoint(self, client):
        """Test /api/signals/feedback-learn endpoint."""
        response = client.get("/api/signals/feedback-learn")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "feedback_summary" in data
        assert "has_sufficient_data" in data
    
    def test_quality_hints_endpoint(self, client):
        """Test /api/signals/quality-hints/{signal_type} endpoint."""
        response = client.get("/api/signals/quality-hints/action")
        
        assert response.status_code == 200
        data = response.json()
        assert "signal_type" in data
        assert data["signal_type"] == "action"
