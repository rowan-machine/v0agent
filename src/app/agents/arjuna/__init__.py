"""
Arjuna Agent Package - SignalFlow Smart Assistant

This package provides the Arjuna conversational AI agent.

MIGRATION STATUS:
The agent is being decomposed from a single 2500+ line file into:
- constants.py - Knowledge bases and configuration ✅
- tools.py - Intent execution tools (ticket CRUD, etc.) ✅
- context.py - Context gathering (system state, focus) ✅
- core.py - ArjunaAgent class (future)
- standup.py - Standup-related methods (future)
- adapters.py - Module-level adapter functions (future)

For now, we re-export from the original module to maintain compatibility.
"""

# Import constants from the new location
from .constants import (
    AVAILABLE_MODELS,
    SYSTEM_PAGES,
    MODEL_ALIASES,
    FOCUS_KEYWORDS,
)

# Import mixins (for use in agent composition)
from .tools import ArjunaToolsMixin
from .context import ArjunaContextMixin

# Import everything else from the original arjuna module (renamed to avoid circular import)
from .._arjuna_core import (
    ArjunaAgent,
    SimpleLLMClient,
    get_arjuna_agent,
    get_follow_up_suggestions,
    get_focus_recommendations,
    get_system_context,
    parse_assistant_intent,
    execute_intent,
    quick_ask,
    quick_ask_sync,
    interpret_user_status_adapter,
)

# MCP commands (already extracted)
from ...mcp.commands import MCP_COMMANDS, MCP_INFERENCE_PATTERNS
from ...mcp.command_parser import parse_mcp_command, infer_mcp_command, get_command_help

__all__ = [
    # Constants
    "AVAILABLE_MODELS",
    "SYSTEM_PAGES", 
    "MODEL_ALIASES",
    "FOCUS_KEYWORDS",
    # Mixins
    "ArjunaToolsMixin",
    "ArjunaContextMixin",
    # Agent
    "ArjunaAgent",
    "SimpleLLMClient",
    "get_arjuna_agent",
    # Adapter functions
    "get_follow_up_suggestions",
    "get_focus_recommendations",
    "get_system_context",
    "parse_assistant_intent",
    "execute_intent",
    "quick_ask",
    "quick_ask_sync",
    "interpret_user_status_adapter",
    # MCP commands
    "MCP_COMMANDS",
    "MCP_INFERENCE_PATTERNS",
    "parse_mcp_command",
    "infer_mcp_command",
    "get_command_help",
]
