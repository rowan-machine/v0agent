# src/app/agents/meeting_analyzer/extractor.py
"""
Meeting Analyzer Signal Extractor

Functions for extracting signals from parsed meeting sections.
"""

import json
import logging
from typing import Any, Dict, List

from .constants import SIGNAL_TYPES, EMPTY_SIGNALS

logger = logging.getLogger(__name__)


def extract_signals_from_sections(parsed_sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract structured signals from parsed sections.
    
    Args:
        parsed_sections: Dict of section_name -> content
    
    Returns:
        Dict with signal lists by type
    """
    signals = {
        "decisions": [],
        "action_items": [],
        "blockers": [],
        "risks": [],
        "ideas": [],
        "key_signals": [],
        "context": "",
        "notes": "",
    }
    
    # Check for synthesized signals section (highest priority)
    synthesized_key = next(
        (k for k in parsed_sections if "synthesized" in k.lower()),
        None
    )
    if synthesized_key:
        synthesized_signals = extract_from_synthesized(parsed_sections[synthesized_key])
        signals = merge_signals(signals, synthesized_signals)
    
    # Process each section
    for section_name, content in parsed_sections.items():
        if not content:
            continue
        
        section_lower = section_name.lower()
        
        # Map section to signal type
        if section_lower in ["decision", "decisions"]:
            signals["decisions"].extend(extract_items(content))
        elif section_lower in ["action_item", "action items", "tasks", "commitments", "work identified"]:
            signals["action_items"].extend(extract_items(content))
        elif section_lower in ["blocker", "blockers", "blocked"]:
            signals["blockers"].extend(extract_items(content))
        elif section_lower in ["risk", "risks", "concerns", "risks / open questions"]:
            signals["risks"].extend(extract_items(content))
        elif section_lower in ["idea", "ideas", "suggestions"]:
            signals["ideas"].extend(extract_items(content))
        elif section_lower in ["key_signal", "key signals", "insights", "outcomes"]:
            signals["key_signals"].extend(extract_items(content))
        elif section_lower in ["context", "background"]:
            signals["context"] = content
        elif section_lower in ["notes", "summary"]:
            signals["notes"] = content
    
    return signals


def extract_items(content: str) -> List[str]:
    """
    Extract individual items from section content.
    
    Args:
        content: Section text content
    
    Returns:
        List of extracted items
    """
    items = []
    
    for line in content.splitlines():
        stripped = line.strip()
        
        # Skip empty lines and markers
        if not stripped or stripped in ["🚦", "🧩", "✨", "📝", "🟩", "🟪"]:
            continue
        
        # Skip sub-headers
        if stripped.startswith("###") or stripped.startswith("**"):
            continue
        
        # Remove bullet points and clean
        item = stripped.lstrip("-•*").strip()
        
        if item and len(item) > 2:  # Minimum length check
            items.append(item)
    
    return items


def extract_from_synthesized(text: str) -> Dict[str, List[str]]:
    """
    Extract signals from a synthesized signals block with internal sections.
    
    Args:
        text: Synthesized signals section content
    
    Returns:
        Dict with signal lists
    """
    result = {
        "decisions": [],
        "action_items": [],
        "blockers": [],
        "risks": [],
        "ideas": [],
        "key_signals": [],
    }
    
    current_section = None
    
    for line in text.splitlines():
        stripped = line.strip()
        
        if not stripped or stripped in ["🚦", "🧩", "✨", "📝"]:
            continue
        
        # Check for inline section headers
        stripped_lower = stripped.lower()
        if "decision" in stripped_lower and stripped_lower.endswith(":"):
            current_section = "decisions"
            continue
        elif "action" in stripped_lower and stripped_lower.endswith(":"):
            current_section = "action_items"
            continue
        elif "block" in stripped_lower and stripped_lower.endswith(":"):
            current_section = "blockers"
            continue
        elif "risk" in stripped_lower and stripped_lower.endswith(":"):
            current_section = "risks"
            continue
        elif "idea" in stripped_lower and stripped_lower.endswith(":"):
            current_section = "ideas"
            continue
        elif "key" in stripped_lower and "signal" in stripped_lower:
            current_section = "key_signals"
            continue
        
        # Add to current section
        if current_section:
            item = stripped.lstrip("-•*").strip()
            if item and item not in result[current_section]:
                result[current_section].append(item)
    
    return result


def extract_signals_keyword_fallback(text: str) -> Dict[str, List[str]]:
    """
    Keyword-based signal extraction as fallback.
    
    Args:
        text: Meeting text
    
    Returns:
        Dict with extracted signals
    """
    result = {
        "decisions": [],
        "action_items": [],
        "blockers": [],
        "risks": [],
        "ideas": [],
        "key_signals": [],
    }
    
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        
        lower = stripped.lower()
        
        for signal_type, info in SIGNAL_TYPES.items():
            for keyword in info["keywords"]:
                if keyword.lower() in lower:
                    # Map signal type to result key
                    key = signal_type + "s" if not signal_type.endswith("s") else signal_type
                    if key == "action_items":
                        key = "action_items"
                    elif key == "key_signals":
                        key = "key_signals"
                    
                    if key in result and stripped not in result[key]:
                        result[key].append(stripped)
                    break
    
    return result


def parse_ai_signal_response(response: str) -> Dict[str, List[str]]:
    """
    Parse AI response containing extracted signals.
    
    Args:
        response: AI model response text
    
    Returns:
        Dict with signal lists
    """
    result = {
        "decisions": [],
        "action_items": [],
        "blockers": [],
        "risks": [],
        "ideas": [],
        "key_signals": [],
    }
    
    # Try to parse as JSON first
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            for key in result:
                if key in parsed and isinstance(parsed[key], list):
                    result[key] = parsed[key]
            return result
    except json.JSONDecodeError:
        pass
    
    # Fall back to line-by-line parsing
    current_section = None
    for line in response.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        
        # Detect section headers
        if "decision" in lower:
            current_section = "decisions"
        elif "action" in lower:
            current_section = "action_items"
        elif "blocker" in lower:
            current_section = "blockers"
        elif "risk" in lower:
            current_section = "risks"
        elif "idea" in lower:
            current_section = "ideas"
        elif "key" in lower and "signal" in lower:
            current_section = "key_signals"
        elif current_section and stripped.startswith("-"):
            item = stripped.lstrip("-•*").strip()
            if item and item not in result[current_section]:
                result[current_section].append(item)
    
    return result


def merge_signals(
    base: Dict[str, Any],
    additional: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Merge additional signals into base, avoiding duplicates.
    
    Args:
        base: Base signals dict
        additional: Additional signals to merge
    
    Returns:
        Merged signals dict
    """
    for key, items in additional.items():
        if key in base and isinstance(base[key], list):
            for item in items:
                if item not in base[key]:
                    base[key].append(item)
    
    return base


def deduplicate_signals(signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove duplicate and near-duplicate signals.
    
    Args:
        signals: Dict with signal lists
    
    Returns:
        Deduplicated signals
    """
    for key, value in signals.items():
        if isinstance(value, list):
            seen = set()
            unique = []
            for item in value:
                # Normalize for comparison
                normalized = item.lower().strip()
                if normalized not in seen:
                    seen.add(normalized)
                    unique.append(item)
            signals[key] = unique
    
    return signals


def extract_signals_from_meeting(parsed_sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Legacy adapter for backward compatibility.
    """
    return extract_signals_from_sections(parsed_sections)


__all__ = [
    "extract_signals_from_sections",
    "extract_items",
    "extract_from_synthesized",
    "extract_signals_keyword_fallback",
    "parse_ai_signal_response",
    "merge_signals",
    "deduplicate_signals",
    "extract_signals_from_meeting",
]
