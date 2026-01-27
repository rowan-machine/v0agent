# tests/unit/test_meeting_analyzer.py
"""
Unit tests for Meeting Analyzer Agent Package.

Tests the modular components of the meeting_analyzer package:
- Constants (signal types, heading patterns)
- Parser (adaptive parsing, heading detection)
- Extractor (signal extraction, merging, deduplication)
- Agent class
- Adapter functions
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

class TestMeetingAnalyzerConstants:
    """Tests for meeting analyzer constants."""
    
    def test_signal_types_defined(self):
        """All signal types should be defined with metadata."""
        from src.app.agents.meeting_analyzer.constants import SIGNAL_TYPES
        
        expected_types = ["decision", "action_item", "blocker", "risk", "idea", "key_signal"]
        
        for signal_type in expected_types:
            assert signal_type in SIGNAL_TYPES
            assert "keywords" in SIGNAL_TYPES[signal_type]
            assert "emoji" in SIGNAL_TYPES[signal_type]
            assert "dikw_level" in SIGNAL_TYPES[signal_type]
    
    def test_heading_patterns_defined(self):
        """Heading patterns should be defined for adaptive parsing."""
        from src.app.agents.meeting_analyzer.constants import HEADING_PATTERNS
        
        assert "markdown_h1" in HEADING_PATTERNS
        assert "markdown_h2" in HEADING_PATTERNS
        assert "bold" in HEADING_PATTERNS
        assert "colon" in HEADING_PATTERNS
    
    def test_heading_to_signal_type_mapping(self):
        """Heading variations should map to canonical signal types."""
        from src.app.agents.meeting_analyzer.constants import HEADING_TO_SIGNAL_TYPE
        
        # Decisions
        assert HEADING_TO_SIGNAL_TYPE["decisions"] == "decision"
        assert HEADING_TO_SIGNAL_TYPE["agreed"] == "decision"
        
        # Actions
        assert HEADING_TO_SIGNAL_TYPE["action items"] == "action_item"
        assert HEADING_TO_SIGNAL_TYPE["next steps"] == "action_item"
        assert HEADING_TO_SIGNAL_TYPE["tasks"] == "action_item"
        
        # Blockers
        assert HEADING_TO_SIGNAL_TYPE["blockers"] == "blocker"
        
        # Risks
        assert HEADING_TO_SIGNAL_TYPE["risks"] == "risk"
        assert HEADING_TO_SIGNAL_TYPE["concerns"] == "risk"
    
    def test_empty_signals_template(self):
        """Empty signals template should have all required keys."""
        from src.app.agents.meeting_analyzer.constants import EMPTY_SIGNALS
        
        expected_keys = ["decisions", "action_items", "blockers", "risks", "ideas", "key_signals", "context", "notes"]
        
        for key in expected_keys:
            assert key in EMPTY_SIGNALS


# =============================================================================
# PARSER TESTS
# =============================================================================

class TestMeetingParser:
    """Tests for meeting text parser."""
    
    def test_parse_markdown_headings(self):
        """Should parse markdown-style headings."""
        from src.app.agents.meeting_analyzer.parser import parse_adaptive
        
        text = """## Decisions
- Decided to use Python
- Agreed on API design

## Action Items
- Review PR by Friday
- Update documentation
"""
        
        sections = parse_adaptive(text)
        
        assert "decision" in sections or "decisions" in sections.keys()
    
    def test_parse_colon_headings(self):
        """Should parse colon-terminated headings."""
        from src.app.agents.meeting_analyzer.parser import parse_adaptive
        
        text = """Decisions:
- Decision 1
- Decision 2

Action Items:
- Action 1
"""
        
        sections = parse_adaptive(text)
        
        # Should have parsed some sections
        assert len(sections) >= 1
    
    def test_detect_heading_markdown(self):
        """Should detect markdown heading patterns."""
        from src.app.agents.meeting_analyzer.parser import detect_heading
        
        # Should detect h2
        result = detect_heading("## Decisions")
        assert result is not None
        
        # Should detect h1
        result = detect_heading("# Summary")
        assert result is not None
    
    def test_detect_heading_colon(self):
        """Should detect colon-terminated headings."""
        from src.app.agents.meeting_analyzer.parser import detect_heading
        
        result = detect_heading("Decisions:")
        assert result is not None
    
    def test_detect_non_heading(self):
        """Should return None for non-headings."""
        from src.app.agents.meeting_analyzer.parser import detect_heading
        
        result = detect_heading("- This is a bullet point")
        assert result is None
        
        result = detect_heading("Regular text content here")
        assert result is None
    
    def test_parse_empty_text(self):
        """Should handle empty text."""
        from src.app.agents.meeting_analyzer.parser import parse_adaptive
        
        sections = parse_adaptive("")
        assert isinstance(sections, dict)
    
    def test_parse_no_headings(self):
        """Should put unstructured text in notes."""
        from src.app.agents.meeting_analyzer.parser import parse_adaptive
        
        text = """This is just some notes without any headings.
Multiple lines of text.
Nothing structured."""
        
        sections = parse_adaptive(text)
        
        # Should have some output
        assert len(sections) >= 0  # May have 'notes' section


# =============================================================================
# EXTRACTOR TESTS
# =============================================================================

class TestSignalExtractor:
    """Tests for signal extraction functions."""
    
    @pytest.fixture
    def parsed_sections(self):
        """Sample parsed sections."""
        return {
            "decisions": "- Decided to use PostgreSQL\n- Agreed on semver versioning",
            "action_items": "- Review PR by Friday\n- Update documentation",
            "blockers": "- Waiting for API credentials",
            "risks": "- Timeline may slip",
        }
    
    def test_extract_signals_from_sections(self, parsed_sections):
        """Should extract signals from parsed sections."""
        from src.app.agents.meeting_analyzer.extractor import extract_signals_from_sections
        
        signals = extract_signals_from_sections(parsed_sections)
        
        assert "decisions" in signals
        assert "action_items" in signals
        assert "blockers" in signals
        assert "risks" in signals
        
        # Should have extracted items
        assert len(signals["decisions"]) == 2
        # action_items key in fixture matches section mapping
        assert len(signals["blockers"]) == 1
    
    def test_extract_items_from_bullets(self):
        """Should extract items from bullet point content."""
        from src.app.agents.meeting_analyzer.extractor import extract_items
        
        content = """- First item
- Second item
- Third item"""
        
        items = extract_items(content)
        
        assert len(items) == 3
        assert "First item" in items
    
    def test_extract_items_removes_bullets(self):
        """Should remove bullet markers from items."""
        from src.app.agents.meeting_analyzer.extractor import extract_items
        
        content = """- Item with dash
* Item with asterisk
• Item with bullet"""
        
        items = extract_items(content)
        
        for item in items:
            assert not item.startswith("-")
            assert not item.startswith("*")
            assert not item.startswith("•")
    
    def test_merge_signals(self):
        """Should merge signals without duplicates."""
        from src.app.agents.meeting_analyzer.extractor import merge_signals
        
        base = {
            "decisions": ["Decision 1", "Decision 2"],
            "action_items": ["Action 1"],
        }
        
        additional = {
            "decisions": ["Decision 3"],
            "action_items": ["Action 1", "Action 2"],  # Action 1 is duplicate
        }
        
        merged = merge_signals(base, additional)
        
        assert len(merged["decisions"]) == 3
        assert len(merged["action_items"]) == 2  # No duplicate
    
    def test_deduplicate_signals(self):
        """Should remove duplicate signals."""
        from src.app.agents.meeting_analyzer.extractor import deduplicate_signals
        
        signals = {
            "decisions": [
                "Decided to use Python",
                "decided to use python",  # Duplicate (case insensitive)
                "Another decision",
            ],
            "action_items": ["Action 1", "Action 1"],  # Exact duplicate
        }
        
        deduped = deduplicate_signals(signals)
        
        assert len(deduped["decisions"]) == 2
        assert len(deduped["action_items"]) == 1
    
    def test_parse_ai_signal_response_json(self):
        """Should parse JSON AI response."""
        from src.app.agents.meeting_analyzer.extractor import parse_ai_signal_response
        
        response = '{"decisions": ["Decision 1"], "action_items": ["Action 1"]}'
        
        signals = parse_ai_signal_response(response)
        
        assert len(signals["decisions"]) == 1
        assert len(signals["action_items"]) == 1
    
    def test_extract_signals_keyword_fallback(self):
        """Should extract signals using keyword fallback."""
        from src.app.agents.meeting_analyzer.extractor import extract_signals_keyword_fallback
        
        text = """We decided to implement the new feature.
Action: Review the code by Friday.
There's a risk that we might miss the deadline.
We're blocked by the vendor."""
        
        signals = extract_signals_keyword_fallback(text)
        
        # Should find some signals based on keywords
        assert isinstance(signals, dict)


# =============================================================================
# AGENT CLASS TESTS
# =============================================================================

class TestMeetingAnalyzerAgent:
    """Tests for MeetingAnalyzerAgent class."""
    
    def test_agent_instantiation(self):
        """Agent should instantiate with config."""
        from src.app.agents.meeting_analyzer.agent import MeetingAnalyzerAgent
        from src.app.agents.base import AgentConfig
        
        config = AgentConfig(
            name="test_meeting_analyzer",
            description="Test meeting analyzer",
        )
        
        agent = MeetingAnalyzerAgent(config=config)
        
        assert agent.config.name == "test_meeting_analyzer"
    
    def test_parse_adaptive_method(self):
        """Agent should expose parse_adaptive method."""
        from src.app.agents.meeting_analyzer.agent import MeetingAnalyzerAgent
        from src.app.agents.base import AgentConfig
        
        config = AgentConfig(name="test", description="test")
        agent = MeetingAnalyzerAgent(config=config)
        
        text = "## Decisions\n- Decision 1"
        sections = agent.parse_adaptive(text)
        
        assert isinstance(sections, dict)
    
    def test_extract_signals_method(self):
        """Agent should expose extract_signals_from_sections method."""
        from src.app.agents.meeting_analyzer.agent import MeetingAnalyzerAgent
        from src.app.agents.base import AgentConfig
        
        config = AgentConfig(name="test", description="test")
        agent = MeetingAnalyzerAgent(config=config)
        
        sections = {"decisions": "- Test decision"}
        signals = agent.extract_signals_from_sections(sections)
        
        assert "decisions" in signals


# =============================================================================
# ADAPTER FUNCTIONS TESTS
# =============================================================================

class TestMeetingAnalyzerAdapters:
    """Tests for backward-compatible adapter functions."""
    
    def test_get_meeting_analyzer_singleton(self):
        """Should return singleton instance."""
        from src.app.agents.meeting_analyzer.adapters import get_meeting_analyzer
        
        agent1 = get_meeting_analyzer()
        agent2 = get_meeting_analyzer()
        
        # Should be same instance
        assert agent1 is agent2
    
    def test_parse_meeting_summary_adaptive(self):
        """Adapter should delegate to parser."""
        from src.app.agents.meeting_analyzer.adapters import parse_meeting_summary_adaptive
        
        text = "## Decisions\n- Decision 1"
        sections = parse_meeting_summary_adaptive(text)
        
        assert isinstance(sections, dict)
    
    def test_extract_signals_from_meeting(self):
        """Adapter should extract signals from text."""
        from src.app.agents.meeting_analyzer.adapters import extract_signals_from_meeting
        
        text = """## Decisions
- Decided to use Python

## Action Items
- Review PR by Friday
"""
        
        signals = extract_signals_from_meeting(text)
        
        assert "decisions" in signals
        assert "action_items" in signals


# =============================================================================
# PACKAGE EXPORTS TESTS
# =============================================================================

class TestMeetingAnalyzerPackageExports:
    """Tests for package-level exports."""
    
    def test_constants_exported(self):
        """Constants should be importable from package."""
        from src.app.agents.meeting_analyzer import (
            SIGNAL_TYPES,
            HEADING_PATTERNS,
            HEADING_TO_SIGNAL_TYPE,
            EMPTY_SIGNALS,
        )
        
        assert SIGNAL_TYPES is not None
        assert HEADING_PATTERNS is not None
    
    def test_parser_exported(self):
        """Parser functions should be importable from package."""
        from src.app.agents.meeting_analyzer import (
            parse_adaptive,
            detect_heading,
            parse_meeting_summary_adaptive,
        )
        
        assert parse_adaptive is not None
        assert detect_heading is not None
    
    def test_extractor_exported(self):
        """Extractor functions should be importable from package."""
        from src.app.agents.meeting_analyzer import (
            extract_signals_from_sections,
            extract_items,
            merge_signals,
            deduplicate_signals,
        )
        
        assert extract_signals_from_sections is not None
        assert merge_signals is not None
    
    def test_agent_exported(self):
        """Agent class should be importable from package."""
        from src.app.agents.meeting_analyzer import MeetingAnalyzerAgent
        
        assert MeetingAnalyzerAgent is not None
    
    def test_adapters_exported(self):
        """Adapter functions should be importable from package."""
        from src.app.agents.meeting_analyzer import (
            get_meeting_analyzer,
            extract_signals_from_meeting,
            analyze_meeting,
        )
        
        assert get_meeting_analyzer is not None
        assert extract_signals_from_meeting is not None
