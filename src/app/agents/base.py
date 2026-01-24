"""
Base agent class for all AI agents in SignalFlow.
Provides common functionality for agent configuration, tool access, and LLM interactions.
Integrates with ModelRouter for automatic model selection per task type.
Integrates with Guardrails for pre/post call safety and reflection (Checkpoint 1.8).
Integrates with LangSmith tracing for observability and debugging.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel
from datetime import datetime
import logging
import uuid

if TYPE_CHECKING:
    from .guardrails import Guardrails

logger = logging.getLogger(__name__)

# Import tracing utilities
try:
    from ..tracing import (
        is_tracing_enabled,
        TracingContext,
        TraceMetadata,
        get_langsmith_client,
        get_project_name,
    )
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    logger.debug("Tracing module not available")


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text using a heuristic.
    
    Uses ~4 characters per token as a reasonable estimate for GPT models.
    This is more accurate than word splitting for real-world text.
    For precise counting, use tiktoken library.
    
    Args:
        text: Input text to estimate tokens for
    
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # ~4 chars per token is a reasonable heuristic for GPT models
    # Slightly better than len(text.split()) which underestimates
    return max(1, len(text) // 4)


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
    enable_tracing: bool = True  # Enable LangSmith tracing for this agent
    
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
        thread_id: Optional[str] = None,
    ):
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration
            llm_client: LLM client (will default to global if None)
            tool_registry: Tool registry (will default to global if None)
            model_router: Model router for auto-selection (will default to global if None)
            guardrails: Guardrails instance for pre/post hooks (will default to global if None)
            thread_id: Optional conversation thread ID for tracing multi-turn conversations
        """
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.model_router = model_router
        self.guardrails = guardrails
        self.interaction_log: List[Dict[str, Any]] = []
        
        # Tracing state
        self._thread_id = thread_id
        self._tracing_context: Optional[Any] = None
    
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
        thread_id: Optional[str] = None,
    ) -> str:
        """
        Call the LLM with automatic model selection, fallback support, guardrails, and tracing.
        
        Guardrails hooks (Checkpoint 1.8):
        - pre_call: Input filtering, safety checks before LLM call
        - post_call: Self-reflection, hallucination detection after response
        
        Tracing (LangSmith integration):
        - Automatic tracing when LANGCHAIN_TRACING_V2=true
        - Tags by agent name, task type, and model
        - Thread/conversation ID for multi-turn tracking
        
        Args:
            prompt: The prompt to send
            task_type: Type of task for model routing (classification, synthesis, etc.)
            model: Override model (bypasses router)
            temperature: Override temperature
            max_tokens: Override max_tokens
            context: Optional context for guardrails (e.g., source documents)
            skip_guardrails: Bypass guardrails for internal reflection calls
            thread_id: Optional thread ID for conversation tracing (overrides instance thread_id)
        
        Returns:
            LLM response text
        
        Raises:
            GuardrailBlockedError: If pre-call guardrails block the request
        """
        # Select model using router or override
        selected_model = self.select_model(task_type=task_type, override=model)
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        
        # Use provided thread_id or fall back to instance thread_id
        effective_thread_id = thread_id or self._thread_id
        
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
        
        # === LANGSMITH TRACING ===
        run_id = None
        langsmith_client = None
        if TRACING_AVAILABLE and self.config.enable_tracing and is_tracing_enabled():
            langsmith_client = get_langsmith_client()
            if langsmith_client:
                run_id = str(uuid.uuid4())
                trace_metadata = TraceMetadata(
                    agent_name=self.config.name,
                    thread_id=effective_thread_id,
                    task_type=task_type,
                    model=selected_model,
                )
                try:
                    langsmith_client.create_run(
                        name=f"{self.config.name}/{task_type or 'default'}",
                        run_type="llm",
                        inputs={
                            "prompt": prompt[:2000],  # Truncate for storage
                            "system_prompt": self.get_system_prompt()[:500],
                            "model": selected_model,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                        tags=trace_metadata.get_tags(),
                        extra={"metadata": trace_metadata.to_langsmith_metadata()},
                        project_name=get_project_name(),
                        id=run_id,
                    )
                except Exception as e:
                    logger.debug(f"Failed to create LangSmith run: {e}")
                    run_id = None
        
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
                prompt_tokens=estimate_tokens(prompt),
                completion_tokens=estimate_tokens(response),
                latency_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                status="success"
            )
            
            # === UPDATE LANGSMITH TRACE (SUCCESS) ===
            if langsmith_client and run_id:
                try:
                    langsmith_client.update_run(
                        run_id=run_id,
                        outputs={
                            "response": response[:2000],  # Truncate for storage
                            "prompt_tokens": estimate_tokens(prompt),
                            "completion_tokens": estimate_tokens(response),
                        },
                        end_time=datetime.now(),
                    )
                except Exception as e:
                    logger.debug(f"Failed to update LangSmith run: {e}")
            
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
            
            # === UPDATE LANGSMITH TRACE (ERROR) ===
            if langsmith_client and run_id:
                try:
                    langsmith_client.update_run(
                        run_id=run_id,
                        error=str(e),
                        end_time=datetime.now(),
                    )
                except Exception as trace_error:
                    logger.debug(f"Failed to update LangSmith run with error: {trace_error}")
            
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
                        prompt_tokens=estimate_tokens(prompt),
                        completion_tokens=estimate_tokens(response),
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
    
    # =========================================================================
    # Thread/Conversation Management for Tracing
    # =========================================================================
    
    def set_thread_id(self, thread_id: str) -> None:
        """
        Set the conversation thread ID for tracing.
        
        All subsequent LLM calls will be tagged with this thread_id,
        allowing you to group multi-turn conversations in LangSmith.
        
        Args:
            thread_id: Unique identifier for this conversation
        """
        self._thread_id = thread_id
        logger.debug(f"Agent {self.config.name} thread_id set to: {thread_id}")
    
    def get_thread_id(self) -> Optional[str]:
        """Get the current conversation thread ID."""
        return self._thread_id
    
    def new_thread(self) -> str:
        """
        Start a new conversation thread and return its ID.
        
        Returns:
            New thread_id (UUID)
        """
        self._thread_id = str(uuid.uuid4())
        logger.debug(f"Agent {self.config.name} started new thread: {self._thread_id}")
        return self._thread_id
    
    def clear_thread(self) -> None:
        """Clear the current thread ID (calls will not be grouped)."""
        self._thread_id = None
    
    # =========================================================================
    # Evaluation Feedback for LangSmith
    # =========================================================================
    
    def submit_feedback(
        self,
        run_id: str,
        key: str = "quality",
        score: Optional[float] = None,
        comment: Optional[str] = None,
        correction: Optional[str] = None,
    ) -> Optional[str]:
        """
        Submit evaluation feedback for a LangSmith trace run.
        
        Use this to provide feedback on agent outputs that can be used
        to track quality and improve prompts over time.
        
        Args:
            run_id: The LangSmith run ID (from ask_llm call)
            key: Feedback dimension (quality, helpfulness, accuracy)
            score: 0.0 to 1.0 score
            comment: Freeform feedback comment
            correction: What the correct output should have been
        
        Returns:
            Feedback ID if successful, None otherwise
        """
        try:
            from ..services.evaluations import submit_feedback
            return submit_feedback(
                run_id=run_id,
                key=key,
                score=score,
                comment=comment,
                correction=correction,
                source_info={"type": "agent", "agent_name": self.config.name},
            )
        except ImportError:
            logger.debug("Evaluations module not available")
            return None
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            return None
    
    async def evaluate_output(
        self,
        output: str,
        evaluators: List[str],
        context: Optional[str] = None,
        expected: Optional[str] = None,
        user_request: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run evaluators on an agent output.
        
        Available evaluators: relevance, accuracy, helpfulness
        
        Args:
            output: The output to evaluate
            evaluators: List of evaluator names to run
            context: Context for relevance evaluation
            expected: Expected output for accuracy evaluation
            user_request: User request for helpfulness evaluation
            run_id: Optional LangSmith run ID to attach feedback
        
        Returns:
            Dict mapping evaluator names to scores and reasoning
        """
        try:
            from ..services.evaluations import evaluate_output
            results = evaluate_output(
                output=output,
                evaluator_names=evaluators,
                context=context,
                expected=expected,
                user_request=user_request,
                run_id=run_id,
                submit_to_langsmith=run_id is not None,
            )
            return {k: {"score": v.score, "reasoning": v.reasoning} for k, v in results.items()}
        except ImportError:
            logger.debug("Evaluations module not available")
            return {}
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {"error": str(e)}

