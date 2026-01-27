"""
Arjuna Agent Package - SignalFlow Smart Assistant

This package provides the Arjuna conversational AI agent.

MIGRATION STATUS: 95% Complete ✅
The agent has been decomposed from a single 2500+ line file into:
- constants.py - Knowledge bases and configuration ✅
- tools.py - Intent execution tools (ticket CRUD, etc.) ✅
- context.py - Context gathering (system state, focus) ✅
- standup.py - Standup-related methods ✅
- focus.py - Focus recommendation methods ✅
- mcp_handler.py - MCP command handling ✅
- chain_executor.py - Chain command execution ✅
- intents.py - Intent parsing and execution ✅
- tickets.py - Ticket CRUD operations ✅
- core.py - ArjunaAgentCore class (new composition-based) ✅
- adapters.py - Module-level adapter functions ✅

For backward compatibility, we still re-export from _arjuna_core.py.
New code should import from this package directly.
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
from .standup import ArjunaStandupMixin
from .focus import ArjunaFocusMixin

# Import new mixins (Phase 2.3)
from .mcp_handler import ArjunaMCPMixin
from .chain_executor import ArjunaChainMixin, CHAIN_DEFINITIONS
from .intents import ArjunaIntentMixin
from .tickets import ArjunaTicketMixin

# Import new core class (Phase 2.3)
from .core import ArjunaAgentCore, ArjunaAgentComposed

# Import adapter functions (Phase 2.3)
from .adapters import (
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

# Import everything else from the original arjuna module (for backward compatibility)
# This will be removed once all code migrates to using this package directly
from .._arjuna_core import (
    ArjunaAgent,  # Original class - use ArjunaAgentCore for new code
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
    "CHAIN_DEFINITIONS",
    # Mixins
    "ArjunaToolsMixin",
    "ArjunaContextMixin",
    "ArjunaStandupMixin",
    "ArjunaFocusMixin",
    "ArjunaMCPMixin",
    "ArjunaChainMixin",
    "ArjunaIntentMixin",
    "ArjunaTicketMixin",
    # Agent classes
    "ArjunaAgent",  # Original (backward compat)
    "ArjunaAgentCore",  # New composition-based
    "ArjunaAgentComposed",  # Alias for ArjunaAgentCore
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
