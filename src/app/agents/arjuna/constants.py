"""
Arjuna Agent Constants - Knowledge bases and configuration.

Extracted from arjuna.py for better maintainability.
"""

from typing import Dict, List, Any

# Available AI models
AVAILABLE_MODELS: List[str] = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
    "claude-sonnet-4",
    "claude-opus-4",
]

# System pages for navigation
SYSTEM_PAGES: Dict[str, Dict[str, str]] = {
    "dashboard": {
        "path": "/",
        "title": "Dashboard",
        "description": "Overview of sprint progress, workflow modes, and quick actions"
    },
    "tickets": {
        "path": "/tickets",
        "title": "Tickets",
        "description": "Manage tasks and work items with kanban board"
    },
    "signals": {
        "path": "/signals",
        "title": "Signals",
        "description": "Review extracted insights from meetings (decisions, actions, blockers)"
    },
    "dikw": {
        "path": "/dikw",
        "title": "DIKW Pyramid",
        "description": "Knowledge hierarchy - promote signals through Data→Info→Knowledge→Wisdom"
    },
    "meetings": {
        "path": "/meetings",
        "title": "Meetings",
        "description": "View and analyze meeting summaries and extracted signals"
    },
    "documents": {
        "path": "/documents",
        "title": "Documents",
        "description": "Documentation and knowledge base"
    },
    "career": {
        "path": "/career",
        "title": "Career Hub",
        "description": "Career development tracking, feedback, and growth planning"
    },
    "accountability": {
        "path": "/accountability",
        "title": "Accountability",
        "description": "Track waiting-for items and dependencies on others"
    },
    "workflow": {
        "path": "/workflow",
        "title": "Workflow Modes",
        "description": "Navigate through 7 workflow stages from ideation to execution"
    },
    "sprint": {
        "path": "/sprint",
        "title": "Sprint Settings",
        "description": "Configure sprint parameters and goals"
    },
    "search": {
        "path": "/search",
        "title": "Search",
        "description": "Semantic search across all content"
    },
    "query": {
        "path": "/query",
        "title": "Query",
        "description": "Ask questions about your data"
    },
}

# Model name normalization map
MODEL_ALIASES: Dict[str, str] = {
    "gpt4": "gpt-4o",
    "gpt-4": "gpt-4o",
    "gpt4o": "gpt-4o",
    "gpt-4o": "gpt-4o",
    "gpt4omini": "gpt-4o-mini",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt4mini": "gpt-4o-mini",
    "mini": "gpt-4o-mini",
    "gpt4turbo": "gpt-4-turbo",
    "gpt-4-turbo": "gpt-4-turbo",
    "turbo": "gpt-4-turbo",
    "gpt35": "gpt-3.5-turbo",
    "gpt-3.5": "gpt-3.5-turbo",
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "claude": "claude-3-sonnet",
    "claude3": "claude-3-sonnet",
    "claudesonnet": "claude-3-sonnet",
    "claude-3-sonnet": "claude-3-sonnet",
    "sonnet": "claude-3-sonnet",
    "claudeopus": "claude-3-opus",
    "claude-3-opus": "claude-3-opus",
    "opus": "claude-3-opus",
    "claudehaiku": "claude-3-haiku",
    "claude-3-haiku": "claude-3-haiku",
    "haiku": "claude-3-haiku",
    "claude-sonnet-4": "claude-sonnet-4",
    "sonnet4": "claude-sonnet-4",
    "claude-opus-4": "claude-opus-4",
    "opus4": "claude-opus-4",
}

# Focus query keywords
FOCUS_KEYWORDS: List[str] = [
    'focus', 'should i do', 'what next', 'prioritize', 
    'work on today', 'start with'
]

__all__ = [
    "AVAILABLE_MODELS",
    "SYSTEM_PAGES",
    "MODEL_ALIASES",
    "FOCUS_KEYWORDS",
]
