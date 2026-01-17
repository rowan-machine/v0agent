# src/app/chat/turn.py

from typing import Tuple, List, Dict

from .planner import plan
from .fallback import fallback_plan
from .context import build_context
from .models import add_message, get_recent_messages

from ..memory.retrieve import retrieve
from ..memory.semantic import semantic_search
from ..memory.rank import rank_items

from ..llm import answer as llm_answer

MAX_CONTEXT = 6


# ============================================================
# Stateless single-turn orchestration (used by /query)
# ============================================================
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

    # ---------- Lexical retrieval ----------
    raw = retrieve(
        terms=terms,
        source_type=effective_source,
        start_date=start_date,
        end_date=end_date,
        limit=MAX_CONTEXT * 2,  # pull extra for hybrid merge
    )

    items: List[Dict] = []

    for d in raw["documents"]:
        items.append({
            "type": "docs",
            "id": d["id"],
            "label": d["source"],
            "content": d["content"],
            "created_at": d["created_at"],
        })

    for m in raw["meetings"]:
        items.append({
            "type": "meetings",
            "id": m["id"],
            "label": m["meeting_name"],
            "content": m["synthesized_notes"],
            "created_at": m["created_at"],
        })

    # ---------- Semantic retrieval ----------
    if effective_source in ("docs", "both"):
        for d in semantic_search(question, "doc"):
            items.append({
                "type": "docs",
                "id": d["id"],
                "label": d["source"],
                "content": d["content"],
                "created_at": d["created_at"],
            })

    if effective_source in ("meetings", "both"):
        for m in semantic_search(question, "meeting"):
            items.append({
                "type": "meetings",
                "id": m["id"],
                "label": m["meeting_name"],
                "content": m["synthesized_notes"],
                "created_at": m["created_at"],
            })

    # ---------- De-duplicate ----------
    seen = set()
    deduped = []
    for it in items:
        key = (it["type"], it["id"])
        if key not in seen:
            seen.add(key)
            deduped.append(it)

    # ---------- Rank (VX.2a logic reused) ----------
    ranked = rank_items(
        deduped,
        terms=terms,
        source_preference=plan_json["source_preference"],
        time_hint=plan_json["time_hint"],
    )

    if not ranked:
        return "I don’t have enough information in the provided sources.", []

    # ---------- Build context ----------
    blocks = []
    sources = []

    for idx, it in enumerate(ranked[:MAX_CONTEXT], start=1):
        blocks.append(f"[{idx}] ({it['type'].capitalize()}: {it['label']})\n{it['content']}")
        sources.append({
            "type": it["type"][:-1],
            "id": it["id"],
            "label": it["label"],
        })

    answer_text = llm_answer(question, blocks)
    return answer_text, sources


# ============================================================
# Stateful conversational orchestration (used by /chat)
# ============================================================
def run_chat_turn(
    conversation_id: int,
    question: str,
) -> str:
    """
    Conversational turn with persistence.
    Used by /chat.
    """

    add_message(conversation_id, "user", question)

    try:
        plan_json = plan(question)
    except Exception:
        plan_json = fallback_plan(question)

    terms = list(set(plan_json["keywords"] + plan_json["concepts"]))

    # ---------- Lexical retrieval ----------
    raw = retrieve(
        terms=terms,
        source_type=plan_json["source_preference"] or "both",
        limit=MAX_CONTEXT * 2,
    )

    items: List[Dict] = []

    for d in raw["documents"]:
        items.append({
            "type": "docs",
            "id": d["id"],
            "label": d["source"],
            "content": d["content"],
            "created_at": d["created_at"],
        })

    for m in raw["meetings"]:
        items.append({
            "type": "meetings",
            "id": m["id"],
            "label": m["meeting_name"],
            "content": m["synthesized_notes"],
            "created_at": m["created_at"],
        })

    # ---------- Semantic retrieval ----------
    for d in semantic_search(question, "doc"):
        items.append({
            "type": "docs",
            "id": d["id"],
            "label": d["source"],
            "content": d["content"],
            "created_at": d["created_at"],
        })

    for m in semantic_search(question, "meeting"):
        items.append({
            "type": "meetings",
            "id": m["id"],
            "label": m["meeting_name"],
            "content": m["synthesized_notes"],
            "created_at": m["created_at"],
        })

    # ---------- De-duplicate ----------
    seen = set()
    deduped = []
    for it in items:
        key = (it["type"], it["id"])
        if key not in seen:
            seen.add(key)
            deduped.append(it)

    # ---------- Rank ----------
    ranked = rank_items(
        deduped,
        terms=terms,
        source_preference=plan_json["source_preference"],
        time_hint=plan_json["time_hint"],
    )

    memory_blocks = []
    for it in ranked[:MAX_CONTEXT]:
        memory_blocks.append(
            f"({it['type'].capitalize()}: {it['label']})\n{it['content']}"
        )

    conversation = get_recent_messages(conversation_id)
    context = build_context(conversation, memory_blocks)

    answer = llm_answer(question, context)

    add_message(conversation_id, "assistant", answer)
    return answer
