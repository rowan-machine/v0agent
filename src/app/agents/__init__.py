"""
Agent Registry - Central management of all AI agents in SignalFlow.
Handles agent registration, configuration loading, and instantiation.
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
        
        self._load_configurations()
    
    def _load_configurations(self):
        """Load agent configurations from YAML file."""
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
    
    def register(self, agent_class: Type[BaseAgent]):
        """
        Register an agent class.
        
        Args:
            agent_class: Agent class to register
        """
        agent_name = agent_class.__name__.lower()
        self.agent_classes[agent_name] = agent_class
        logger.info(f"Registered agent class: {agent_name}")
    
    def create(self, agent_name: str) -> BaseAgent:
        """
        Create an agent instance.
        
        Args:
            agent_name: Name of the agent to create
        
        Returns:
            Instantiated agent
        """
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
        )
        
        self.agents[agent_name] = agent
        logger.info(f"Created agent instance: {agent_name}")
        
        return agent
    
    def get(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get an agent instance (creates if doesn't exist).
        
        Args:
            agent_name: Name of the agent
        
        Returns:
            Agent instance or None
        """
        try:
            return self.create(agent_name)
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to get agent {agent_name}: {e}")
            return None
    
    def set_llm_client(self, llm_client: Any):
        """Set the LLM client for all agents."""
        self.llm_client = llm_client
        for agent in self.agents.values():
            agent.llm_client = llm_client
    
    def set_tool_registry(self, tool_registry: Any):
        """Set the tool registry for all agents."""
        self.tool_registry = tool_registry
        for agent in self.agents.values():
            agent.tool_registry = tool_registry
    
    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered agents and their configs.
        
        Returns:
            Dictionary of agent info
        """
        return {
            name: {
                "config": self.configs[name].dict() if name in self.configs else {},
                "instantiated": name in self.agents,
            }
            for name in self.agent_classes.keys()
        }
    
    def reload_configurations(self):
        """Reload configurations from file (useful for hot-reloading in development)."""
        self.configs.clear()
        self._load_configurations()
        logger.info("Agent configurations reloaded")


# Global registry instance
_global_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def initialize_registry(config_path: str = "config/agents.yaml") -> AgentRegistry:
    """Initialize the global agent registry."""
    global _global_registry
    _global_registry = AgentRegistry(config_path)
    return _global_registry
