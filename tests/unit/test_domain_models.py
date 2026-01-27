# tests/unit/test_domain_models.py
"""
Unit tests for domain models.

Tests the core domain entities, value objects, and business logic
without external dependencies.
"""

import pytest
from datetime import datetime, date
from typing import Optional


class TestSignalEntity:
    """Tests for Signal domain entity."""
    
    def test_signal_creation(self):
        """Signal should be created with required fields."""
        from src.app.core.domain.models import Signal, SignalType
        
        signal = Signal(
            id="sig-1",
            signal_type=SignalType.DECISION,
            signal_text="Decided to use Python",
            confidence=0.85,
            meeting_id="mtg-10"
        )
        
        assert signal.id == "sig-1"
        assert signal.signal_type == SignalType.DECISION
        assert signal.signal_text == "Decided to use Python"
        assert signal.confidence == 0.85
        assert signal.meeting_id == "mtg-10"
    
    def test_signal_to_dict(self):
        """Signal should convert to dictionary correctly."""
        from src.app.core.domain.models import Signal, SignalType
        
        signal = Signal(
            id="sig-1",
            signal_type=SignalType.DECISION,
            signal_text="Test decision",
            confidence=0.8
        )
        
        d = signal.to_dict()
        assert d["id"] == "sig-1"
        assert d["signal_type"] == "decision"  # Should be string value
        assert d["signal_text"] == "Test decision"
    
    def test_signal_types(self):
        """All signal types should be accessible."""
        from src.app.core.domain.models import SignalType
        
        # Core types
        assert SignalType.DECISION.value == "decision"
        assert SignalType.ACTION_ITEM.value == "action_item"
        assert SignalType.RISK.value == "risk"
        assert SignalType.BLOCKER.value == "blocker"
        
        # Extended types
        assert SignalType.IDEA.value == "idea"
        assert SignalType.INSIGHT.value == "insight"


class TestMeetingEntity:
    """Tests for Meeting domain entity."""
    
    def test_meeting_creation(self):
        """Meeting should be created with required fields."""
        from src.app.core.domain.models import Meeting
        
        meeting = Meeting(
            id="mtg-1",
            meeting_name="Daily Standup",
            meeting_date="2024-01-15",
            summary="Team discussed progress"
        )
        
        assert meeting.id == "mtg-1"
        assert meeting.meeting_name == "Daily Standup"
        assert meeting.meeting_date == "2024-01-15"
    
    def test_meeting_with_signals(self):
        """Meeting should support signals dictionary."""
        from src.app.core.domain.models import Meeting
        
        meeting = Meeting(
            id="mtg-1",
            meeting_name="Test",
            meeting_date="2024-01-15",
            signals={
                "decisions": ["Decision 1", "Decision 2"],
                "action_items": ["Action 1"],
                "risks": []
            }
        )
        
        assert len(meeting.signals["decisions"]) == 2
        assert len(meeting.signals["action_items"]) == 1
    
    def test_meeting_pocket_fields(self):
        """Meeting should support Pocket integration fields."""
        from src.app.core.domain.models import Meeting
        
        meeting = Meeting(
            id="mtg-1",
            meeting_name="Test",
            pocket_recording_id="pocket-123",
            pocket_transcript="Transcript content",
            pocket_template_type="standup"
        )
        
        assert meeting.pocket_recording_id == "pocket-123"
        assert meeting.pocket_template_type == "standup"


class TestDIKWItem:
    """Tests for DIKW domain entity."""
    
    def test_dikw_levels(self):
        """DIKW should support all pyramid levels."""
        from src.app.core.domain.models import DIKWLevel
        
        assert DIKWLevel.DATA.value == "data"
        assert DIKWLevel.INFORMATION.value == "information"
        assert DIKWLevel.KNOWLEDGE.value == "knowledge"
        assert DIKWLevel.WISDOM.value == "wisdom"
    
    def test_dikw_level_hierarchy(self):
        """DIKW levels should follow pyramid order."""
        from src.app.core.domain.models import DIKWLevel
        
        levels = list(DIKWLevel)
        level_names = [l.value for l in levels]
        
        # Verify order
        assert level_names.index("data") < level_names.index("information")
        assert level_names.index("information") < level_names.index("knowledge")
        assert level_names.index("knowledge") < level_names.index("wisdom")


class TestTicketEntity:
    """Tests for Ticket domain entity."""
    
    def test_ticket_status_workflow(self):
        """Ticket statuses should cover full workflow."""
        from src.app.core.domain.models import TicketStatus
        
        assert TicketStatus.BACKLOG.value == "backlog"
        assert TicketStatus.READY.value == "ready"
        assert TicketStatus.IN_PROGRESS.value == "in_progress"
        assert TicketStatus.BLOCKED.value == "blocked"
        assert TicketStatus.IN_REVIEW.value == "in_review"
        assert TicketStatus.DONE.value == "done"


class TestNotificationEntity:
    """Tests for Notification domain entity."""
    
    def test_notification_types(self):
        """All notification types should be accessible."""
        from src.app.core.domain.models import NotificationType
        
        assert NotificationType.INFO.value == "info"
        assert NotificationType.SUCCESS.value == "success"
        assert NotificationType.WARNING.value == "warning"
        assert NotificationType.ERROR.value == "error"
        assert NotificationType.TASK.value == "task"


class TestSuggestionEntity:
    """Tests for Suggestion domain entities."""
    
    def test_suggestion_types(self):
        """All suggestion types should be accessible."""
        from src.app.core.domain.models import SuggestionType
        
        assert SuggestionType.SKILL_DEVELOPMENT.value == "skill_development"
        assert SuggestionType.PROJECT_IDEA.value == "project_idea"
        assert SuggestionType.LEARNING_PATH.value == "learning_path"
    
    def test_suggestion_status_workflow(self):
        """Suggestion statuses should cover lifecycle."""
        from src.app.core.domain.models import SuggestionStatus
        
        assert SuggestionStatus.SUGGESTED.value == "suggested"
        assert SuggestionStatus.ACCEPTED.value == "accepted"
        assert SuggestionStatus.DISMISSED.value == "dismissed"
        assert SuggestionStatus.COMPLETED.value == "completed"
        assert SuggestionStatus.CONVERTED.value == "converted"


class TestMemoryType:
    """Tests for Memory type enum."""
    
    def test_memory_types(self):
        """All memory types should be accessible."""
        from src.app.core.domain.models import MemoryType
        
        assert MemoryType.PROJECT.value == "project"
        assert MemoryType.ACHIEVEMENT.value == "achievement"
        assert MemoryType.LEARNING.value == "learning"
        assert MemoryType.FEEDBACK.value == "feedback"
        assert MemoryType.MILESTONE.value == "milestone"
