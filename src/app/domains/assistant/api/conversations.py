# src/app/domains/assistant/api/conversations.py
"""
Chat Conversation Routes

Manages chat conversations, messages, and conversation lifecycle.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import json
import os
import logging
from urllib.parse import urlencode

from ....infrastructure.supabase_client import get_supabase_client
from ....chat.models import (
    create_conversation,
    get_recent_messages,
    get_all_conversations,
    get_conversation,
    update_conversation_title,
    delete_conversation,
    archive_conversation,
    unarchive_conversation,
    update_conversation_context,
)
from ....chat.turn import run_chat_turn, run_chat_turn_with_context

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversations"])
templates = Jinja2Templates(directory="src/app/templates")
templates.env.globals['env'] = os.environ


def _get_supabase():
    """Get Supabase client."""
    return get_supabase_client()


def preserve_auth_redirect(url: str, request: Request, extra_params: dict = None) -> str:
    """Build redirect URL preserving auth token if present."""
    params = {}
    token = request.query_params.get("token")
    if token:
        params["token"] = token
    if extra_params:
        params.update(extra_params)
    if params:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{urlencode(params)}"
    return url


def get_meetings_for_selector(limit: int = 50):
    """Get recent meetings for the context selector from Supabase."""
    try:
        sb = _get_supabase()
        result = sb.table("meetings").select(
            "id, meeting_name, meeting_date"
        ).order("meeting_date", desc=True).limit(limit).execute()
        
        meetings = []
        for m in result.data or []:
            meetings.append({
                "id": m["id"],
                "meeting_name": m["meeting_name"],
                "meeting_date": m.get("meeting_date"),
                "linked_doc_id": None
            })
        return meetings
    except Exception as e:
        logger.error(f"Error fetching meetings: {e}")
        return []


def get_documents_for_selector(limit: int = 50):
    """Get recent documents for the context selector from Supabase."""
    try:
        sb = _get_supabase()
        result = sb.table("documents").select(
            "id, source, created_at"
        ).order("created_at", desc=True).limit(limit).execute()
        
        return [dict(d) for d in result.data or []]
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return []


def get_recent_signals_for_context(days: int = 14, limit: int = 8):
    """Get recent signals for the context panel from Supabase."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    try:
        sb = _get_supabase()
        result = sb.table("meetings").select(
            "meeting_name, signals, meeting_date"
        ).not_.is_("signals", "null").gte(
            "meeting_date", cutoff[:10]
        ).order("meeting_date", desc=True).limit(10).execute()
        
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
        
        for m in result.data or []:
            try:
                data = m.get("signals") or {}
                if isinstance(data, str):
                    data = json.loads(data)
                
                for stype in ["blockers", "action_items", "decisions", "risks", "ideas"]:
                    items = data.get(stype, [])
                    if isinstance(items, list):
                        for item in items[:2]:
                            if item and len(signals) < limit:
                                if isinstance(item, dict):
                                    text = item.get("text") or item.get("description") or str(item)
                                else:
                                    text = str(item)
                                signals.append({
                                    "text": text,
                                    "type": type_classes.get(stype, ""),
                                    "type_label": type_labels.get(stype, stype),
                                    "source": m["meeting_name"]
                                })
            except Exception as e:
                logger.debug(f"Error parsing signals: {e}")
        
        return signals[:limit]
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        return []


def get_sprint_stats(days: int = 14):
    """Get signal counts for current sprint period from Supabase."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()[:10]
    
    try:
        sb = _get_supabase()
        result = sb.table("meetings").select(
            "signals"
        ).not_.is_("signals", "null").gte("meeting_date", cutoff).execute()
        
        blockers = 0
        actions = 0
        
        for m in result.data or []:
            try:
                data = m.get("signals") or {}
                if isinstance(data, str):
                    data = json.loads(data)
                
                b = data.get("blockers", [])
                a = data.get("action_items", [])
                if isinstance(b, list):
                    blockers += len(b)
                if isinstance(a, list):
                    actions += len(a)
            except:
                pass
        
        return {"blockers": blockers, "actions": actions}
    except Exception as e:
        logger.error(f"Error fetching sprint stats: {e}")
        return {"blockers": 0, "actions": 0}


def generate_chat_title(first_message: str) -> str:
    """Generate a short title from the first message using LLM."""
    prompt = f"""Generate a very short title (3-6 words max) for a conversation that starts with this message:

"{first_message[:500]}"

Return ONLY the title, no quotes, no explanation."""
    
    try:
        from src.app.llm import ask
        title = ask(prompt, model="gpt-4.1-mini")
        return title.strip()[:100]
    except:
        words = first_message.split()[:5]
        return " ".join(words)[:50] + ("..." if len(words) > 5 else "")


def _get_meeting_name(meeting_id: int) -> str:
    """Get meeting name from Supabase."""
    try:
        sb = _get_supabase()
        result = sb.table("meetings").select("meeting_name").eq("id", meeting_id).execute()
        if result.data:
            return result.data[0]["meeting_name"]
    except:
        pass
    return None


def _get_document_name(document_id: int) -> str:
    """Get document name from Supabase."""
    try:
        sb = _get_supabase()
        result = sb.table("documents").select("source").eq("id", document_id).execute()
        if result.data:
            return result.data[0]["source"]
    except:
        pass
    return None


# ===== Routes =====

@router.get("/conversations")
def chat_history(request: Request):
    """Show chat history page with all conversations."""
    conversations = get_all_conversations(limit=50)
    recent_signals = get_recent_signals_for_context()
    sprint_stats = get_sprint_stats()
    meetings_list = get_meetings_for_selector()
    documents_list = get_documents_for_selector()
    
    return templates.TemplateResponse(
        "chat_history.html",
        {
            "request": request,
            "conversations": conversations,
            "active_conversation": None,
            "messages": [],
            "recent_signals": recent_signals,
            "sprint_stats": sprint_stats,
            "meetings_list": meetings_list,
            "documents_list": documents_list,
        },
    )


@router.get("/conversations/new")
def new_chat(request: Request, prompt: str = None):
    """Create a new conversation and redirect to it."""
    cid = create_conversation()
    base_url = f"/assistant/conversations/{cid}"
    extra_params = {"prompt": prompt} if prompt else None
    return RedirectResponse(url=preserve_auth_redirect(base_url, request, extra_params), status_code=303)


@router.get("/conversations/{conversation_id}")
def view_chat(request: Request, conversation_id: int, prompt: str = None):
    """View a specific conversation within the chat history page."""
    conversations = get_all_conversations(limit=50)
    conversation = get_conversation(conversation_id)
    
    if not conversation:
        return RedirectResponse(url=preserve_auth_redirect("/assistant/conversations", request), status_code=303)
    
    meeting_id = conversation.get("meeting_id")
    document_id = conversation.get("document_id")
    
    messages = get_recent_messages(conversation_id, limit=50)
    
    recent_signals = get_recent_signals_for_context()
    sprint_stats = get_sprint_stats()
    meetings_list = get_meetings_for_selector()
    documents_list = get_documents_for_selector()
    
    selected_meeting = None
    selected_document = None
    if meeting_id:
        name = _get_meeting_name(meeting_id)
        if name:
            selected_meeting = {"id": meeting_id, "name": name}
    
    if document_id:
        name = _get_document_name(document_id)
        if name:
            selected_document = {"id": document_id, "name": name}
    
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
            "prefill_prompt": prompt,
            "meetings_list": meetings_list,
            "documents_list": documents_list,
            "selected_meeting": selected_meeting,
            "selected_document": selected_document,
        },
    )


@router.post("/conversations/{conversation_id}")
def chat_turn(
    request: Request,
    conversation_id: int,
    message: str = Form(...),
):
    """Process a chat turn and return the updated view."""
    conversation = get_conversation(conversation_id)
    
    meeting_id = None
    document_id = None
    if conversation:
        meeting_id = conversation.get("meeting_id")
        document_id = conversation.get("document_id")
    
    if meeting_id or document_id:
        answer, run_id = run_chat_turn_with_context(conversation_id, message, meeting_id, document_id)
    else:
        answer, run_id = run_chat_turn(conversation_id, message)
    
    if conversation and not conversation.get("title"):
        title = generate_chat_title(message)
        update_conversation_title(conversation_id, title)
    
    conversations = get_all_conversations(limit=50)
    messages = get_recent_messages(conversation_id, limit=50)
    conversation = get_conversation(conversation_id)
    recent_signals = get_recent_signals_for_context()
    sprint_stats = get_sprint_stats()
    meetings_list = get_meetings_for_selector()
    documents_list = get_documents_for_selector()
    
    meeting_id = conversation.get("meeting_id") if conversation else None
    document_id = conversation.get("document_id") if conversation else None
    
    selected_meeting = None
    selected_document = None
    if meeting_id:
        name = _get_meeting_name(meeting_id)
        if name:
            selected_meeting = {"id": meeting_id, "name": name}
    if document_id:
        name = _get_document_name(document_id)
        if name:
            selected_document = {"id": document_id, "name": name}
    
    return templates.TemplateResponse(
        "chat_history.html",
        {
            "request": request,
            "conversations": conversations,
            "active_conversation": conversation,
            "conversation_id": conversation_id,
            "messages": messages,
            "answer": answer,
            "last_run_id": run_id,
            "recent_signals": recent_signals,
            "sprint_stats": sprint_stats,
            "meetings_list": meetings_list,
            "documents_list": documents_list,
            "selected_meeting": selected_meeting,
            "selected_document": selected_document,
        },
    )


@router.post("/conversations/{conversation_id}/send")
async def send_chat_message(conversation_id: int, request: Request):
    """Send a message via AJAX and get the response without page reload."""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        
        if not message:
            return JSONResponse({"error": "Message is required"}, status_code=400)
        
        conversation = get_conversation(conversation_id)
        if not conversation:
            return JSONResponse({"error": "Conversation not found"}, status_code=404)
        
        meeting_id = conversation.get("meeting_id")
        document_id = conversation.get("document_id")
        
        if meeting_id or document_id:
            answer, run_id = run_chat_turn_with_context(conversation_id, message, meeting_id, document_id)
        else:
            answer, run_id = run_chat_turn(conversation_id, message)
        
        if not conversation.get("title"):
            title = generate_chat_title(message)
            update_conversation_title(conversation_id, title)
        
        return JSONResponse({
            "success": True,
            "response": answer,
            "run_id": run_id,
            "conversation_id": conversation_id,
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/conversations/{conversation_id}")
def delete_chat(conversation_id: int):
    """Delete a conversation permanently."""
    delete_conversation(conversation_id)
    return JSONResponse({"status": "ok", "deleted": conversation_id})


@router.post("/conversations/{conversation_id}/archive")
def archive_chat(conversation_id: int):
    """Archive a conversation."""
    archive_conversation(conversation_id)
    return JSONResponse({"status": "ok", "archived": conversation_id})


@router.post("/conversations/{conversation_id}/unarchive")
def unarchive_chat(conversation_id: int):
    """Unarchive (restore) a conversation."""
    unarchive_conversation(conversation_id)
    return JSONResponse({"status": "ok", "unarchived": conversation_id})


@router.post("/conversations/{conversation_id}/title")
def update_chat_title(request: Request, conversation_id: int, title: str = Form(...)):
    """Update conversation title."""
    update_conversation_title(conversation_id, title)
    return RedirectResponse(url=preserve_auth_redirect(f"/assistant/conversations/{conversation_id}", request), status_code=303)


@router.post("/conversations/{conversation_id}/context")
async def update_chat_context(conversation_id: int, request: Request):
    """Update the meeting/document context for a conversation."""
    try:
        data = await request.json()
        meeting_id = data.get("meeting_id")
        document_id = data.get("document_id")
        
        meeting_id = int(meeting_id) if meeting_id else None
        document_id = int(document_id) if document_id else None
        
        update_conversation_context(conversation_id, meeting_id, document_id)
        return JSONResponse({"status": "ok", "meeting_id": meeting_id, "document_id": document_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ===== Sprint Stats API =====

@router.get("/sprint-stats")
def api_sprint_stats():
    """API endpoint for sprint stats."""
    stats = get_sprint_stats()
    return JSONResponse(stats)


# Cache for sprint signals
_sprint_signals_cache = {
    "blockers": {"data": None, "timestamp": 0},
    "action_items": {"data": None, "timestamp": 0}
}
_SIGNALS_CACHE_TTL = 120  # 2 minutes


@router.get("/sprint-signals/{signal_type}")
def api_sprint_signals(signal_type: str, days: int = 14, force: bool = False):
    """Get actual signal items (blockers or actions) for the sprint period."""
    import time
    
    if signal_type not in ["blockers", "action_items"]:
        return JSONResponse({"error": "Invalid signal type"}, status_code=400)
    
    now = time.time()
    cache_entry = _sprint_signals_cache.get(signal_type, {"data": None, "timestamp": 0})
    if not force and cache_entry["data"] is not None and (now - cache_entry["timestamp"]) < _SIGNALS_CACHE_TTL:
        return JSONResponse(cache_entry["data"])
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()[:10]
    
    try:
        sb = _get_supabase()
        result = sb.table("meetings").select(
            "id, meeting_name, meeting_date, signals"
        ).not_.is_("signals", "null").gte(
            "meeting_date", cutoff
        ).order("meeting_date", desc=True).execute()
        
        signals = []
        for m in result.data or []:
            try:
                data = m.get("signals") or {}
                if isinstance(data, str):
                    data = json.loads(data)
                
                items = data.get(signal_type, [])
                if isinstance(items, list):
                    for item in items:
                        text = item if isinstance(item, str) else item.get("text", str(item))
                        signals.append({
                            "id": f"{m['id']}_{len(signals)}",
                            "meeting_id": m["id"],
                            "meeting_name": m["meeting_name"],
                            "meeting_date": m.get("meeting_date"),
                            "text": text,
                            "type": signal_type
                        })
            except:
                pass
        
        result_data = {"signals": signals, "count": len(signals)}
        _sprint_signals_cache[signal_type] = {"data": result_data, "timestamp": time.time()}
        
        return JSONResponse(result_data)
    except Exception as e:
        logger.error(f"Error fetching sprint signals: {e}")
        return JSONResponse({"signals": [], "count": 0})


@router.post("/signal-action")
def api_signal_action(request: Request, signal_id: str = Form(...), action: str = Form(...)):
    """Handle approve/reject/archive actions on signals."""
    return JSONResponse({"status": "ok", "signal_id": signal_id, "action": action})


__all__ = ["router"]
