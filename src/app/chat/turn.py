# src/app/chat/turn.py

from typing import Tuple, List, Dict

from .planner import plan
from .fallback import fallback_plan
from .context import build_context
from .models import add_message, get_recent_messages

from ..memory.retrieve import retrieve
from ..memory.semantic import semantic_search
from ..memory.rank import rank_items
from ..db import connect

from ..llm import answer as llm_answer

MAX_CONTEXT = 6


def get_meeting_content_with_screenshots(meeting_id: int, base_content: str) -> str:
    """Append screenshot summaries to meeting content if available."""
    try:
        with connect() as conn:
            screenshots = conn.execute(
                """
                SELECT image_summary FROM meeting_screenshots
                WHERE meeting_id = ? AND image_summary IS NOT NULL
                """,
                (meeting_id,)
            ).fetchall()
        
        if screenshots:
            screenshot_text = "\n\n[Meeting Screenshots]:\n" + "\n".join(
                [f"- {s['image_summary']}" for s in screenshots]
            )
            return base_content + screenshot_text
    except:
        pass
    return base_content


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
        content = get_meeting_content_with_screenshots(m["id"], m["synthesized_notes"])
        items.append({
            "type": "meetings",
            "id": m["id"],
            "label": m["meeting_name"],
            "content": content,
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
            content = get_meeting_content_with_screenshots(m["id"], m["synthesized_notes"])
            items.append({
                "type": "meetings",
                "id": m["id"],
                "label": m["meeting_name"],
                "content": content,
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
        content = get_meeting_content_with_screenshots(m["id"], m["synthesized_notes"])
        items.append({
            "type": "meetings",
            "id": m["id"],
            "label": m["meeting_name"],
            "content": content,
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
        content = get_meeting_content_with_screenshots(m["id"], m["synthesized_notes"])
        items.append({
            "type": "meetings",
            "id": m["id"],
            "label": m["meeting_name"],
            "content": content,
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

    # If no memory blocks found, try ArjunaAgent as fallback
    if not memory_blocks:
        try:
            from ..agents.arjuna import quick_ask_sync
            result = quick_ask_sync(query=question)
            if result.get("success") and result.get("response"):
                answer = result["response"]
                run_id = result.get("run_id")
                add_message(conversation_id, "assistant", answer, run_id=run_id)
                return answer, run_id
        except Exception as e:
            print(f"ArjunaAgent fallback failed: {e}")
            import traceback
            traceback.print_exc()
            pass

    conversation = get_recent_messages(conversation_id)
    context = build_context(conversation, memory_blocks)

    answer, run_id = llm_answer(question, context, return_run_id=True, thread_id=str(conversation_id))

    add_message(conversation_id, "assistant", answer, run_id=run_id)
    return answer, run_id


# ============================================================
# Conversational turn with specific meeting/document context
# ============================================================
def run_chat_turn_with_context(
    conversation_id: int,
    question: str,
    meeting_id: int = None,
    document_id: int = None,
) -> str:
    """
    Conversational turn with specific meeting/document context.
    When a meeting_id or document_id is provided, use that as primary context.
    """

    add_message(conversation_id, "user", question)

    items: List[Dict] = []
    context_names = []

    # If specific meeting is selected, prioritize it
    if meeting_id:
        with connect() as conn:
            m = conn.execute(
                "SELECT id, meeting_name, synthesized_notes, created_at FROM meeting_summaries WHERE id = ?",
                (meeting_id,)
            ).fetchone()
            if m:
                content = get_meeting_content_with_screenshots(m["id"], m["synthesized_notes"])
                items.append({
                    "type": "meetings",
                    "id": m["id"],
                    "label": m["meeting_name"],
                    "content": content,
                    "created_at": m["created_at"],
                    "priority": True,
                })
                context_names.append(f"Meeting: {m['meeting_name']}")

    # If specific document is selected, prioritize it
    if document_id:
        with connect() as conn:
            d = conn.execute(
                "SELECT id, source, content, created_at FROM documents WHERE id = ?",
                (document_id,)
            ).fetchone()
            if d:
                items.append({
                    "type": "docs",
                    "id": d["id"],
                    "label": d["source"],
                    "content": d["content"],
                    "created_at": d["created_at"],
                    "priority": True,
                })
                context_names.append(f"Document: {d['source']}")

    # Build memory blocks - priority items first with focus instruction
    memory_blocks = []
    
    # Add a strong instruction to focus only on the selected context
    if context_names:
        focus_instruction = f"""[IMPORTANT INSTRUCTION]
You are answering questions ONLY about the following specific context:
{', '.join(context_names)}

Do NOT reference or include information from any other meetings or documents.
Base your answers EXCLUSIVELY on the content provided below.
If the question cannot be answered from this specific context, say so clearly."""
        memory_blocks.append(focus_instruction)
    
    for it in items:
        memory_blocks.append(
            f"[CONTEXT - {it['type'].capitalize()}: {it['label']}]\n{it['content']}"
        )

    # If no context items found (only focus instruction), use ArjunaAgent fallback
    if len(memory_blocks) <= 1 and not items:
        try:
            from ..agents.arjuna import quick_ask_sync
            result = quick_ask_sync(query=question)
            if result.get("success") and result.get("response"):
                answer = result["response"]
                run_id = result.get("run_id")
                add_message(conversation_id, "assistant", answer, run_id=run_id)
                return answer, run_id
        except Exception as e:
            print(f"ArjunaAgent fallback failed: {e}")
            import traceback
            traceback.print_exc()
            pass

    conversation = get_recent_messages(conversation_id)
    context = build_context(conversation, memory_blocks)

    answer, run_id = llm_answer(question, context, return_run_id=True, thread_id=str(conversation_id))

    add_message(conversation_id, "assistant", answer, run_id=run_id)
    return answer, run_id
