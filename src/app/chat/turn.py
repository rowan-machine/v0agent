# src/app/chat/turn.py

import re
from typing import Tuple, List, Dict
from .planner import plan
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
    Single grounded Q&A turn with planner (fail-hard).
    """

    # ---- 1) Planner (fail hard) ----
    plan_json = plan(question=question)

    # Merge planner hints (OR semantics)
    terms = list(set(plan_json["keywords"] + plan_json["concepts"]))
    if not terms:
        return "I don’t have enough information in the provided sources.", []

    # Planner may suggest a preference (soft)
    effective_source = plan_json["source_preference"] or source_type

    # ---- 2) Retrieve ----
    raw = retrieve(
        terms=terms,
        source_type=effective_source,
        start_date=start_date,
        end_date=end_date,
        limit=MAX_CONTEXT,
    )

    # ---- 3) Assemble context ----
    blocks: List[str] = []
    sources: List[Dict] = []

    for d in raw["documents"]:
        idx = len(blocks) + 1
        blocks.append(f"[{idx}] (Document: {d['source']})\n{d['content']}")
        sources.append({"type": "document", "id": d["id"], "label": d["source"]})
        if len(blocks) >= MAX_CONTEXT:
            break

    if len(blocks) < MAX_CONTEXT:
        for m in raw["meetings"]:
            idx = len(blocks) + 1
            blocks.append(
                f"[{idx}] (Meeting: {m['meeting_name']})\n{m['synthesized_notes']}"
            )
            sources.append(
                {"type": "meeting", "id": m["id"], "label": m["meeting_name"]}
            )
            if len(blocks) >= MAX_CONTEXT:
                break

    if not blocks:
        return "I don’t have enough information in the provided sources.", []

    # ---- 4) Answer ----
    answer_text = llm_answer(question, blocks)
    return answer_text, sources
