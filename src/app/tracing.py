"""
LangSmith Tracing Integration for SignalFlow Agents

Provides automatic tracing with:
- Agent-specific tags for grouping traces by agent type
- Conversation/thread_id tracking for multi-turn conversations
- Metadata for model, task type, and user context
- Seamless integration with existing OpenAI calls

Environment Variables:
- LANGCHAIN_TRACING_V2=true to enable
- LANGCHAIN_API_KEY=your_key
- LANGCHAIN_PROJECT=signalflow (optional, defaults to signalflow)
- LANGCHAIN_ENDPOINT=https://api.smith.langchain.com (optional)

Usage:
    from .tracing import traced_llm_call, get_tracer, TracingContext
    
    # Simple traced call
    response = await traced_llm_call(
        prompt="Analyze this meeting",
        agent_name="DIKWSynthesizer",
        thread_id="conv-123",
    )
    
    # Context manager for multi-step operations
    with TracingContext(agent_name="Arjuna", thread_id="conv-456") as ctx:
        # All calls within this context share the same trace
        response1 = ctx.trace_step("intent_parsing", ...)
        response2 = ctx.trace_step("action_execution", ...)
"""

import os
import uuid
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass, field

# Ensure env vars are loaded before checking tracing
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Track if tracing is enabled
_tracing_enabled: Optional[bool] = None
_langsmith_client = None
_tracer = None


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    global _tracing_enabled
    
    if _tracing_enabled is None:
        # Check both old (LANGCHAIN_) and new (LANGSMITH_) env var formats
        env_value_old = os.environ.get("LANGCHAIN_TRACING_V2", "false").lower()
        env_value_new = os.environ.get("LANGSMITH_TRACING", "false").lower()
        api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY", "")
        
        tracing_enabled = (env_value_old == "true" or env_value_new == "true") and bool(api_key)
        _tracing_enabled = tracing_enabled
        
        if _tracing_enabled:
            logger.info("LangSmith tracing ENABLED")
        else:
            if (env_value_old == "true" or env_value_new == "true") and not api_key:
                logger.warning("LANGSMITH_TRACING=true but LANGSMITH_API_KEY not set")
    
    return _tracing_enabled


def get_project_name() -> str:
    """Get the LangSmith project name."""
    return os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "signalflow")


@dataclass
class TraceMetadata:
    """Metadata for a traced operation."""
    agent_name: str
    thread_id: Optional[str] = None
    task_type: Optional[str] = None
    model: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_langsmith_metadata(self) -> Dict[str, Any]:
        """Convert to LangSmith metadata format."""
        metadata = {
            "agent_name": self.agent_name,
            "timestamp": datetime.now().isoformat(),
        }
        
        if self.thread_id:
            # LangSmith Threads feature looks for session_id, conversation_id, or thread_id
            # We include all three for maximum compatibility
            metadata["session_id"] = self.thread_id  # Primary key for Threads
            metadata["thread_id"] = self.thread_id
            metadata["conversation_id"] = self.thread_id  # Alias for UI
        
        if self.task_type:
            metadata["task_type"] = self.task_type
        
        if self.model:
            metadata["model"] = self.model
        
        if self.user_id:
            metadata["user_id"] = self.user_id
            
        if self.session_id and self.session_id != self.thread_id:
            # If explicitly set separately from thread_id
            metadata["session_id"] = self.session_id
        
        metadata.update(self.extra)
        return metadata
    
    def get_tags(self) -> List[str]:
        """Get tags including auto-generated ones."""
        tags = [f"agent:{self.agent_name}"]
        
        if self.task_type:
            tags.append(f"task:{self.task_type}")
        
        if self.thread_id:
            tags.append(f"thread:{self.thread_id[:8]}")  # Short prefix for readability
        
        if self.model:
            tags.append(f"model:{self.model}")
        
        tags.extend(self.tags)
        return tags


def get_langsmith_client():
    """Get or create LangSmith client."""
    global _langsmith_client
    
    if not is_tracing_enabled():
        return None
    
    if _langsmith_client is None:
        try:
            from langsmith import Client
            _langsmith_client = Client()
            logger.info(f"LangSmith client initialized for project: {get_project_name()}")
        except ImportError:
            logger.warning("langsmith package not installed. Run: pip install langsmith")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith client: {e}")
            return None
    
    return _langsmith_client


def get_tracer():
    """Get or create LangSmith tracer for callbacks."""
    global _tracer
    
    if not is_tracing_enabled():
        return None
    
    if _tracer is None:
        try:
            from langsmith import traceable
            from langchain.callbacks.tracers import LangChainTracer
            
            _tracer = LangChainTracer(
                project_name=get_project_name(),
            )
            logger.info("LangSmith tracer initialized")
        except ImportError:
            logger.warning("langchain not installed. Run: pip install langchain langsmith")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith tracer: {e}")
            return None
    
    return _tracer


class TracingContext:
    """
    Context manager for tracing multi-step agent operations.
    
    All LLM calls within the context share the same parent trace,
    making it easy to group related operations together.
    
    Usage:
        async with TracingContext(
            agent_name="Arjuna",
            thread_id="conv-123",
            task_type="ticket_creation",
        ) as ctx:
            # Step 1: Parse intent
            intent = await ctx.traced_call(
                step_name="parse_intent",
                func=parse_intent,
                prompt=user_message,
            )
            
            # Step 2: Execute action  
            result = await ctx.traced_call(
                step_name="execute_action",
                func=execute_action,
                intent=intent,
            )
    """
    
    def __init__(
        self,
        agent_name: str,
        thread_id: Optional[str] = None,
        task_type: Optional[str] = None,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.metadata = TraceMetadata(
            agent_name=agent_name,
            thread_id=thread_id or str(uuid.uuid4()),
            task_type=task_type,
            user_id=user_id,
            tags=tags or [],
            extra=extra_metadata or {},
        )
        self._run_id: Optional[str] = None
        self._client = None
        self._steps: List[Dict[str, Any]] = []
    
    async def __aenter__(self):
        if is_tracing_enabled():
            self._client = get_langsmith_client()
            if self._client:
                self._run_id = str(uuid.uuid4())
                # Create parent run
                try:
                    self._client.create_run(
                        name=f"{self.metadata.agent_name}",
                        run_type="chain",
                        inputs={"thread_id": self.metadata.thread_id},
                        tags=self.metadata.get_tags(),
                        extra={"metadata": self.metadata.to_langsmith_metadata()},
                        project_name=get_project_name(),
                        id=self._run_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to create trace run: {e}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client and self._run_id:
            try:
                self._client.update_run(
                    run_id=self._run_id,
                    outputs={"steps_completed": len(self._steps)},
                    end_time=datetime.now(),
                    error=str(exc_val) if exc_val else None,
                )
            except Exception as e:
                logger.error(f"Failed to close trace run: {e}")
    
    def __enter__(self):
        """Sync context manager entry."""
        if is_tracing_enabled():
            self._client = get_langsmith_client()
            if self._client:
                self._run_id = str(uuid.uuid4())
                try:
                    self._client.create_run(
                        name=f"{self.metadata.agent_name}",
                        run_type="chain",
                        inputs={"thread_id": self.metadata.thread_id},
                        tags=self.metadata.get_tags(),
                        extra={"metadata": self.metadata.to_langsmith_metadata()},
                        project_name=get_project_name(),
                        id=self._run_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to create trace run: {e}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        if self._client and self._run_id:
            try:
                self._client.update_run(
                    run_id=self._run_id,
                    outputs={"steps_completed": len(self._steps)},
                    end_time=datetime.now(),
                    error=str(exc_val) if exc_val else None,
                )
            except Exception as e:
                logger.error(f"Failed to close trace run: {e}")
    
    def trace_step(
        self,
        step_name: str,
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Record a step in the trace.
        
        Returns:
            Step run_id for reference
        """
        step_id = str(uuid.uuid4())
        step_data = {
            "step_id": step_id,
            "step_name": step_name,
            "inputs": inputs,
            "outputs": outputs,
            "model": model,
            "timestamp": datetime.now().isoformat(),
        }
        self._steps.append(step_data)
        
        if self._client and self._run_id:
            try:
                self._client.create_run(
                    name=step_name,
                    run_type="llm" if model else "chain",
                    inputs=inputs,
                    outputs=outputs,
                    tags=self.metadata.get_tags() + [f"step:{step_name}"],
                    extra={"metadata": {**self.metadata.to_langsmith_metadata(), "model": model}},
                    project_name=get_project_name(),
                    parent_run_id=self._run_id,
                    id=step_id,
                )
                if outputs:
                    self._client.update_run(run_id=step_id, outputs=outputs, end_time=datetime.now())
            except Exception as e:
                logger.error(f"Failed to trace step {step_name}: {e}")
        
        return step_id
    
    def update_step(self, step_id: str, outputs: Dict[str, Any], error: Optional[str] = None):
        """Update a step with outputs after completion."""
        if self._client:
            try:
                self._client.update_run(
                    run_id=step_id,
                    outputs=outputs,
                    end_time=datetime.now(),
                    error=error,
                )
            except Exception as e:
                logger.error(f"Failed to update step {step_id}: {e}")


def traced(
    agent_name: str,
    task_type: Optional[str] = None,
    capture_thread_id: bool = True,
):
    """
    Decorator to add LangSmith tracing to an async function.
    
    Usage:
        @traced(agent_name="DIKWSynthesizer", task_type="synthesis")
        async def synthesize_signals(signals: List[str], thread_id: str = None):
            ...
    
    Args:
        agent_name: Name of the agent for grouping traces
        task_type: Type of task being performed
        capture_thread_id: If True, looks for thread_id in kwargs
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not is_tracing_enabled():
                return await func(*args, **kwargs)
            
            thread_id = kwargs.get("thread_id") if capture_thread_id else None
            
            async with TracingContext(
                agent_name=agent_name,
                thread_id=thread_id,
                task_type=task_type,
            ) as ctx:
                ctx.trace_step(
                    step_name=func.__name__,
                    inputs={"args": str(args)[:500], "kwargs_keys": list(kwargs.keys())},
                )
                result = await func(*args, **kwargs)
                return result
        
        return wrapper
    return decorator


async def traced_llm_call(
    prompt: str,
    agent_name: str,
    model: str = "gpt-4o-mini",
    system_prompt: Optional[str] = None,
    thread_id: Optional[str] = None,
    task_type: Optional[str] = None,
    user_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    tags: Optional[List[str]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Make a traced LLM call with automatic LangSmith integration.
    
    This is a drop-in replacement for direct OpenAI calls that adds
    full tracing capabilities.
    
    Args:
        prompt: User prompt
        agent_name: Name of the agent making the call
        model: Model to use
        system_prompt: Optional system prompt
        thread_id: Conversation/thread ID for multi-turn tracking
        task_type: Type of task (classification, synthesis, etc.)
        user_id: Optional user ID
        temperature: Model temperature
        max_tokens: Max response tokens
        tags: Additional tags
        extra_metadata: Additional metadata to include
    
    Returns:
        LLM response text
    """
    from .llm import _client_once
    
    metadata = TraceMetadata(
        agent_name=agent_name,
        thread_id=thread_id,
        task_type=task_type,
        model=model,
        user_id=user_id,
        tags=tags or [],
        extra=extra_metadata or {},
    )
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    start_time = datetime.now()
    run_id = None
    client = get_langsmith_client()
    
    # Create trace run before LLM call
    if client:
        run_id = str(uuid.uuid4())
        try:
            client.create_run(
                name=f"{agent_name}/{task_type or 'default'}",
                run_type="llm",
                inputs={
                    "messages": messages,
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                tags=metadata.get_tags(),
                extra={"metadata": metadata.to_langsmith_metadata()},
                project_name=get_project_name(),
                id=run_id,
            )
        except Exception as e:
            logger.error(f"Failed to create LangSmith run: {e}")
            run_id = None
    
    try:
        # Make the actual LLM call
        response = _client_once().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        result = response.choices[0].message.content.strip()
        
        # Update trace with success
        if client and run_id:
            try:
                client.update_run(
                    run_id=run_id,
                    outputs={
                        "response": result,
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                        },
                    },
                    end_time=datetime.now(),
                )
            except Exception as e:
                logger.error(f"Failed to update LangSmith run: {e}")
        
        return result
        
    except Exception as e:
        # Update trace with error
        if client and run_id:
            try:
                client.update_run(
                    run_id=run_id,
                    error=str(e),
                    end_time=datetime.now(),
                )
            except Exception as trace_error:
                logger.error(f"Failed to update LangSmith run with error: {trace_error}")
        raise


def create_traced_openai_wrapper():
    """
    Create a traced wrapper for the OpenAI client.
    
    This can be used to automatically trace all OpenAI calls
    without modifying existing code.
    
    Returns:
        Wrapped OpenAI client with tracing enabled
    """
    if not is_tracing_enabled():
        from .llm import _client_once
        return _client_once()
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain.callbacks.tracers import LangChainTracer
        
        tracer = LangChainTracer(project_name=get_project_name())
        
        # This returns a LangChain model, not raw OpenAI
        # Use for LangChain-based code paths
        return ChatOpenAI(
            model="gpt-4o-mini",
            callbacks=[tracer],
        )
    except ImportError:
        logger.warning("langchain-openai not installed, using raw OpenAI client")
        from .llm import _client_once
        return _client_once()


# =============================================================================
# Utility functions for thread/conversation management
# =============================================================================

_active_threads: Dict[str, Dict[str, Any]] = {}


def start_thread(
    thread_id: Optional[str] = None,
    agent_name: str = "default",
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Start a new conversation thread for tracing.
    
    Returns:
        thread_id for use in subsequent calls
    """
    thread_id = thread_id or str(uuid.uuid4())
    
    _active_threads[thread_id] = {
        "agent_name": agent_name,
        "user_id": user_id,
        "metadata": metadata or {},
        "started_at": datetime.now().isoformat(),
        "message_count": 0,
    }
    
    logger.info(f"Started thread {thread_id} for agent {agent_name}")
    return thread_id


def get_thread_info(thread_id: str) -> Optional[Dict[str, Any]]:
    """Get information about an active thread."""
    return _active_threads.get(thread_id)


def end_thread(thread_id: str) -> None:
    """End a conversation thread."""
    if thread_id in _active_threads:
        del _active_threads[thread_id]
        logger.info(f"Ended thread {thread_id}")


def increment_thread_message_count(thread_id: str) -> int:
    """Increment and return the message count for a thread."""
    if thread_id in _active_threads:
        _active_threads[thread_id]["message_count"] += 1
        return _active_threads[thread_id]["message_count"]
    return 0


# =============================================================================
# LangChain Integration Bridge
# =============================================================================

def get_traced_langchain_model(
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    agent_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """
    Get a LangChain ChatOpenAI model with automatic LangSmith tracing.
    
    This bridges our native tracing with LangChain's ecosystem,
    enabling use of LangChain tools while maintaining our tracing setup.
    
    Usage:
        from .tracing import get_traced_langchain_model
        
        llm = get_traced_langchain_model(
            model="gpt-4o",
            agent_name="DIKWSynthesizer",
        )
        
        # Can use with LangChain tools, chains, etc.
        response = llm.invoke([HumanMessage(content="Hello")])
    
    Args:
        model: Model name (gpt-4o, gpt-4o-mini, etc.)
        temperature: Model temperature
        agent_name: Name for trace grouping
        tags: Additional tags for filtering
    
    Returns:
        ChatOpenAI instance with tracing callbacks
    """
    try:
        from langchain_openai import ChatOpenAI
        
        callbacks = []
        
        if is_tracing_enabled():
            try:
                from langchain.callbacks.tracers import LangChainTracer
                
                tracer = LangChainTracer(project_name=get_project_name())
                callbacks.append(tracer)
            except ImportError:
                logger.warning("langchain callbacks not available")
        
        # Build tags
        all_tags = []
        if agent_name:
            all_tags.append(f"agent:{agent_name}")
        if tags:
            all_tags.extend(tags)
        
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            callbacks=callbacks if callbacks else None,
            tags=all_tags if all_tags else None,
        )
        
    except ImportError:
        logger.error("langchain-openai not installed. Run: pip install langchain-openai")
        raise


def get_langchain_runnable_config(
    agent_name: str,
    thread_id: Optional[str] = None,
    task_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Get a config dict for LangChain runnables with tracing metadata.
    
    Use this when invoking LangChain chains/graphs to include tracing.
    
    Usage:
        from langchain_core.runnables import RunnableSequence
        
        config = get_langchain_runnable_config(
            agent_name="Arjuna",
            thread_id="conv-123",
        )
        
        result = chain.invoke(input, config=config)
    
    Returns:
        Config dict with callbacks and metadata
    """
    config = {
        "metadata": {
            "agent_name": agent_name,
            "thread_id": thread_id,
            "task_type": task_type,
        },
        "tags": [],
    }
    
    if agent_name:
        config["tags"].append(f"agent:{agent_name}")
    if thread_id:
        config["tags"].append(f"thread:{thread_id[:8]}")
    if task_type:
        config["tags"].append(f"task:{task_type}")
    if tags:
        config["tags"].extend(tags)
    
    if is_tracing_enabled():
        try:
            from langchain.callbacks.tracers import LangChainTracer
            tracer = LangChainTracer(project_name=get_project_name())
            config["callbacks"] = [tracer]
        except ImportError:
            pass
    
    return config

