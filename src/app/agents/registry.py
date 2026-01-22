"""
Agent Registry - Central management of all AI agents in SignalFlow.
Handles agent registration, configuration loading, and instantiation.

This module contains the AgentRegistry class which manages agent lifecycle,
configuration, and dependency injection including the ModelRouter and Guardrails.
"""

from typing import Dict, Type, Optional, Any
from .base import BaseAgent, AgentConfig
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Central registry for all AI agents.
    Handles agent configuration, registration, and lifecycle.
    
    Key responsibilities:
    - Load and manage agent configurations from YAML
    - Register agent classes
    - Create and cache agent instances (singleton per agent)
    - Manage dependencies (LLM client, tool registry, model router, guardrails)
    - Support hot-reloading configurations in development
    """
    
    def __init__(self, config_path: str = "config/agents.yaml"):
        """
        Initialize the agent registry.
        
        Args:
            config_path: Path to agents.yaml configuration file
        """
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_classes: Dict[str, Type[BaseAgent]] = {}
        self.configs: Dict[str, AgentConfig] = {}
        self.config_path = Path(config_path)
        self.llm_client = None
        self.tool_registry = None
        self.model_router = None
        self.guardrails = None
        
        self._load_configurations()
        self._init_model_router()
        self._init_guardrails()
    
    def _load_configurations(self):
        """
        Load agent configurations from YAML file.
        
        Expected YAML structure:
        ```yaml
        agents:
          arjuna:
            model: gpt-4o-mini
            temperature: 0.7
            system_prompt_path: prompts/agents/arjuna/system.jinja2
          career_coach:
            model: gpt-4o
            temperature: 0.5
        ```
        """
        if not self.config_path.exists():
            logger.warning(f"Agent config file not found: {self.config_path}")
            return
        
        try:
            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f)
            
            if not config_data or "agents" not in config_data:
                logger.warning("No agents section in config file")
                return
            
            for agent_name, agent_config in config_data["agents"].items():
                try:
                    self.configs[agent_name] = AgentConfig(
                        name=agent_name,
                        **agent_config
                    )
                    logger.info(f"Loaded config for agent: {agent_name}")
                except Exception as e:
                    logger.error(f"Failed to load config for {agent_name}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to load agent configurations: {e}")
    
    def _init_model_router(self):
        """Initialize the model router with policy from config directory."""
        try:
            from .model_router import ModelRouter
            
            # Look for routing policy in same directory as agent config
            policy_path = self.config_path.parent / "model_routing.yaml"
            if policy_path.exists():
                self.model_router = ModelRouter(str(policy_path))
                logger.info(f"Model router initialized from {policy_path}")
            else:
                self.model_router = ModelRouter()  # Use embedded default
                logger.info("Model router initialized with embedded default policy")
        except Exception as e:
            logger.warning(f"Failed to initialize model router: {e}")
    
    def _init_guardrails(self):
        """Initialize guardrails with config from config directory (Checkpoint 1.8)."""
        try:
            from .guardrails import Guardrails
            
            # Look for guardrails config in same directory as agent config
            guardrails_path = self.config_path.parent / "guardrails.yaml"
            if guardrails_path.exists():
                self.guardrails = Guardrails(str(guardrails_path))
                logger.info(f"Guardrails initialized from {guardrails_path}")
            else:
                self.guardrails = Guardrails()  # Use embedded default
                logger.info("Guardrails initialized with embedded default config")
        except Exception as e:
            logger.warning(f"Failed to initialize guardrails: {e}")
    
    def register(self, agent_class: Type[BaseAgent]):
        """
        Register an agent class.
        
        This should be called at startup for each agent that will be used.
        
        Example:
        ```python
        registry = get_registry()
        registry.register(ArjunaAgent)
        registry.register(CareerCoachAgent)
        ```
        
        Args:
            agent_class: Agent class to register (must inherit from BaseAgent)
        """
        agent_name = agent_class.__name__.lower()
        self.agent_classes[agent_name] = agent_class
        logger.info(f"Registered agent class: {agent_name}")
    
    def create(self, agent_name: str) -> BaseAgent:
        """
        Create an agent instance.
        
        Instances are cached (singleton pattern per agent).
        Subsequent calls to create(name) return the same instance.
        
        Args:
            agent_name: Name of the agent to create
        
        Returns:
            Instantiated agent
        
        Raises:
            ValueError: If agent class not registered or config not found
        """
        # Return cached instance if exists
        if agent_name in self.agents:
            return self.agents[agent_name]
        
        if agent_name not in self.agent_classes:
            raise ValueError(f"Agent class not registered: {agent_name}")
        
        if agent_name not in self.configs:
            raise ValueError(f"Agent configuration not found: {agent_name}")
        
        agent_class = self.agent_classes[agent_name]
        config = self.configs[agent_name]
        
        agent = agent_class(
            config=config,
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
            model_router=self.model_router,
            guardrails=self.guardrails,
        )
        
        self.agents[agent_name] = agent
        logger.info(f"Created agent instance: {agent_name}")
        
        return agent
    
    def get(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get an agent instance (creates if doesn't exist).
        
        Convenience wrapper around create() that handles errors gracefully.
        
        Args:
            agent_name: Name of the agent
        
        Returns:
            Agent instance or None if creation failed
        """
        try:
            return self.create(agent_name)
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to get agent {agent_name}: {e}")
            return None
    
    def set_llm_client(self, llm_client: Any):
        """
        Set the LLM client for all agents (dependency injection).
        
        Args:
            llm_client: LLM client instance (e.g., OpenAI client)
        """
        self.llm_client = llm_client
        for agent in self.agents.values():
            agent.llm_client = llm_client
    
    def set_tool_registry(self, tool_registry: Any):
        """
        Set the tool registry for all agents (dependency injection).
        
        Args:
            tool_registry: Tool registry instance
        """
        self.tool_registry = tool_registry
        for agent in self.agents.values():
            agent.tool_registry = tool_registry
    
    def set_model_router(self, model_router: Any):
        """
        Set the model router for all agents (dependency injection).
        
        Args:
            model_router: ModelRouter instance
        """
        self.model_router = model_router
        for agent in self.agents.values():
            agent.model_router = model_router
    
    def set_guardrails(self, guardrails: Any):
        """
        Set the guardrails for all agents (dependency injection).
        
        Args:
            guardrails: Guardrails instance (Checkpoint 1.8)
        """
        self.guardrails = guardrails
        for agent in self.agents.values():
            agent.guardrails = guardrails
    
    def get_model_router(self):
        """Get the current model router."""
        return self.model_router
    
    def get_guardrails(self):
        """Get the current guardrails instance."""
        return self.guardrails
    
    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered agents and their configs.
        
        Returns:
            Dictionary of agent info with structure:
            {
                "arjuna": {
                    "config": {...},
                    "instantiated": true
                },
                ...
            }
        """
        return {
            name: {
                "config": self.configs[name].dict() if name in self.configs else {},
                "instantiated": name in self.agents,
            }
            for name in self.agent_classes.keys()
        }
    
    def reload_configurations(self):
        """
        Reload configurations from file.
        
        Useful for hot-reloading in development without restarting server.
        Note: Does not affect already-instantiated agents.
        """
        self.configs.clear()
        self._load_configurations()
        
        # Also reload model router policy
        if self.model_router:
            self.model_router.reload_policy()
        
        # Also reload guardrails config
        if self.guardrails:
            self.guardrails.reload_config()
        
        logger.info("Agent configurations, model routing policy, and guardrails reloaded")
