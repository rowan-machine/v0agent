# src/app/api/chat.py

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import json
from ..db import connect
from ..chat.models import (
    create_conversation,
    get_recent_messages,
    get_all_conversations,
    get_conversation,
    update_conversation_title,
    delete_conversation,
    archive_conversation,
    unarchive_conversation,
)
from ..chat.turn import run_chat_turn
from ..llm import ask

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


def get_recent_signals_for_context(days: int = 14, limit: int = 8):
    """Get recent signals for the context panel."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    with connect() as conn:
        meetings = conn.execute(
            """
            SELECT meeting_name, signals_json, meeting_date
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL
            AND (meeting_date >= ? OR (meeting_date IS NULL AND created_at >= ?))
            ORDER BY COALESCE(meeting_date, created_at) DESC
            LIMIT 10
            """,
            (cutoff, cutoff)
        ).fetchall()
    
    signals = []
    type_labels = {
        "decisions": "Decision",
        "action_items": "Action",
        "blockers": "Blocker",
        "risks": "Risk",
        "ideas": "Idea"
    }
    type_classes = {
        "decisions": "decision",
        "action_items": "action",
        "blockers": "blocker",
        "risks": "risk",
        "ideas": "idea"
    }
    
    for m in meetings:
        try:
            data = json.loads(m["signals_json"])
            for stype in ["blockers", "action_items", "decisions", "risks", "ideas"]:
                items = data.get(stype, [])
                if isinstance(items, list):
                    for item in items[:2]:
                        if item and len(signals) < limit:
                            signals.append({
                                "text": item,
                                "type": type_classes.get(stype, ""),
                                "type_label": type_labels.get(stype, stype),
                                "source": m["meeting_name"]
                            })
        except:
            pass
    
    return signals[:limit]


def get_sprint_stats(days: int = 14):
    """Get signal counts for current sprint period."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    with connect() as conn:
        meetings = conn.execute(
            """
            SELECT signals_json
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL
            AND (meeting_date >= ? OR (meeting_date IS NULL AND created_at >= ?))
            """,
            (cutoff, cutoff)
        ).fetchall()
    
    blockers = 0
    actions = 0
    
    for m in meetings:
        try:
            data = json.loads(m["signals_json"])
            b = data.get("blockers", [])
            a = data.get("action_items", [])
            if isinstance(b, list):
                blockers += len(b)
            if isinstance(a, list):
                actions += len(a)
        except:
            pass
    
    return {"blockers": blockers, "actions": actions}


def generate_chat_title(first_message: str) -> str:
    """Generate a short title from the first message using LLM."""
    prompt = f"""Generate a very short title (3-6 words max) for a conversation that starts with this message:

"{first_message[:500]}"

Return ONLY the title, no quotes, no explanation."""
    
    try:
        title = ask(prompt, model="gpt-4.1-mini")
        return title.strip()[:100]  # Limit to 100 chars
    except:
        # Fallback to first few words
        words = first_message.split()[:5]
        return " ".join(words)[:50] + ("..." if len(words) > 5 else "")


@router.get("/chat")
def chat_history(request: Request):
    """Show chat history page with all conversations."""
    conversations = get_all_conversations(limit=50)
    recent_signals = get_recent_signals_for_context()
    sprint_stats = get_sprint_stats()
    
    return templates.TemplateResponse(
        "chat_history.html",
        {
            "request": request,
            "conversations": conversations,
            "active_conversation": None,
            "messages": [],
            "recent_signals": recent_signals,
            "sprint_stats": sprint_stats,
        },
    )


@router.get("/chat/new")
def new_chat(request: Request, prompt: str = None):
    """Create a new conversation and redirect to it."""
    cid = create_conversation()
    if prompt:
        # If prompt provided, redirect with it as a query param to pre-fill
        return RedirectResponse(url=f"/chat/{cid}?prompt={prompt}", status_code=303)
    return RedirectResponse(url=f"/chat/{cid}", status_code=303)


@router.get("/chat/{conversation_id}")
def view_chat(request: Request, conversation_id: int, prompt: str = None):
    """View a specific conversation within the chat history page."""
    conversations = get_all_conversations(limit=50)
    conversation = get_conversation(conversation_id)
    
    if not conversation:
        return RedirectResponse(url="/chat", status_code=303)
    
    messages = get_recent_messages(conversation_id, limit=50)
    recent_signals = get_recent_signals_for_context()
    sprint_stats = get_sprint_stats()
    
    return templates.TemplateResponse(
        "chat_history.html",
        {
            "request": request,
            "conversations": conversations,
            "active_conversation": conversation,
            "conversation_id": conversation_id,
            "messages": messages,
            "answer": None,
            "recent_signals": recent_signals,
            "sprint_stats": sprint_stats,
            "prefill_prompt": prompt,  # Pass prompt to template for pre-filling
        },
    )


@router.post("/chat/{conversation_id}")
def chat_turn(
    request: Request,
    conversation_id: int,
    message: str = Form(...),
):
    """Process a chat turn and return the updated view."""
    # Get conversation to check if it needs a title
    conversation = get_conversation(conversation_id)
    
    # Run the chat turn
    answer = run_chat_turn(conversation_id, message)
    
    # Generate title if this is the first message
    if conversation and not conversation["title"]:
        title = generate_chat_title(message)
        update_conversation_title(conversation_id, title)
    
    # Get updated data
    conversations = get_all_conversations(limit=50)
    messages = get_recent_messages(conversation_id, limit=50)
    conversation = get_conversation(conversation_id)  # Refresh after title update
    recent_signals = get_recent_signals_for_context()
    sprint_stats = get_sprint_stats()
    
    return templates.TemplateResponse(
        "chat_history.html",
        {
            "request": request,
            "conversations": conversations,
            "active_conversation": conversation,
            "conversation_id": conversation_id,
            "messages": messages,
            "answer": answer,
            "recent_signals": recent_signals,
            "sprint_stats": sprint_stats,
        },
    )


@router.delete("/chat/{conversation_id}")
def delete_chat(conversation_id: int):
    """Delete a conversation permanently."""
    delete_conversation(conversation_id)
    return JSONResponse({"status": "ok", "deleted": conversation_id})


@router.post("/chat/{conversation_id}/archive")
def archive_chat(conversation_id: int):
    """Archive a conversation."""
    archive_conversation(conversation_id)
    return JSONResponse({"status": "ok", "archived": conversation_id})


@router.post("/chat/{conversation_id}/unarchive")
def unarchive_chat(conversation_id: int):
    """Unarchive (restore) a conversation."""
    unarchive_conversation(conversation_id)
    return JSONResponse({"status": "ok", "unarchived": conversation_id})


@router.post("/chat/{conversation_id}/title")
def update_chat_title(conversation_id: int, title: str = Form(...)):
    """Update conversation title."""
    update_conversation_title(conversation_id, title)
    return RedirectResponse(url=f"/chat/{conversation_id}", status_code=303)


@router.get("/api/sprint-stats")
def api_sprint_stats():
    """API endpoint for sprint stats."""
    stats = get_sprint_stats()
    return JSONResponse(stats)


@router.get("/api/sprint-signals/{signal_type}")
def api_sprint_signals(signal_type: str, days: int = 14):
    """Get actual signal items (blockers or actions) for the sprint period."""
    if signal_type not in ["blockers", "action_items"]:
        return JSONResponse({"error": "Invalid signal type"}, status_code=400)
    
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    with connect() as conn:
        meetings = conn.execute(
            """
            SELECT id, meeting_name, meeting_date, signals_json
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL
            AND (meeting_date >= ? OR (meeting_date IS NULL AND created_at >= ?))
            ORDER BY meeting_date DESC, created_at DESC
            """,
            (cutoff, cutoff)
        ).fetchall()
    
    signals = []
    for m in meetings:
        try:
            data = json.loads(m["signals_json"])
            items = data.get(signal_type, [])
            if isinstance(items, list):
                for item in items:
                    text = item if isinstance(item, str) else item.get("text", str(item))
                    signals.append({
                        "id": f"{m['id']}_{len(signals)}",
                        "meeting_id": m["id"],
                        "meeting_name": m["meeting_name"],
                        "meeting_date": m["meeting_date"],
                        "text": text,
                        "type": signal_type
                    })
        except:
            pass
    
    return JSONResponse({"signals": signals, "count": len(signals)})


@router.post("/api/signal-action")
def api_signal_action(request: Request, signal_id: str = Form(...), action: str = Form(...)):
    """Handle approve/reject/archive actions on signals."""
    # For now, just log the action - you could store this in DB
    # action can be: approve, reject, archive
    return JSONResponse({"status": "ok", "signal_id": signal_id, "action": action})


