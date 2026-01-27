# src/app/agents/meeting_analyzer/__init__.py
"""
Meeting Analyzer Agent Package

Extracts structured signals from meeting summaries and transcripts.
Supports multiple formats: Teams, Pocket, markdown, plain text.

Usage:
    # Singleton pattern (backward compatible)
    from src.app.agents.meeting_analyzer import (
        get_meeting_analyzer,
        parse_meeting_summary_adaptive,
        extract_signals_from_meeting,
    )
    
    # Direct class usage
    from src.app.agents.meeting_analyzer import MeetingAnalyzerAgent
    
    # Constants
    from src.app.agents.meeting_analyzer import SIGNAL_TYPES, HEADING_PATTERNS
"""

# Agent class
from .agent import MeetingAnalyzerAgent

# Constants
from .constants import (
    SIGNAL_TYPES,
    HEADING_PATTERNS,
    HEADING_TO_SIGNAL_TYPE,
    EMPTY_SIGNALS,
)

# Parser functions
from .parser import (
    parse_adaptive,
    detect_heading,
    parse_meeting_summary_adaptive,  # Alias
)

# Extractor functions
from .extractor import (
    extract_signals_from_sections,
    extract_items,
    extract_signals_keyword_fallback,
    parse_ai_signal_response,
    merge_signals,
    deduplicate_signals,
)

# Adapter functions (backward compatibility)
from .adapters import (
    get_meeting_analyzer,
    parse_meeting_summary_adaptive,
    extract_signals_from_meeting,
    analyze_meeting,
)

__all__ = [
    # Agent
    "MeetingAnalyzerAgent",
    
    # Constants
    "SIGNAL_TYPES",
    "HEADING_PATTERNS",
    "HEADING_TO_SIGNAL_TYPE",
    "EMPTY_SIGNALS",
    
    # Parser
    "parse_adaptive",
    "detect_heading",
    "parse_meeting_summary_adaptive",
    
    # Extractor
    "extract_signals_from_sections",
    "extract_items",
    "extract_signals_keyword_fallback",
    "parse_ai_signal_response",
    "merge_signals",
    "deduplicate_signals",
    
    # Adapters
    "get_meeting_analyzer",
    "extract_signals_from_meeting",
    "analyze_meeting",
]
