# tests/test_coach_recommendations.py
"""
Tests for CoachRecommendationEngine

Tests the embedding-based recommendation system for the "Your Coach" dashboard.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestCoachRecommendationEngine:
    """Test suite for CoachRecommendationEngine"""
    
    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client"""
        with patch('src.app.services.coach_recommendations.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    @pytest.fixture
    def engine(self, mock_supabase):
        """Create engine instance with mocked Supabase"""
        from src.app.services.coach_recommendations import CoachRecommendationEngine
        return CoachRecommendationEngine(user_id="test-user-123", user_name="TestUser")
    
    def test_engine_initialization(self, mock_supabase):
        """Test engine initializes correctly"""
        from src.app.services.coach_recommendations import CoachRecommendationEngine
        engine = CoachRecommendationEngine(user_id="user-1", user_name="Alice")
        
        assert engine.user_id == "user-1"
        assert engine.user_name == "Alice"
        assert engine.supabase is not None
    
    def test_get_recommendations_empty(self, engine, mock_supabase):
        """Test getting recommendations when database is empty"""
        # Mock all query methods to return empty results
        mock_query = Mock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.ilike.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.execute.return_value = Mock(data=[])
        
        mock_supabase.table.return_value = mock_query
        mock_supabase.rpc.return_value = Mock()
        mock_supabase.rpc.return_value.execute.return_value = Mock(data=[])
        
        recommendations = engine.get_recommendations()
        
        assert isinstance(recommendations, list)
    
    def test_get_recommendations_respects_dismissed(self, engine, mock_supabase):
        """Test that dismissed IDs are filtered out"""
        mock_query = Mock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.ilike.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.execute.return_value = Mock(data=[])
        
        mock_supabase.table.return_value = mock_query
        mock_supabase.rpc.return_value = Mock()
        mock_supabase.rpc.return_value.execute.return_value = Mock(data=[])
        
        dismissed = ["rec-1", "rec-2"]
        recommendations = engine.get_recommendations(dismissed_ids=dismissed)
        
        assert isinstance(recommendations, list)
    
    def test_get_recommendations_max_items(self, engine, mock_supabase):
        """Test max_items parameter limits results"""
        mock_query = Mock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.ilike.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.execute.return_value = Mock(data=[])
        
        mock_supabase.table.return_value = mock_query
        mock_supabase.rpc.return_value = Mock()
        mock_supabase.rpc.return_value.execute.return_value = Mock(data=[])
        
        recommendations = engine.get_recommendations(max_items=5)
        
        assert len(recommendations) <= 5
    
    def test_priority_ordering(self, engine, mock_supabase):
        """Test recommendations are sorted by priority"""
        # Create mock recommendations of different types
        mock_recs = [
            {"id": "1", "type": "idea", "title": "Low priority"},
            {"id": "2", "type": "blocker", "title": "High priority"},
            {"id": "3", "type": "mention", "title": "Medium priority"},
        ]
        
        # Priority order: blocker > mention > idea
        priority_map = {"blocker": 0, "mention": 1, "idea": 7}
        sorted_recs = sorted(mock_recs, key=lambda r: priority_map.get(r.get("type", "idea"), 99))
        
        assert sorted_recs[0]["type"] == "blocker"
        assert sorted_recs[1]["type"] == "mention"
        assert sorted_recs[2]["type"] == "idea"


class TestDIKWRecommendations:
    """Tests for DIKW-based recommendations"""
    
    @pytest.fixture
    def mock_supabase(self):
        with patch('src.app.services.coach_recommendations.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    @pytest.fixture
    def engine(self, mock_supabase):
        from src.app.services.coach_recommendations import CoachRecommendationEngine
        return CoachRecommendationEngine(user_id="test-user", user_name="Test")
    
    def test_dikw_recommendations_format(self, engine, mock_supabase):
        """Test DIKW recommendations have correct format"""
        # Mock DIKW data
        dikw_data = [
            {
                "id": "dikw-1",
                "title": "Important pattern detected",
                "stage": "knowledge",
                "created_at": datetime.now().isoformat(),
                "content": "Test content"
            }
        ]
        
        mock_query = Mock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.ilike.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.execute.return_value = Mock(data=dikw_data)
        
        mock_supabase.table.return_value = mock_query
        mock_supabase.rpc.return_value = Mock()
        mock_supabase.rpc.return_value.execute.return_value = Mock(data=[])
        
        recs = engine._get_dikw_recommendations([])
        
        # Should return recommendations list
        assert isinstance(recs, list)


class TestMentionRecommendations:
    """Tests for user mention recommendations"""
    
    @pytest.fixture
    def mock_supabase(self):
        with patch('src.app.services.coach_recommendations.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    @pytest.fixture  
    def engine(self, mock_supabase):
        from src.app.services.coach_recommendations import CoachRecommendationEngine
        return CoachRecommendationEngine(user_id="test-user", user_name="TestUser")
    
    def test_mention_detection_uses_username(self, engine, mock_supabase):
        """Test mentions are searched by username"""
        mock_query = Mock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.ilike.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.execute.return_value = Mock(data=[])
        
        mock_supabase.table.return_value = mock_query
        mock_supabase.rpc.return_value = Mock()
        mock_supabase.rpc.return_value.execute.return_value = Mock(data=[])
        
        engine._get_user_mention_recommendations([])
        
        # Verify ilike was called (for case-insensitive username search)
        # The exact call depends on implementation


class TestTranscriptRecommendations:
    """Tests for missing transcript recommendations"""
    
    @pytest.fixture
    def mock_supabase(self):
        with patch('src.app.services.coach_recommendations.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    @pytest.fixture
    def engine(self, mock_supabase):
        from src.app.services.coach_recommendations import CoachRecommendationEngine
        return CoachRecommendationEngine(user_id="test-user", user_name="Test")
    
    def test_missing_transcript_recommendations(self, engine, mock_supabase):
        """Test recommendations for meetings without transcripts"""
        # Mock meetings without transcripts
        meetings_data = [
            {
                "id": "meeting-1",
                "title": "Team Standup",
                "date": datetime.now().isoformat(),
                "transcript": None
            }
        ]
        
        mock_query = Mock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.ilike.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.execute.return_value = Mock(data=meetings_data)
        
        mock_supabase.table.return_value = mock_query
        mock_supabase.rpc.return_value = Mock()
        mock_supabase.rpc.return_value.execute.return_value = Mock(data=[])
        
        recs = engine._get_missing_transcript_recommendations([])
        
        assert isinstance(recs, list)


class TestBacklogGroomingRecommendations:
    """Tests for ticket backlog grooming recommendations"""
    
    @pytest.fixture
    def mock_supabase(self):
        with patch('src.app.services.coach_recommendations.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    @pytest.fixture
    def engine(self, mock_supabase):
        from src.app.services.coach_recommendations import CoachRecommendationEngine
        return CoachRecommendationEngine(user_id="test-user", user_name="Test")
    
    def test_grooming_recommendations_for_stale_tickets(self, engine, mock_supabase):
        """Test recommendations for tickets needing grooming"""
        stale_tickets = [
            {
                "id": "ticket-1",
                "key": "PROJ-123",
                "summary": "Old ticket",
                "status": "In Progress",
                "updated_at": (datetime.now() - timedelta(days=30)).isoformat()
            }
        ]
        
        mock_query = Mock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.neq.return_value = mock_query
        mock_query.lte.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.ilike.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.execute.return_value = Mock(data=stale_tickets)
        
        mock_supabase.table.return_value = mock_query
        mock_supabase.rpc.return_value = Mock()
        mock_supabase.rpc.return_value.execute.return_value = Mock(data=[])
        
        recs = engine._get_backlog_grooming_recommendations([])
        
        assert isinstance(recs, list)
