"""
Base agent class for all AI agents in SignalFlow.
Provides common functionality for agent configuration, tool access, and LLM interactions.
Integrates with ModelRouter for automatic model selection per task type.
Integrates with Guardrails for pre/post call safety and reflection (Checkpoint 1.8).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel
from datetime import datetime
import logging

if TYPE_CHECKING:
    from .guardrails import Guardrails

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Configuration for an AI agent."""
    
    name: str
    description: str
    primary_model: str = "gpt-4o-mini"
    fallback_model: Optional[str] = None
    model_override: Optional[str] = None  # User override for this agent
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
    Integrates with ModelRouter for automatic model selection.
    Integrates with Guardrails for pre/post call hooks (safety, reflection).
    """
    
    def __init__(
        self,
        config: AgentConfig,
        llm_client=None,
        tool_registry=None,
        model_router=None,
        guardrails: Optional["Guardrails"] = None,
    ):
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration
            llm_client: LLM client (will default to global if None)
            tool_registry: Tool registry (will default to global if None)
            model_router: Model router for auto-selection (will default to global if None)
            guardrails: Guardrails instance for pre/post hooks (will default to global if None)
        """
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.model_router = model_router
        self.guardrails = guardrails
        self.interaction_log: List[Dict[str, Any]] = []
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """Execute the agent's primary function."""
        pass
    
    def select_model(
        self,
        task_type: Optional[str] = None,
        override: Optional[str] = None,
    ) -> str:
        """
        Select the appropriate model for a task using the router.
        
        Priority:
        1. Explicit override parameter
        2. Agent config model_override
        3. Router selection based on task_type
        4. Agent's primary_model (legacy fallback)
        
        Args:
            task_type: Type of task (classification, synthesis, etc.)
            override: Explicit model override
        
        Returns:
            Selected model name
        """
        # Use router if available
        if self.model_router:
            from .model_router import get_model_router
            router = self.model_router or get_model_router()
            
            result = router.select(
                task_type=task_type,
                agent_name=self.config.name,
                override=override,
                agent_config_override=self.config.model_override,
            )
            return result.model
        
        # Legacy fallback: use override or config primary_model
        return override or self.config.model_override or self.config.primary_model
    
    async def ask_llm(
        self,
        prompt: str,
        task_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        skip_guardrails: bool = False,
    ) -> str:
        """
        Call the LLM with automatic model selection, fallback support, and guardrails.
        
        Guardrails hooks (Checkpoint 1.8):
        - pre_call: Input filtering, safety checks before LLM call
        - post_call: Self-reflection, hallucination detection after response
        
        Args:
            prompt: The prompt to send
            task_type: Type of task for model routing (classification, synthesis, etc.)
            model: Override model (bypasses router)
            temperature: Override temperature
            max_tokens: Override max_tokens
            context: Optional context for guardrails (e.g., source documents)
            skip_guardrails: Bypass guardrails for internal reflection calls
        
        Returns:
            LLM response text
        
        Raises:
            GuardrailBlockedError: If pre-call guardrails block the request
        """
        # Select model using router or override
        selected_model = self.select_model(task_type=task_type, override=model)
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        
        # === PRE-CALL GUARDRAILS ===
        if not skip_guardrails and self.guardrails:
            pre_result = await self.guardrails.pre_call(
                input_text=prompt,
                agent_name=self.config.name,
                context=context,
            )
            
            if pre_result.blocked:
                logger.warning(
                    f"Guardrails blocked request for {self.config.name}: "
                    f"action={pre_result.action.value}, rules={pre_result.triggered_rules}"
                )
                # Return refusal message instead of calling LLM
                return pre_result.refusal_message or "I'm not able to help with that request."
        
        start_time = datetime.now()
        
        try:
            response = await self._call_model(
                model=selected_model,
                system_prompt=self.get_system_prompt(),
                user_prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            # Log interaction
            self._log_interaction(
                model=selected_model,
                task_type=task_type,
                prompt_tokens=len(prompt.split()),
                completion_tokens=len(response.split()),
                latency_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                status="success"
            )
            
            # === POST-CALL GUARDRAILS (Self-Reflection) ===
            if not skip_guardrails and self.guardrails:
                post_result = await self.guardrails.post_call(
                    response=response,
                    agent_name=self.config.name,
                    original_query=prompt,
                    context=str(context) if context else None,
                )
                
                if post_result.needs_revision:
                    logger.info(
                        f"Guardrails flagged response for {self.config.name}: "
                        f"outcome={post_result.outcome.value}, issues={post_result.issues_found}"
                    )
                    
                    # For now, log the warning but return response
                    # Future: could trigger re-generation with reflection prompt
                    if post_result.hallucination_risk and post_result.hallucination_risk > 0.8:
                        logger.warning(
                            f"High hallucination risk ({post_result.hallucination_risk:.2f}) "
                            f"detected for {self.config.name}"
                        )
            
            return response
            
        except Exception as e:
            logger.error(f"Model call failed for {selected_model}: {e}")
            
            # Try fallback chain from router or config
            fallback_models = self._get_fallback_chain(task_type, selected_model)
            
            for fallback_model in fallback_models:
                logger.info(f"Attempting fallback model: {fallback_model}")
                try:
                    response = await self._call_model(
                        model=fallback_model,
                        system_prompt=self.get_system_prompt(),
                        user_prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    
                    self._log_interaction(
                        model=fallback_model,
                        task_type=task_type,
                        prompt_tokens=len(prompt.split()),
                        completion_tokens=len(response.split()),
                        latency_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                        status="fallback"
                    )
                    
                    return response
                except Exception as fallback_error:
                    logger.error(f"Fallback model {fallback_model} also failed: {fallback_error}")
                    continue
            
            # All fallbacks exhausted
            raise
    
    def _get_fallback_chain(self, task_type: Optional[str], exclude_model: str) -> List[str]:
        """
        Get fallback model chain, excluding already-tried model.
        
        Args:
            task_type: Task type for router lookup
            exclude_model: Model that already failed
        
        Returns:
            List of fallback models to try
        """
        fallbacks = []
        
        # Try router first
        if self.model_router and task_type:
            chain = self.model_router.get_fallback_chain(task_type)
            fallbacks = [m for m in chain if m != exclude_model]
        
        # Add config fallback if not already in list
        if self.config.fallback_model and self.config.fallback_model not in fallbacks:
            fallbacks.append(self.config.fallback_model)
        
        return fallbacks
    
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
        status: str = "success",
        task_type: Optional[str] = None,
    ):
        """Log an agent interaction for analytics."""
        interaction = {
            "agent_name": self.config.name,
            "model": model,
            "task_type": task_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        self.interaction_log.append(interaction)
        
        logger.info(
            f"Agent {self.config.name} interaction: {model} | "
            f"task={task_type or 'default'} | "
            f"Tokens: {completion_tokens} | Latency: {latency_ms}ms"
        )
    
    def get_interaction_log(self) -> List[Dict[str, Any]]:
        """Get all logged interactions for this agent."""
        return self.interaction_log.copy()
