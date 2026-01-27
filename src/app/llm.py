import os
from openai import OpenAI

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

_openai_client = None
_anthropic_client = None

# Claude model identifier
CLAUDE_OPUS_MODEL = "claude-opus-4-5-20250514"

def _openai_client_once():
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please add it to your .env file."
            )
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _anthropic_client_once():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is not set. "
                    "Please add it to your .env file."
                )
            _anthropic_client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    return _anthropic_client


def _is_claude_model(model: str) -> bool:
    """Check if the model is a Claude model."""
    return model and (model.startswith("claude") or "anthropic" in model.lower())

SYSTEM_PROMPT = """You are a meeting retrieval agent. You answer questions ONLY using the provided context.
If the answer is not supported by the context, say:
"I don’t have enough information in the provided sources."
Cite sources by index in square brackets, e.g., [1], [2].
Be concise and factual. If asked what blocked by, return the blocked items and reasons.
"""

def get_current_model() -> str:
    """Get currently selected AI model from settings database."""
    from .infrastructure.supabase_client import get_supabase_client
    try:
        supabase = get_supabase_client()
        result = supabase.table("settings").select("value").eq("key", "ai_model").execute()
        rows = result.data or []
        if rows:
            return rows[0]["value"]
    except Exception:
        pass
    return "gpt-4o-mini"  # Default fallback

def ask(prompt: str, model: str = None, trace_name: str = "llm.ask", thread_id: str = None) -> str:
    """Simple single-turn prompt to LLM without context.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model to use (defaults to current_model setting)
        trace_name: Name for LangSmith tracing (optional)
        thread_id: Thread ID for LangSmith thread grouping (optional)
    
    Returns:
        LLM response text
    """
    import uuid
    from datetime import datetime
    
    model = model or get_current_model()
    
    # LangSmith tracing
    run_id = None
    langsmith_client = None
    try:
        from .tracing import is_tracing_enabled, get_langsmith_client, get_project_name, TraceMetadata
        if is_tracing_enabled():
            langsmith_client = get_langsmith_client()
            if langsmith_client:
                run_id = str(uuid.uuid4())
                
                # Build metadata with thread_id for Threads feature
                metadata = {"source": "llm.ask"}
                tags = [f"model:{model}", "source:llm.ask"]
                
                if thread_id:
                    # LangSmith looks for session_id, thread_id, or conversation_id
                    metadata["session_id"] = thread_id
                    metadata["thread_id"] = thread_id
                    metadata["conversation_id"] = thread_id
                    tags.append(f"thread:{thread_id[:8]}")
                
                langsmith_client.create_run(
                    name=trace_name,
                    run_type="llm",
                    inputs={"prompt": prompt[:2000], "model": model},
                    tags=tags,
                    extra={"metadata": metadata},
                    project_name=get_project_name(),
                    id=run_id,
                )
                print(f"✅ LangSmith: created run {run_id[:8]}... for {trace_name}")
    except Exception as e:
        print(f"⚠️ LangSmith: tracing init error: {e}")
    
    try:
        # Route to appropriate provider based on model
        if _is_claude_model(model):
            # Use Anthropic API for Claude models
            client = _anthropic_client_once()
            message = client.messages.create(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text.strip()
        else:
            # Use OpenAI API
            resp = _openai_client_once().chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = resp.choices[0].message.content.strip()
        
        # Update trace with success
        if langsmith_client and run_id:
            try:
                langsmith_client.update_run(
                    run_id=run_id,
                    outputs={"response": response_text[:2000]},
                    end_time=datetime.now(),
                )
            except Exception:
                pass
        
        return response_text
    except Exception as e:
        # Update trace with error
        if langsmith_client and run_id:
            try:
                langsmith_client.update_run(
                    run_id=run_id,
                    error=str(e),
                    end_time=datetime.now(),
                )
            except Exception:
                pass
        raise


# Alias for backward compatibility with LangSmith evaluations
chat = ask


def analyze_image(image_base64: str, prompt: str = None) -> str:
    """Analyze an image using GPT-4 Vision and return a text description."""
    if not prompt:
        prompt = """Analyze this image and provide a detailed description. 
If it's a screenshot of a meeting, diagram, or document:
- Summarize the key information visible
- Extract any text, names, dates, or action items
- Describe any diagrams, charts, or visual elements
- Note anything that seems important for meeting context

Return the analysis as structured text that can be stored and searched."""
    
    resp = _openai_client_once().chat.completions.create(
        model="gpt-4o",  # Vision requires gpt-4o or gpt-4-turbo
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_tokens=1000
    )
    return resp.choices[0].message.content.strip()

def get_user_status_context() -> str:
    """Get current user status for chat context."""
    from .infrastructure.supabase_client import get_supabase_client
    try:
        supabase = get_supabase_client()
        result = supabase.table("user_status").select("*").eq("is_current", True).order("created_at", desc=True).limit(1).execute()
        rows = result.data or []
        
        if not rows:
            return ""
        
        status = rows[0]
        return f"[Current User Status: {status['status_text']} (Mode: {status['interpreted_mode']}, Activity: {status['interpreted_activity']})]"
    except Exception:
        return ""


def answer(question: str, context_blocks: list[str], trace_name: str = "llm.answer", return_run_id: bool = False, thread_id: str = None) -> str | tuple:
    """Answer a question using provided context.
    
    Args:
        question: The question to answer
        context_blocks: List of context blocks to use
        trace_name: Name for LangSmith tracing (optional)
        return_run_id: If True, return (answer, run_id) tuple for feedback
        thread_id: Thread ID for LangSmith Threads feature (e.g. conversation_id)
    
    Returns:
        LLM response text, or (response, run_id) tuple if return_run_id=True
    """
    import uuid
    from datetime import datetime
    
    if not context_blocks:
        result = "I don't have enough information in the provided sources."
        return (result, None) if return_run_id else result

    ctx = "\n\n".join(context_blocks)
    
    # Add user status context
    status_ctx = get_user_status_context()
    if status_ctx:
        ctx = status_ctx + "\n\n" + ctx
    
    model = get_current_model()
    
    # LangSmith tracing
    run_id = None
    langsmith_client = None
    try:
        from .tracing import is_tracing_enabled, get_langsmith_client, get_project_name
        if is_tracing_enabled():
            langsmith_client = get_langsmith_client()
            if langsmith_client:
                run_id = str(uuid.uuid4())
                
                # Build metadata with thread_id for Threads feature
                metadata = {"source": "llm.answer"}
                tags = [f"model:{model}", "source:llm.answer"]
                
                if thread_id:
                    # LangSmith looks for session_id for thread grouping
                    metadata["session_id"] = str(thread_id)
                    metadata["thread_id"] = str(thread_id)
                    metadata["conversation_id"] = str(thread_id)
                    tags.append(f"thread:{str(thread_id)[:8]}")
                
                langsmith_client.create_run(
                    name=trace_name,
                    run_type="llm",
                    inputs={
                        "question": question[:500],
                        "context_blocks_count": len(context_blocks),
                        "model": model
                    },
                    tags=tags,
                    extra={"metadata": metadata},
                    project_name=get_project_name(),
                    id=run_id,
                )
                print(f"✅ LangSmith: created run {run_id[:8]}... for {trace_name}" + (f" thread:{thread_id}" if thread_id else ""))
    except Exception as e:
        print(f"⚠️ LangSmith: tracing init error: {e}")
    
    try:
        resp = _openai_client_once().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{ctx}\n\nQuestion:\n{question}",
                },
            ],
        )
        response_text = resp.choices[0].message.content.strip()
        
        # Update trace with success
        if langsmith_client and run_id:
            try:
                langsmith_client.update_run(
                    run_id=run_id,
                    outputs={"response": response_text[:2000]},
                    end_time=datetime.now(),
                )
            except Exception:
                pass
        
        return (response_text, run_id) if return_run_id else response_text
    except Exception as e:
        # Update trace with error
        if langsmith_client and run_id:
            try:
                langsmith_client.update_run(
                    run_id=run_id,
                    error=str(e),
                    end_time=datetime.now(),
                )
            except Exception:
                pass
        raise
