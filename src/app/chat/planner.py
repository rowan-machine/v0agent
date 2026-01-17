# src/app/chat/planner.py

import json
from typing import Dict, Any
from ..llm import _client_once

# ---- Schema Definition ----
REQUIRED_KEYS = {"keywords", "concepts"}
OPTIONAL_KEYS = {"source_preference", "time_hint", "notes"}
ALL_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS


SYSTEM_PROMPT = """
You are a query planning assistant.

Your task is to translate a user's question into broad, inclusive search hints.

Rules:
- Do NOT answer the question.
- Do NOT decide relevance.
- Do NOT exclude information.
- Do NOT generate strict filters.
- Only suggest keywords and concepts that may appear in documents or meeting notes.

You must return valid JSON.
The JSON MUST contain:
- keywords (list of strings)
- concepts (list of strings)

The JSON MAY contain:
- source_preference ("docs", "meetings", "both", or null)
- time_hint ("recent", "past", "any", or null)
- notes (string or null)

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
    Produce a structured query plan from a natural language question.

    Fail hard if required keys are missing or if unknown keys appear.
    Normalize optional fields if omitted.
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

    raw_text = resp.output_text.strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Planner returned invalid JSON: {e}\nRaw output:\n{raw_text}"
        )

    # ---- Required keys ----
    missing_required = REQUIRED_KEYS - data.keys()
    if missing_required:
        raise ValueError(
            f"Planner missing required keys: {missing_required}"
        )

    # ---- Unknown keys ----
    unknown_keys = set(data.keys()) - ALL_KEYS
    if unknown_keys:
        raise ValueError(
            f"Planner returned unknown keys: {unknown_keys}"
        )

    # ---- Normalize optional keys ----
    for key in OPTIONAL_KEYS:
        data.setdefault(key, None)

    # ---- Validate types ----
    if not isinstance(data["keywords"], list):
        raise ValueError("Planner 'keywords' must be a list")

    if not isinstance(data["concepts"], list):
        raise ValueError("Planner 'concepts' must be a list")

    if data["source_preference"] not in ("docs", "meetings", "both", None):
        raise ValueError("Invalid source_preference value")

    if data["time_hint"] not in ("recent", "past", "any", None):
        raise ValueError("Invalid time_hint value")

    # ---- Normalize strings ----
    data["keywords"] = [
        k.lower() for k in data["keywords"] if isinstance(k, str)
    ]
    data["concepts"] = [
        c.lower() for c in data["concepts"] if isinstance(c, str)
    ]

    return data
