"""
Agents Module - AI agents for SignalFlow.

Clean exports for agent functionality without circular dependencies.
AgentRegistry implementation is in registry.py.
ModelRouter implementation is in model_router.py.
Guardrails implementation is in guardrails.py.

Usage:
    from src.app.agents import get_registry, BaseAgent, AgentConfig
    from src.app.agents import get_model_router, ModelRouter
    from src.app.agents import get_guardrails, Guardrails
    
    registry = get_registry()
    arjuna = registry.get("arjuna")
    
    router = get_model_router()
    model = router.select("classification", agent_name="arjuna")
    
    guardrails = get_guardrails()
    result = guardrails.pre_call("arjuna", user_input)
"""

from typing import Optional
from .base import BaseAgent, AgentConfig
from .registry import AgentRegistry
from .model_router import (
    ModelRouter,
    ModelSelectionResult,
    TaskTypeConfig,
    get_model_router,
    initialize_model_router,
)
from .guardrails import (
    Guardrails,
    GuardrailConfig,
    GuardrailResult,
    GuardrailAction,
    ReflectionResult,
    ReflectionOutcome,
    GuardrailMetrics,
    get_guardrails,
    initialize_guardrails,
)
from .arjuna import (
    ArjunaAgent,
    get_arjuna_agent,
    AVAILABLE_MODELS,
    SYSTEM_PAGES,
    MODEL_ALIASES,
    FOCUS_KEYWORDS,
    # MCP Short Notation Commands
    MCP_COMMANDS,
    MCP_INFERENCE_PATTERNS,
    parse_mcp_command,
    infer_mcp_command,
    get_command_help,
    # Adapter functions for backward compatibility
    get_follow_up_suggestions,
    get_focus_recommendations,
    get_system_context,
    parse_assistant_intent,
    execute_intent,
)
from .career_coach import (
    CareerCoachAgent,
    get_career_coach_agent,
    CAREER_REPO_CAPABILITIES,
    format_capabilities_context,
    # Adapter functions for backward compatibility
    get_career_capabilities,
    career_chat_adapter,
    generate_suggestions_adapter,
    analyze_standup_adapter,
)
import logging

logger = logging.getLogger(__name__)


# Global registry instance (lazy-loaded)
_global_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """
    Get the global agent registry (singleton).
    
    Lazy-initializes on first call. Thread-safe for single-threaded FastAPI.
    
    Returns:
        Global AgentRegistry instance
    
    Example:
        registry = get_registry()
        arjuna = registry.get("arjuna")
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def initialize_registry(config_path: str = "config/agents.yaml") -> AgentRegistry:
    """
    Initialize the global agent registry with custom config path.
    
    Call this at application startup if using non-default config location.
    
    Args:
        config_path: Path to agents.yaml configuration file
    
    Returns:
        Initialized AgentRegistry instance
    
    Example:
        registry = initialize_registry("config/production.yaml")
    """
    global _global_registry
    _global_registry = AgentRegistry(config_path)
    return _global_registry


# Public API
__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentRegistry",
    "get_registry",
    "initialize_registry",
    "ModelRouter",
    "ModelSelectionResult",
    "TaskTypeConfig",
    "get_model_router",
    "initialize_model_router",
    "Guardrails",
    "GuardrailConfig",
    "GuardrailResult",
    "GuardrailAction",
    "ReflectionResult",
    "ReflectionOutcome",
    "GuardrailMetrics",
    "get_guardrails",
    "initialize_guardrails",
    # Arjuna Agent (Checkpoint 2.2)
    "ArjunaAgent",
    "get_arjuna_agent",
    "AVAILABLE_MODELS",
    "SYSTEM_PAGES",
    "MODEL_ALIASES",
    "FOCUS_KEYWORDS",
    # MCP Short Notation Commands
    "MCP_COMMANDS",
    "MCP_INFERENCE_PATTERNS",
    "parse_mcp_command",
    "infer_mcp_command",
    "get_command_help",
    # Arjuna Adapter functions
    "get_follow_up_suggestions",
    "get_focus_recommendations",
    "get_system_context",
    "parse_assistant_intent",
    "execute_intent",
    # Career Coach Agent (Checkpoint 2.3)
    "CareerCoachAgent",
    "get_career_coach_agent",
    "CAREER_REPO_CAPABILITIES",
    "format_capabilities_context",
    # Career Coach Adapter functions
    "get_career_capabilities",
    "career_chat_adapter",
    "generate_suggestions_adapter",
    "analyze_standup_adapter",
]
