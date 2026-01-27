# src/app/agents/meeting_analyzer/adapters.py
"""
Backward-compatible adapter functions for meeting_analyzer.

These functions maintain compatibility with existing code that uses
the module-level singleton pattern.
"""

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from ..base import AgentConfig
from .agent import MeetingAnalyzerAgent
from .parser import parse_adaptive as _parse_adaptive
from .extractor import (
    extract_signals_from_sections as _extract_from_sections,
    merge_signals,
    deduplicate_signals,
)

logger = logging.getLogger(__name__)

# Module-level singleton
_meeting_analyzer_instance: Optional[MeetingAnalyzerAgent] = None


def get_meeting_analyzer(
    llm_client=None,
    db_connection=None,
) -> MeetingAnalyzerAgent:
    """
    Get or create the MeetingAnalyzerAgent singleton.
    
    Args:
        llm_client: Optional LLM client override
        db_connection: Optional database connection
    
    Returns:
        MeetingAnalyzerAgent instance
    """
    global _meeting_analyzer_instance
    
    if _meeting_analyzer_instance is None:
        config = AgentConfig(
            name="meeting_analyzer",
            description="Extracts signals from meeting summaries and transcripts",
        )
        _meeting_analyzer_instance = MeetingAnalyzerAgent(
            config=config,
            llm_client=llm_client,
            db_connection=db_connection,
        )
        logger.info("Created MeetingAnalyzerAgent singleton")
    
    return _meeting_analyzer_instance


def parse_meeting_summary_adaptive(text: str) -> Dict[str, str]:
    """
    Parse meeting summary adaptively based on headings.
    
    This is the main entry point for parsing meeting text.
    Detects heading style (markdown, caps, etc.) and extracts sections.
    
    Args:
        text: Meeting summary text
    
    Returns:
        Dict mapping section names to content
    """
    return _parse_adaptive(text)


def extract_signals_from_meeting(
    text: str,
    parsed_sections: Dict[str, str] = None,
) -> Dict[str, List[str]]:
    """
    Extract signals from meeting text.
    
    Args:
        text: Meeting text (used if parsed_sections not provided)
        parsed_sections: Pre-parsed sections (optional)
    
    Returns:
        Dict with signal types as keys and list of signals as values
    """
    if parsed_sections is None:
        parsed_sections = _parse_adaptive(text)
    
    signals = _extract_from_sections(parsed_sections)
    return deduplicate_signals(signals)


# Async adapter for full meeting analysis
async def analyze_meeting(
    meeting_text: str,
    meeting_name: str = None,
    meeting_date: str = None,
    context: Dict[str, Any] = None,
    llm_client=None,
) -> Dict[str, Any]:
    """
    Full async meeting analysis with AI enhancement.
    
    Args:
        meeting_text: The meeting summary or transcript
        meeting_name: Optional meeting name
        meeting_date: Optional meeting date
        context: Additional context
        llm_client: Optional LLM client override
    
    Returns:
        Analysis results with signals and metadata
    """
    analyzer = get_meeting_analyzer(llm_client=llm_client)
    return await analyzer.run(
        meeting_text=meeting_text,
        meeting_name=meeting_name,
        meeting_date=meeting_date,
        context=context,
    )


__all__ = [
    "get_meeting_analyzer",
    "parse_meeting_summary_adaptive",
    "extract_signals_from_meeting",
    "analyze_meeting",
]
