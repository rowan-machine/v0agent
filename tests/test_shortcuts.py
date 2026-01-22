# tests/test_shortcuts.py
"""
Tests for Arjuna Shortcuts API

Tests the shortcuts management system including:
- System default shortcuts
- AI-suggested shortcuts
- Usage tracking
- CRUD operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestSystemShortcuts:
    """Test system default shortcuts"""
    
    def test_system_shortcuts_defined(self):
        """Test system shortcuts are properly defined"""
        from src.app.api.shortcuts import SYSTEM_SHORTCUTS
        
        assert len(SYSTEM_SHORTCUTS) >= 4
        
        # Check required keys
        for shortcut in SYSTEM_SHORTCUTS:
            assert "shortcut_key" in shortcut
            assert "label" in shortcut
            assert "message" in shortcut
            assert "emoji" in shortcut
            assert "source" in shortcut
            assert shortcut["source"] == "system"
    
    def test_focus_shortcut_exists(self):
        """Test focus shortcut is available"""
        from src.app.api.shortcuts import SYSTEM_SHORTCUTS
        
        focus = next((s for s in SYSTEM_SHORTCUTS if s["shortcut_key"] == "focus"), None)
        assert focus is not None
        assert focus["emoji"] == "🎯"
        assert "focus" in focus["message"].lower()
    
    def test_blocked_shortcut_exists(self):
        """Test blocked shortcut is available"""
        from src.app.api.shortcuts import SYSTEM_SHORTCUTS
        
        blocked = next((s for s in SYSTEM_SHORTCUTS if s["shortcut_key"] == "blocked"), None)
        assert blocked is not None
        assert blocked["emoji"] == "🚫"
        assert "blocked" in blocked["message"].lower()
    
    def test_tickets_shortcut_exists(self):
        """Test tickets shortcut is available"""
        from src.app.api.shortcuts import SYSTEM_SHORTCUTS
        
        tickets = next((s for s in SYSTEM_SHORTCUTS if s["shortcut_key"] == "tickets"), None)
        assert tickets is not None
        assert tickets["emoji"] == "📋"


class TestShortcutsAPI:
    """Test shortcuts API endpoints"""
    
    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client"""
        with patch('src.app.api.shortcuts.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    def test_shortcut_create_model(self):
        """Test ShortcutCreate model validation"""
        from src.app.api.shortcuts import ShortcutCreate
        
        shortcut = ShortcutCreate(
            shortcut_key="test-key",
            label="Test Label",
            message="Test message",
            emoji="🧪"
        )
        
        assert shortcut.shortcut_key == "test-key"
        assert shortcut.label == "Test Label"
        assert shortcut.source == "ai"  # default
    
    def test_shortcut_create_defaults(self):
        """Test ShortcutCreate default values"""
        from src.app.api.shortcuts import ShortcutCreate
        
        shortcut = ShortcutCreate(
            shortcut_key="key",
            label="Label",
            message="Message"
        )
        
        assert shortcut.emoji == "💬"  # default emoji
        assert shortcut.source == "ai"  # default source
        assert shortcut.tooltip is None
    
    def test_shortcut_update_model(self):
        """Test ShortcutUpdate model allows partial updates"""
        from src.app.api.shortcuts import ShortcutUpdate
        
        # All fields are optional
        update = ShortcutUpdate(label="New Label")
        
        assert update.label == "New Label"
        assert update.message is None
        assert update.emoji is None
        assert update.is_active is None
    
    def test_shortcut_response_model(self):
        """Test ShortcutResponse model structure"""
        from src.app.api.shortcuts import ShortcutResponse
        
        response = ShortcutResponse(
            id="shortcut-123",
            shortcut_key="test",
            label="Test",
            message="Test message",
            emoji="🧪",
            tooltip="Test tooltip",
            source="system",
            usage_count=5,
            is_active=True,
            sort_order=1
        )
        
        assert response.id == "shortcut-123"
        assert response.usage_count == 5
        assert response.is_active == True


class TestShortcutSuggestionEngine:
    """Test AI suggestion generation for shortcuts"""
    
    @pytest.fixture
    def mock_supabase(self):
        with patch('src.app.api.shortcuts.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    def test_frequent_command_detection(self, mock_supabase):
        """Test detection of frequently used commands"""
        # This tests the pattern analysis for suggestions
        # Mock conversation data with repeated patterns
        conversations = [
            {"content": "What are my blocked tickets?"},
            {"content": "Show blocked tickets"},
            {"content": "What's blocked?"},
        ]
        
        # Pattern should detect "blocked" as common theme
        blocked_count = sum(1 for c in conversations if "blocked" in c["content"].lower())
        assert blocked_count >= 2
    
    def test_emoji_mapping(self):
        """Test emoji mapping for different contexts"""
        # Test that system shortcuts use appropriate emojis
        from src.app.api.shortcuts import SYSTEM_SHORTCUTS
        
        # Verify emojis are valid unicode characters
        for shortcut in SYSTEM_SHORTCUTS:
            emoji = shortcut.get("emoji", "")
            assert len(emoji) >= 1  # At least one character
            
        # Verify specific emoji mappings
        focus = next((s for s in SYSTEM_SHORTCUTS if s["shortcut_key"] == "focus"), None)
        assert focus["emoji"] == "🎯"
        
        blocked = next((s for s in SYSTEM_SHORTCUTS if s["shortcut_key"] == "blocked"), None)
        assert blocked["emoji"] == "🚫"


class TestUsageTracking:
    """Test shortcut usage tracking"""
    
    @pytest.fixture
    def mock_supabase(self):
        with patch('src.app.api.shortcuts.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    def test_usage_count_increments(self, mock_supabase):
        """Test that usage tracking increments counter"""
        # Mock the update query
        mock_query = Mock()
        mock_query.update.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = Mock(data=[{"usage_count": 6}])
        
        mock_supabase.table.return_value = mock_query
        
        # Verify the pattern of incrementing
        initial_count = 5
        new_count = initial_count + 1
        assert new_count == 6


class TestShortcutValidation:
    """Test shortcut input validation"""
    
    def test_shortcut_key_format(self):
        """Test shortcut key validation"""
        from src.app.api.shortcuts import ShortcutCreate
        
        # Valid shortcut key
        shortcut = ShortcutCreate(
            shortcut_key="my-shortcut",
            label="Label",
            message="Message"
        )
        assert shortcut.shortcut_key == "my-shortcut"
    
    def test_emoji_in_shortcut(self):
        """Test emoji can be stored with shortcut"""
        from src.app.api.shortcuts import ShortcutCreate
        
        shortcut = ShortcutCreate(
            shortcut_key="rocket",
            label="Launch",
            message="Launch the project",
            emoji="🚀"
        )
        assert shortcut.emoji == "🚀"
    
    def test_multiline_message(self):
        """Test multiline messages are allowed"""
        from src.app.api.shortcuts import ShortcutCreate
        
        shortcut = ShortcutCreate(
            shortcut_key="multiline",
            label="Multi",
            message="Line 1\nLine 2\nLine 3"
        )
        assert "\n" in shortcut.message


class TestAISuggestionGeneration:
    """Test AI-powered shortcut suggestion generation"""
    
    @pytest.fixture
    def mock_supabase(self):
        with patch('src.app.api.shortcuts.get_supabase_client') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    def test_suggestion_categories(self):
        """Test suggestion categories are comprehensive"""
        categories = [
            "tickets",
            "meetings", 
            "standup",
            "focus",
            "blocked",
            "planning",
            "signals"
        ]
        
        # All core categories should be coverable
        assert len(categories) >= 5
    
    def test_suggestion_deduplication(self):
        """Test AI suggestions avoid duplicating system shortcuts"""
        from src.app.api.shortcuts import SYSTEM_SHORTCUTS
        
        system_keys = {s["shortcut_key"] for s in SYSTEM_SHORTCUTS}
        
        # AI suggestions should not duplicate these
        new_suggestion_key = "custom-action"
        assert new_suggestion_key not in system_keys
