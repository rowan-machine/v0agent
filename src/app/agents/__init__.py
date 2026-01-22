"""
Agents Module - AI agents for SignalFlow.

Clean exports for agent functionality without circular dependencies.
AgentRegistry implementation is in registry.py.
ModelRouter implementation is in model_router.py.

Usage:
    from src.app.agents import get_registry, BaseAgent, AgentConfig
    from src.app.agents import get_model_router, ModelRouter
    
    registry = get_registry()
    arjuna = registry.get("arjuna")
    
    router = get_model_router()
    model = router.select("classification", agent_name="arjuna")
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
]
