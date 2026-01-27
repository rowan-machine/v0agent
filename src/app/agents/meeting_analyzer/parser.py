# src/app/agents/meeting_analyzer/parser.py
"""
Meeting Analyzer Parser

Adaptive parsing utilities for meeting summaries.
Supports multiple formats: Teams, Pocket, manual markdown, etc.
"""

import re
import logging
from typing import Dict, List, Optional

from .constants import HEADING_PATTERNS, HEADING_TO_SIGNAL_TYPE

logger = logging.getLogger(__name__)


def parse_adaptive(text: str) -> Dict[str, str]:
    """
    Adaptively parse meeting text by detecting heading patterns.
    
    Supports multiple formats:
    - Teams summary format
    - Pocket dynamic summaries
    - Manual markdown notes
    - Plain text with colon-headers
    
    Args:
        text: Raw meeting summary text
    
    Returns:
        Dict mapping section names to content
    """
    result = {}
    current_section = None
    buffer: List[str] = []
    
    lines = text.splitlines()
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines but preserve them in content
        if not stripped:
            buffer.append(line)
            continue
        
        # Skip HTML aside tags
        if stripped.startswith("<aside") or stripped.endswith("</aside>"):
            continue
        
        # Try to detect a heading
        heading = detect_heading(stripped)
        
        if heading:
            # Save previous section
            if current_section:
                result[current_section] = "\n".join(buffer).strip()
            current_section = heading
            buffer = []
            continue
        
        buffer.append(line)
    
    # Save final section
    if current_section:
        result[current_section] = "\n".join(buffer).strip()
    elif buffer:
        # No sections detected - treat entire text as notes
        result["notes"] = "\n".join(buffer).strip()
    
    return result


def detect_heading(line: str) -> Optional[str]:
    """
    Detect if a line is a heading and return the canonical heading name.
    
    Args:
        line: A single line of text
    
    Returns:
        Canonical heading name or None
    """
    # Remove markdown formatting
    cleaned = line.lstrip("#").strip().strip("*").strip()
    
    # Try each heading pattern
    for pattern_name, pattern in HEADING_PATTERNS.items():
        match = re.match(pattern, line)
        if match:
            if pattern_name == "emoji":
                # For emoji patterns, use the text part
                heading_text = match.group(2).lower().strip()
            else:
                heading_text = match.group(1).lower().strip() if match.groups() else cleaned.lower()
            
            # Map to canonical type if known, otherwise use original
            return HEADING_TO_SIGNAL_TYPE.get(heading_text, cleaned)
    
    # Check if the cleaned text matches known headers
    cleaned_lower = cleaned.lower()
    if cleaned_lower in HEADING_TO_SIGNAL_TYPE:
        return HEADING_TO_SIGNAL_TYPE[cleaned_lower]
    
    return None


def parse_meeting_summary_adaptive(text: str) -> Dict[str, str]:
    """
    Legacy wrapper for parse_adaptive.
    Maintained for backward compatibility.
    """
    return parse_adaptive(text)


__all__ = [
    "parse_adaptive",
    "detect_heading",
    "parse_meeting_summary_adaptive",
]
