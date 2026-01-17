# src/app/chat/fallback.py

import re

def fallback_plan(question: str) -> dict:
    """
    Extremely simple lexical fallback.
    Used only when planner fails.
    """

    terms = [
        w.lower()
        for w in re.findall(r"[a-zA-Z]+", question)
        if len(w) > 2
    ]

    return {
        "keywords": terms,
        "concepts": [],
        "source_preference": None,
        "time_hint": None,
        "notes": "fallback_used",
    }
