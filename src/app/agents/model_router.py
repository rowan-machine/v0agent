"""
Model Router - Auto-selection of LLM models per task type with user override.

Implements checkpoint 1.7 from PHASED_MIGRATION_ROLLOUT.md:
- Lightweight router with clear defaults (small for classification, larger for synthesis)
- Deterministic fallback chain
- User override via config or explicit param
- Declarative routing policy (YAML) for future LangChain/LangGraph swap

Usage:
    router = get_model_router()
    model = router.select("classification", agent_name="arjuna")
    model = router.select("synthesis", override="gpt-4o")  # User override
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import logging
import yaml

logger = logging.getLogger(__name__)


@dataclass
class ModelSelectionResult:
    """Result of model selection with metadata for observability."""
    model: str
    task_type: str
    agent_name: Optional[str]
    selection_reason: str
    fallback_used: bool = False
    override_applied: bool = False
    latency_budget_ms: Optional[int] = None
    cost_tier: str = "standard"  # "low", "standard", "premium"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TaskTypeConfig:
    """Configuration for a task type's model selection."""
    default_model: str
    fallback_models: List[str] = field(default_factory=list)
    latency_budget_ms: int = 5000
    max_tokens: int = 1000
    cost_tier: str = "standard"
    description: str = ""


# Default routing policy embedded for zero-config startup
DEFAULT_ROUTING_POLICY = {
    "version": "1.0",
    "description": "Model routing policy for SignalFlow agents",
    
    # Task type → model mapping
    "task_types": {
        # Fast, cheap tasks
        "classification": {
            "default_model": "gpt-4o-mini",
            "fallback_models": ["gpt-3.5-turbo"],
            "latency_budget_ms": 2000,
            "max_tokens": 500,
            "cost_tier": "low",
            "description": "Intent classification, routing, simple parsing"
        },
        "routing": {
            "default_model": "gpt-4o-mini",
            "fallback_models": ["gpt-3.5-turbo"],
            "latency_budget_ms": 1500,
            "max_tokens": 300,
            "cost_tier": "low",
            "description": "Agent routing, query classification"
        },
        "parsing": {
            "default_model": "gpt-4o-mini",
            "fallback_models": ["gpt-3.5-turbo"],
            "latency_budget_ms": 2000,
            "max_tokens": 500,
            "cost_tier": "low",
            "description": "Structured extraction, JSON parsing"
        },
        
        # Medium complexity
        "summarization": {
            "default_model": "gpt-4o-mini",
            "fallback_models": ["gpt-3.5-turbo"],
            "latency_budget_ms": 5000,
            "max_tokens": 1000,
            "cost_tier": "standard",
            "description": "Meeting summaries, document summaries"
        },
        "extraction": {
            "default_model": "gpt-4o-mini",
            "fallback_models": ["gpt-3.5-turbo"],
            "latency_budget_ms": 5000,
            "max_tokens": 1500,
            "cost_tier": "standard",
            "description": "Signal extraction, entity extraction"
        },
        "conversation": {
            "default_model": "gpt-4o-mini",
            "fallback_models": ["gpt-3.5-turbo"],
            "latency_budget_ms": 4000,
            "max_tokens": 1000,
            "cost_tier": "standard",
            "description": "Chat responses, Q&A"
        },
        
        # High complexity - larger models
        "synthesis": {
            "default_model": "gpt-4o",
            "fallback_models": ["gpt-4o-mini", "gpt-3.5-turbo"],
            "latency_budget_ms": 15000,
            "max_tokens": 2000,
            "cost_tier": "premium",
            "description": "DIKW synthesis, knowledge graph updates, complex reasoning"
        },
        "analysis": {
            "default_model": "gpt-4o",
            "fallback_models": ["gpt-4o-mini"],
            "latency_budget_ms": 10000,
            "max_tokens": 2000,
            "cost_tier": "premium",
            "description": "Deep analysis, career insights, pattern detection"
        },
        "long_context": {
            "default_model": "gpt-4o",
            "fallback_models": ["gpt-4o-mini"],
            "latency_budget_ms": 20000,
            "max_tokens": 4000,
            "cost_tier": "premium",
            "description": "Multi-document synthesis, meeting bundles"
        },
        
        # Vision tasks
        "vision": {
            "default_model": "gpt-4o",
            "fallback_models": [],
            "latency_budget_ms": 10000,
            "max_tokens": 1000,
            "cost_tier": "premium",
            "description": "Image analysis, screenshot extraction"
        },
    },
    
    # Agent → default task type mapping
    "agent_defaults": {
        "arjuna": "conversation",
        "career_coach": "analysis",
        "meeting_analyzer": "extraction",
        "dikw_synthesizer": "synthesis",
    },
    
    # Global fallback if task type unknown
    "global_fallback": {
        "model": "gpt-4o-mini",
        "reason": "Unknown task type, using global fallback"
    },
}


class ModelRouter:
    """
    Model router with declarative policy and user override support.
    
    Selection priority:
    1. Explicit override parameter (user request)
    2. Agent-specific override in config
    3. Task type default from policy
    4. Agent default task type
    5. Global fallback
    """
    
    def __init__(self, policy_path: Optional[str] = None):
        """
        Initialize the model router.
        
        Args:
            policy_path: Path to routing policy YAML (uses embedded default if None)
        """
        self.policy = self._load_policy(policy_path)
        self.task_configs: Dict[str, TaskTypeConfig] = {}
        self.selection_log: List[ModelSelectionResult] = []
        self._parse_policy()
        
        logger.info(f"ModelRouter initialized with {len(self.task_configs)} task types")
    
    def _load_policy(self, policy_path: Optional[str]) -> Dict[str, Any]:
        """Load routing policy from YAML or use embedded default."""
        if policy_path and Path(policy_path).exists():
            try:
                with open(policy_path, "r") as f:
                    policy = yaml.safe_load(f)
                logger.info(f"Loaded routing policy from {policy_path}")
                return policy
            except Exception as e:
                logger.warning(f"Failed to load policy from {policy_path}: {e}, using default")
        
        return DEFAULT_ROUTING_POLICY.copy()
    
    def _parse_policy(self):
        """Parse policy into TaskTypeConfig objects."""
        for task_type, config in self.policy.get("task_types", {}).items():
            self.task_configs[task_type] = TaskTypeConfig(
                default_model=config.get("default_model", "gpt-4o-mini"),
                fallback_models=config.get("fallback_models", []),
                latency_budget_ms=config.get("latency_budget_ms", 5000),
                max_tokens=config.get("max_tokens", 1000),
                cost_tier=config.get("cost_tier", "standard"),
                description=config.get("description", ""),
            )
    
    def select(
        self,
        task_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        override: Optional[str] = None,
        agent_config_override: Optional[str] = None,
    ) -> ModelSelectionResult:
        """
        Select the appropriate model for a task.
        
        Priority:
        1. override (explicit user request)
        2. agent_config_override (from agent's config file)
        3. task_type default
        4. agent's default task type
        5. global fallback
        
        Args:
            task_type: Type of task (classification, synthesis, etc.)
            agent_name: Name of the agent making the request
            override: Explicit model override from user
            agent_config_override: Model override from agent config
        
        Returns:
            ModelSelectionResult with selected model and metadata
        """
        # Priority 1: Explicit override
        if override:
            result = ModelSelectionResult(
                model=override,
                task_type=task_type or "unknown",
                agent_name=agent_name,
                selection_reason="explicit_override",
                override_applied=True,
            )
            self._log_selection(result)
            return result
        
        # Priority 2: Agent config override
        if agent_config_override:
            result = ModelSelectionResult(
                model=agent_config_override,
                task_type=task_type or "unknown",
                agent_name=agent_name,
                selection_reason="agent_config_override",
                override_applied=True,
            )
            self._log_selection(result)
            return result
        
        # Priority 3: Task type default
        if task_type and task_type in self.task_configs:
            config = self.task_configs[task_type]
            result = ModelSelectionResult(
                model=config.default_model,
                task_type=task_type,
                agent_name=agent_name,
                selection_reason="task_type_default",
                latency_budget_ms=config.latency_budget_ms,
                cost_tier=config.cost_tier,
            )
            self._log_selection(result)
            return result
        
        # Priority 4: Agent default task type
        if agent_name:
            agent_defaults = self.policy.get("agent_defaults", {})
            if agent_name in agent_defaults:
                default_task = agent_defaults[agent_name]
                if default_task in self.task_configs:
                    config = self.task_configs[default_task]
                    result = ModelSelectionResult(
                        model=config.default_model,
                        task_type=default_task,
                        agent_name=agent_name,
                        selection_reason="agent_default_task_type",
                        latency_budget_ms=config.latency_budget_ms,
                        cost_tier=config.cost_tier,
                    )
                    self._log_selection(result)
                    return result
        
        # Priority 5: Global fallback
        fallback = self.policy.get("global_fallback", {})
        result = ModelSelectionResult(
            model=fallback.get("model", "gpt-4o-mini"),
            task_type=task_type or "unknown",
            agent_name=agent_name,
            selection_reason=fallback.get("reason", "global_fallback"),
            fallback_used=True,
        )
        self._log_selection(result)
        return result
    
    def get_fallback_chain(self, task_type: str) -> List[str]:
        """
        Get the fallback chain for a task type.
        
        Returns:
            List of models in fallback order [primary, fallback1, fallback2, ...]
        """
        if task_type not in self.task_configs:
            fallback = self.policy.get("global_fallback", {})
            return [fallback.get("model", "gpt-4o-mini")]
        
        config = self.task_configs[task_type]
        return [config.default_model] + config.fallback_models
    
    def get_task_config(self, task_type: str) -> Optional[TaskTypeConfig]:
        """Get configuration for a task type."""
        return self.task_configs.get(task_type)
    
    def list_task_types(self) -> Dict[str, str]:
        """List all task types with descriptions."""
        return {
            name: config.description
            for name, config in self.task_configs.items()
        }
    
    def _log_selection(self, result: ModelSelectionResult):
        """Log model selection for observability."""
        self.selection_log.append(result)
        
        # Keep only last 1000 selections in memory
        if len(self.selection_log) > 1000:
            self.selection_log = self.selection_log[-1000:]
        
        logger.info(
            f"Model selected: {result.model} | "
            f"task={result.task_type} | "
            f"agent={result.agent_name or 'none'} | "
            f"reason={result.selection_reason}"
        )
    
    def get_selection_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """
        Get model selection statistics for observability.
        
        Args:
            minutes: Time window in minutes
        
        Returns:
            Statistics dictionary
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(minutes=minutes)
        cutoff_str = cutoff.isoformat()
        
        recent = [s for s in self.selection_log if s.timestamp > cutoff_str]
        
        if not recent:
            return {"total": 0, "by_model": {}, "by_task_type": {}, "overrides": 0}
        
        by_model: Dict[str, int] = {}
        by_task_type: Dict[str, int] = {}
        overrides = 0
        fallbacks = 0
        
        for s in recent:
            by_model[s.model] = by_model.get(s.model, 0) + 1
            by_task_type[s.task_type] = by_task_type.get(s.task_type, 0) + 1
            if s.override_applied:
                overrides += 1
            if s.fallback_used:
                fallbacks += 1
        
        return {
            "total": len(recent),
            "by_model": by_model,
            "by_task_type": by_task_type,
            "overrides": overrides,
            "fallbacks": fallbacks,
            "override_rate": overrides / len(recent) if recent else 0,
            "fallback_rate": fallbacks / len(recent) if recent else 0,
        }
    
    def reload_policy(self, policy_path: Optional[str] = None):
        """
        Reload routing policy from file.
        
        Useful for hot-reloading in development.
        """
        self.policy = self._load_policy(policy_path)
        self._parse_policy()
        logger.info("Model routing policy reloaded")


# Global router instance (lazy-loaded singleton)
_global_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """
    Get the global model router (singleton).
    
    Returns:
        Global ModelRouter instance
    """
    global _global_router
    if _global_router is None:
        _global_router = ModelRouter()
    return _global_router


def initialize_model_router(policy_path: Optional[str] = None) -> ModelRouter:
    """
    Initialize the global model router with custom policy.
    
    Call at application startup if using custom policy file.
    
    Args:
        policy_path: Path to routing policy YAML
    
    Returns:
        Initialized ModelRouter instance
    """
    global _global_router
    _global_router = ModelRouter(policy_path)
    return _global_router
