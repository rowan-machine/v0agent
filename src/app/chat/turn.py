# src/app/chat/turn.py

from typing import Tuple, List, Dict
from .planner import plan
from .context import build_context
from .models import add_message, get_recent_messages
from ..memory.retrieve import retrieve
from ..llm import answer as llm_answer

MAX_CONTEXT = 6


# -----------------------------
# Stateless single-turn (QUERY)
# -----------------------------
def run_turn(
    question: str,
    source_type: str = "docs",
    start_date: str | None = None,
    end_date: str | None = None,
) -> Tuple[str, List[Dict]]:
    """
    Single-turn, stateless Q&A.
    Used by /query.
    """

    plan_json = plan(question)

    terms = list(set(plan_json["keywords"] + plan_json["concepts"]))
    if not terms:
        return "I don’t have enough information in the provided sources.", []

    effective_source = plan_json["source_preference"] or source_type

    raw = retrieve(
        terms=terms,
        source_type=effective_source,
        start_date=start_date,
        end_date=end_date,
        limit=MAX_CONTEXT,
    )

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

    answer_text = llm_answer(question, blocks)
    return answer_text, sources


# -----------------------------
# Stateful conversational (CHAT)
# -----------------------------
def run_chat_turn(
    conversation_id: int,
    question: str,
) -> str:
    """
    Conversational turn with persistence.
    Used by /chat.
    """

    add_message(conversation_id, "user", question)

    plan_json = plan(question)
    terms = list(set(plan_json["keywords"] + plan_json["concepts"]))

    raw = retrieve(
        terms=terms,
        source_type=plan_json["source_preference"] or "both",
        limit=MAX_CONTEXT,
    )

    memory_blocks = []

    for d in raw["documents"]:
        memory_blocks.append(f"(Document: {d['source']})\n{d['content']}")

    for m in raw["meetings"]:
        memory_blocks.append(
            f"(Meeting: {m['meeting_name']})\n{m['synthesized_notes']}"
        )

    conversation = get_recent_messages(conversation_id)

    context = build_context(conversation, memory_blocks)

    answer = llm_answer(question, context)

    add_message(conversation_id, "assistant", answer)

    return answer

