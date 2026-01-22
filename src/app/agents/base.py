"""
Base agent class for all AI agents in SignalFlow.
Provides common functionality for agent configuration, tool access, and LLM interactions.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Configuration for an AI agent."""
    
    name: str
    description: str
    primary_model: str = "gpt-4o-mini"
    fallback_model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    system_prompt_file: Optional[str] = None
    tools: List[str] = []  # List of tool names this agent can use
    
    class Config:
        frozen = True


class BaseAgent(ABC):
    """
    Abstract base class for all agents in SignalFlow.
    Handles configuration, tool access, and LLM interactions.
    """
    
    def __init__(self, config: AgentConfig, llm_client=None, tool_registry=None):
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration
            llm_client: LLM client (will default to global if None)
            tool_registry: Tool registry (will default to global if None)
        """
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.interaction_log: List[Dict[str, Any]] = []
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """Execute the agent's primary function."""
        pass
    
    async def ask_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Call the LLM with fallback support.
        
        Args:
            prompt: The prompt to send
            model: Override model (defaults to config.primary_model)
            temperature: Override temperature
            max_tokens: Override max_tokens
        
        Returns:
            LLM response text
        """
        model = model or self.config.primary_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        
        start_time = datetime.now()
        
        try:
            response = await self._call_model(
                model=model,
                system_prompt=self.get_system_prompt(),
                user_prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            # Log interaction
            self._log_interaction(
                model=model,
                prompt_tokens=len(prompt.split()),
                completion_tokens=len(response.split()),
                latency_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                status="success"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Model call failed for {model}: {e}")
            
            # Try fallback model if available
            if self.config.fallback_model:
                logger.info(f"Attempting fallback model: {self.config.fallback_model}")
                try:
                    response = await self._call_model(
                        model=self.config.fallback_model,
                        system_prompt=self.get_system_prompt(),
                        user_prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    
                    self._log_interaction(
                        model=self.config.fallback_model,
                        prompt_tokens=len(prompt.split()),
                        completion_tokens=len(response.split()),
                        latency_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                        status="fallback"
                    )
                    
                    return response
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {fallback_error}")
                    raise
            else:
                raise
    
    async def _call_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Actually call the LLM.
        This will be injected by the agent registry.
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not initialized")
        
        return await self.llm_client.ask(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    def get_available_tools(self) -> List[str]:
        """Get list of tools this agent can use."""
        return self.config.tools
    
    def _log_interaction(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        status: str = "success"
    ):
        """Log an agent interaction for analytics."""
        interaction = {
            "agent_name": self.config.name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        self.interaction_log.append(interaction)
        
        logger.info(
            f"Agent {self.config.name} interaction: {model} | "
            f"Tokens: {completion_tokens} | Latency: {latency_ms}ms"
        )
    
    def get_interaction_log(self) -> List[Dict[str, Any]]:
        """Get all logged interactions for this agent."""
        return self.interaction_log.copy()
