# src/app/chat/turn.py

import re
from typing import Tuple, List, Dict
from ..memory.retrieve import retrieve
from ..llm import answer as llm_answer

MAX_CONTEXT = 6


def extract_terms(text: str) -> List[str]:
    return [
        w for w in re.findall(r"[a-zA-Z]+", text.lower())
        if len(w) > 2
    ]


def run_turn(
    question: str,
    source_type: str = "docs",
    start_date: str | None = None,
    end_date: str | None = None,
) -> Tuple[str, List[Dict]]:
    """
    Execute a single grounded Q&A turn.
    Not conversational. No planner yet.
    """

    terms = extract_terms(question)
    if not terms:
        return "I don’t have enough information in the provided sources.", []

    raw = retrieve(
        terms=terms,
        source_type=source_type,
        start_date=start_date,
        end_date=end_date,
        limit=MAX_CONTEXT,
    )

    blocks: List[str] = []
    sources: List[Dict] = []

    # Prefer documents first
    for d in raw["documents"]:
        idx = len(blocks) + 1
        blocks.append(
            f"[{idx}] (Document: {d['source']})\n{d['content']}"
        )
        sources.append(
            {"type": "document", "id": d["id"], "label": d["source"]}
        )
        if len(blocks) >= MAX_CONTEXT:
            break

    # Then meetings
    if len(blocks) < MAX_CONTEXT:
        for m in raw["meetings"]:
            idx = len(blocks) + 1
            blocks.append(
                f"[{idx}] (Meeting: {m['meeting_name']})\n{m['synthesized_notes']}"
            )
            sources.append(
                {
                    "type": "meeting",
                    "id": m["id"],
                    "label": m["meeting_name"],
                }
            )
            if len(blocks) >= MAX_CONTEXT:
                break

    if not blocks:
        return "I don’t have enough information in the provided sources.", []

    answer_text = llm_answer(question, blocks)
    return answer_text, sources
