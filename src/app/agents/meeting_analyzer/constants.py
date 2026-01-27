# src/app/agents/meeting_analyzer/constants.py
"""
Meeting Analyzer Constants

Defines signal types, heading patterns, and mappings for meeting analysis.
"""

from typing import Dict, List

# =============================================================================
# SIGNAL TYPES AND CATEGORIES
# =============================================================================

SIGNAL_TYPES: Dict[str, Dict] = {
    "decision": {
        "keywords": ["decided", "agreed", "finalized", "approved", "confirmed", "committed to"],
        "emoji": "✅",
        "dikw_level": "information",
    },
    "action_item": {
        "keywords": ["will", "needs to", "should", "must", "action:", "todo:", "task:"],
        "emoji": "📋",
        "dikw_level": "data",
    },
    "blocker": {
        "keywords": ["blocked", "waiting on", "depends on", "can't proceed", "impediment"],
        "emoji": "🚫",
        "dikw_level": "data",
    },
    "risk": {
        "keywords": ["risk", "concern", "might", "could fail", "uncertain", "unsure"],
        "emoji": "⚠️",
        "dikw_level": "information",
    },
    "idea": {
        "keywords": ["idea:", "suggestion:", "could we", "what if", "maybe we should"],
        "emoji": "💡",
        "dikw_level": "data",
    },
    "key_signal": {
        "keywords": ["key insight", "important", "critical", "main takeaway"],
        "emoji": "🔑",
        "dikw_level": "knowledge",
    },
}


# =============================================================================
# ADAPTIVE HEADING PATTERNS
# Supports multiple summary formats: Teams, Pocket, manual, etc.
# =============================================================================

HEADING_PATTERNS: Dict[str, str] = {
    # Standard markdown headers
    "markdown_h1": r"^#\s+(.+)$",
    "markdown_h2": r"^##\s+(.+)$",
    "markdown_h3": r"^###\s+(.+)$",
    # Bold text as headers
    "bold": r"^\*\*(.+?)\*\*\s*:?\s*$",
    # Colon-terminated headers
    "colon": r"^([A-Za-z][A-Za-z\s/]+):\s*$",
    # Emoji-prefixed headers
    "emoji": r"^([\U0001F300-\U0001F9FF])\s*(.+)$",
}

# Map common heading variations to canonical signal types
HEADING_TO_SIGNAL_TYPE: Dict[str, str] = {
    # Decisions
    "decision": "decision",
    "decisions": "decision",
    "agreed": "decision",
    "confirmed": "decision",
    "approved": "decision",
    # Actions
    "action": "action_item",
    "actions": "action_item",
    "action item": "action_item",
    "action items": "action_item",
    "tasks": "action_item",
    "todo": "action_item",
    "next steps": "action_item",
    "commitments": "action_item",
    "work identified": "action_item",
    # Blockers
    "blocker": "blocker",
    "blockers": "blocker",
    "blocked": "blocker",
    "impediments": "blocker",
    # Risks
    "risk": "risk",
    "risks": "risk",
    "concerns": "risk",
    "risks / open questions": "risk",
    "open questions": "risk",
    # Ideas
    "idea": "idea",
    "ideas": "idea",
    "suggestions": "idea",
    "proposals": "idea",
    # Key signals
    "key signal": "key_signal",
    "key signals": "key_signal",
    "insights": "key_signal",
    "takeaways": "key_signal",
    "outcomes": "key_signal",
    # Context/Notes (not signals, but useful metadata)
    "context": "context",
    "background": "context",
    "notes": "notes",
    "summary": "summary",
    "synthesized signals": "synthesized",
}


# Empty signals template
EMPTY_SIGNALS: Dict[str, List] = {
    "decisions": [],
    "action_items": [],
    "blockers": [],
    "risks": [],
    "ideas": [],
    "key_signals": [],
    "context": "",
    "notes": "",
}


__all__ = [
    "SIGNAL_TYPES",
    "HEADING_PATTERNS",
    "HEADING_TO_SIGNAL_TYPE",
    "EMPTY_SIGNALS",
]
