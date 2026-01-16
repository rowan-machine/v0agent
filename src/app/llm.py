import os
from openai import OpenAI

_client = None

def _client_once():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please set it with: export OPENAI_API_KEY='your-key'"
            )
        _client = OpenAI(api_key=api_key)
    return _client

SYSTEM_PROMPT = """You are a meeting retrieval agent. You answer questions ONLY using the provided context.
If the answer is not supported by the context, say:
"I don’t have enough information in the provided sources."
Cite sources by index in square brackets, e.g., [1], [2].
Be concise and factual. If asked what blocked by, return the blocked items and reasons.
"""

def answer(question: str, context_blocks: list[str]) -> str:
    if not context_blocks:
        return "I don’t have enough information in the provided sources."

    ctx = "\n\n".join(context_blocks)

    resp = _client_once().responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{ctx}\n\nQuestion:\n{question}",
            },
        ],
    )
    return resp.output_text.strip()
