# src/app/chat/planner.py

import json
from typing import Dict, Any
from ..llm import _client_once

PLANNER_SCHEMA_KEYS = {
    "keywords",
    "concepts",
    "source_preference",
    "time_hint",
    "notes",
}

SYSTEM_PROMPT = """
You are a query planning assistant.

Your task is to translate a user's question into broad, inclusive search hints.

Rules:
- Do NOT answer the question.
- Do NOT decide relevance.
- Do NOT exclude information.
- Do NOT generate filters or limits.
- Only suggest keywords and concepts that may appear in documents or meeting notes.

You must return valid JSON matching the provided schema.
Return JSON only. No explanations.
"""

USER_PROMPT_TEMPLATE = """
Conversation context:
{conversation}

User question:
{question}

Return JSON only.
"""


def plan(
    question: str,
    conversation: str | None = None,
) -> Dict[str, Any]:
    """
    Call LLM to produce a strict JSON plan.
    Fail hard on any schema or parsing error.
    """
    prompt = USER_PROMPT_TEMPLATE.format(
        conversation=conversation or "",
        question=question,
    )

    resp = _client_once().responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": prompt.strip()},
        ],
    )

    text = resp.output_text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {e}\n{text}")

    # ---- Strict schema validation (fail hard) ----
    if set(data.keys()) != PLANNER_SCHEMA_KEYS:
        raise ValueError(
            f"Planner JSON keys mismatch. "
            f"Expected {PLANNER_SCHEMA_KEYS}, got {set(data.keys())}"
        )

    if not isinstance(data["keywords"], list):
        raise ValueError("Planner 'keywords' must be a list")
    if not isinstance(data["concepts"], list):
        raise ValueError("Planner 'concepts' must be a list")

    if data["source_preference"] not in ("docs", "meetings", "both", None):
        raise ValueError("Invalid source_preference")

    if data["time_hint"] not in ("recent", "past", "any", None):
        raise ValueError("Invalid time_hint")

    # Normalize strings to lowercase for retrieval
    data["keywords"] = [k.lower() for k in data["keywords"] if isinstance(k, str)]
    data["concepts"] = [c.lower() for c in data["concepts"] if isinstance(c, str)]

    return data
