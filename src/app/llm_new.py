import os
from openai import OpenAI

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Available Models Configuration
AVAILABLE_MODELS = {
    # OpenAI Models
    "gpt-4.1-mini": {"provider": "openai", "name": "GPT-4.1 Mini", "tier": "fast", "cost": "$"},
    "gpt-4.1": {"provider": "openai", "name": "GPT-4.1", "tier": "balanced", "cost": "$$"},
    "gpt-5": {"provider": "openai", "name": "GPT-5", "tier": "premium", "cost": "$$$"},
    "gpt-5.1": {"provider": "openai", "name": "GPT-5.1", "tier": "premium", "cost": "$$$"},
    "gpt-5.2": {"provider": "openai", "name": "GPT-5.2", "tier": "premium", "cost": "$$$$"},
    "codex-5": {"provider": "openai", "name": "Codex-5", "tier": "code", "cost": "$$$"},
    # Anthropic Models
    "claude-opus-4.5": {"provider": "anthropic", "name": "Claude Opus 4.5", "tier": "premium", "cost": "$$$$"},
    "claude-sonnet-4": {"provider": "anthropic", "name": "Claude Sonnet 4", "tier": "balanced", "cost": "$$"},
    "claude-haiku-3": {"provider": "anthropic", "name": "Claude Haiku 3", "tier": "fast", "cost": "$"},
}

# Default model from environment or fallback
DEFAULT_MODEL = os.getenv("SIGNALFLOW_MODEL", "gpt-4.1-mini")

_openai_client = None
_anthropic_client = None

def _openai_client_once():
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env file.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

def _anthropic_client_once():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set in .env file.")
            _anthropic_client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    return _anthropic_client

def get_current_model():
    """Get currently selected model from settings."""
    from .infrastructure.supabase_client import get_supabase_client
    try:
        supabase = get_supabase_client()
        result = supabase.table("settings").select("value").eq("key", "ai_model").execute()
        rows = result.data or []
        if rows:
            return rows[0]["value"]
    except:
        pass
    return DEFAULT_MODEL

def set_model(model_id: str):
    """Set the AI model to use."""
    if model_id not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown model: {model_id}")
    from .infrastructure.supabase_client import get_supabase_client
    supabase = get_supabase_client()
    supabase.table("settings").upsert({"key": "ai_model", "value": model_id}).execute()

def ask(prompt: str, model: str = None) -> str:
    """Simple single-turn prompt to LLM without context."""
    model = model or get_current_model()
    model_info = AVAILABLE_MODELS.get(model, AVAILABLE_MODELS[DEFAULT_MODEL])
    
    if model_info["provider"] == "anthropic":
        return _ask_anthropic(prompt, model)
    else:
        return _ask_openai(prompt, model)

def _ask_openai(prompt: str, model: str) -> str:
    """Call OpenAI API."""
    resp = _openai_client_once().responses.create(
        model=model,
        input=[{"role": "user", "content": prompt}],
    )
    return resp.output_text.strip()

def _ask_anthropic(prompt: str, model: str) -> str:
    """Call Anthropic API."""
    client = _anthropic_client_once()
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()

SYSTEM_PROMPT = """You are a meeting retrieval agent. You answer questions ONLY using the provided context.
If the answer is not supported by the context, say:
"I don't have enough information in the provided sources."
Cite sources by index in square brackets, e.g., [1], [2].
Be concise and factual. If asked what blocked by, return the blocked items and reasons.
"""

def answer(question: str, context_blocks: list[str], model: str = None) -> str:
    if not context_blocks:
        return "I don't have enough information in the provided sources."

    model = model or get_current_model()
    model_info = AVAILABLE_MODELS.get(model, AVAILABLE_MODELS[DEFAULT_MODEL])
    ctx = "\n\n".join(context_blocks)
    
    if model_info["provider"] == "anthropic":
        client = _anthropic_client_once()
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Context:\n{ctx}\n\nQuestion:\n{question}"}]
        )
        return message.content[0].text.strip()
    else:
        resp = _openai_client_once().responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion:\n{question}"},
            ],
        )
        return resp.output_text.strip()
