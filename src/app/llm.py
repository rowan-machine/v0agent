import os
from openai import OpenAI

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

_client = None

def _client_once():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please add it to your .env file."
            )
        _client = OpenAI(api_key=api_key)
    return _client

SYSTEM_PROMPT = """You are a meeting retrieval agent. You answer questions ONLY using the provided context.
If the answer is not supported by the context, say:
"I don’t have enough information in the provided sources."
Cite sources by index in square brackets, e.g., [1], [2].
Be concise and factual. If asked what blocked by, return the blocked items and reasons.
"""

def get_current_model() -> str:
    """Get currently selected AI model from settings database."""
    from .db import connect
    try:
        with connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'ai_model'").fetchone()
            if row:
                return row["value"]
    except Exception:
        pass
    return "gpt-4o-mini"  # Default fallback

def ask(prompt: str, model: str = None) -> str:
    """Simple single-turn prompt to LLM without context."""
    model = model or get_current_model()
    resp = _client_once().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


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
    
    resp = _client_once().chat.completions.create(
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
    from .db import connect
    try:
        with connect() as conn:
            status = conn.execute(
                "SELECT * FROM user_status WHERE is_current = 1 ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        
        if not status:
            return ""
        
        return f"[Current User Status: {status['status_text']} (Mode: {status['interpreted_mode']}, Activity: {status['interpreted_activity']})]"
    except Exception:
        return ""


def answer(question: str, context_blocks: list[str]) -> str:
    if not context_blocks:
        return "I don't have enough information in the provided sources."

    ctx = "\n\n".join(context_blocks)
    
    # Add user status context
    status_ctx = get_user_status_context()
    if status_ctx:
        ctx = status_ctx + "\n\n" + ctx
    
    model = get_current_model()

    resp = _client_once().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{ctx}\n\nQuestion:\n{question}",
            },
        ],
    )
    return resp.choices[0].message.content.strip()
