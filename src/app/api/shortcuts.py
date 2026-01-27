# src/app/api/shortcuts.py
"""
Arjuna Shortcuts API

Provides endpoints for managing user shortcuts:
1. AI-suggested shortcuts based on common actions and conversations
2. System default shortcuts
3. Frequently used command tracking
4. CRUD operations for shortcuts

Technical Debt Item: Fix Arjuna shortcuts
- Removed user editing for now (UI-side change needed)
- Added AI-suggested shortcuts based on conversation patterns
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from ..infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ShortcutCreate(BaseModel):
    shortcut_key: str
    label: str
    message: str
    emoji: str = "💬"
    tooltip: Optional[str] = None
    source: str = "ai"  # ai, system, frequent


class ShortcutUpdate(BaseModel):
    label: Optional[str] = None
    message: Optional[str] = None
    emoji: Optional[str] = None
    tooltip: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ShortcutResponse(BaseModel):
    id: str
    shortcut_key: str
    label: str
    message: str
    emoji: str
    tooltip: Optional[str]
    source: str
    usage_count: int
    is_active: bool
    sort_order: int


# =============================================================================
# DEFAULT SYSTEM SHORTCUTS
# =============================================================================

SYSTEM_SHORTCUTS = [
    {
        "shortcut_key": "focus",
        "label": "Focus",
        "message": "What should I focus on?",
        "emoji": "🎯",
        "tooltip": "Get AI focus recommendation",
        "source": "system",
        "sort_order": 1,
    },
    {
        "shortcut_key": "blocked",
        "label": "Blocked",
        "message": "What are my blocked tickets?",
        "emoji": "🚫",
        "tooltip": "Show blocked items",
        "source": "system",
        "sort_order": 2,
    },
    {
        "shortcut_key": "tickets",
        "label": "My Tickets",
        "message": "What are my open tickets?",
        "emoji": "📋",
        "tooltip": "List open tickets",
        "source": "system",
        "sort_order": 3,
    },
    {
        "shortcut_key": "new-task",
        "label": "New Task",
        "message": "Create a task for ",
        "emoji": "➕",
        "tooltip": "Create a new task",
        "source": "system",
        "sort_order": 4,
    },
]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/api/shortcuts")
async def list_shortcuts(request: Request, include_inactive: bool = False):
    """
    List all shortcuts for the current user.
    
    Returns system defaults + AI suggestions + frequently used.
    """
    supabase = get_supabase_client()
    
    if supabase:
        return await _list_shortcuts_supabase(supabase, include_inactive)
    else:
        return await _list_shortcuts_sqlite(include_inactive)


async def _list_shortcuts_supabase(supabase, include_inactive: bool):
    """List shortcuts from Supabase."""
    try:
        query = supabase.table("user_shortcuts").select("*")
        
        if not include_inactive:
            query = query.eq("is_active", True)
        
        result = query.order("sort_order").execute()
        shortcuts = result.data or []
        
        # If no shortcuts, return system defaults
        if not shortcuts:
            return JSONResponse({
                "status": "ok",
                "shortcuts": SYSTEM_SHORTCUTS,
                "source": "system_defaults"
            })
        
        return JSONResponse({
            "status": "ok",
            "shortcuts": shortcuts,
            "source": "database"
        })
    
    except Exception as e:
        logger.error(f"Failed to list shortcuts from Supabase: {e}")
        return JSONResponse({
            "status": "ok",
            "shortcuts": SYSTEM_SHORTCUTS,
            "source": "fallback"
        })


async def _list_shortcuts_sqlite(include_inactive: bool):
    """List shortcuts from SQLite (fallback)."""
    # SQLite doesn't have the shortcuts table, return system defaults
    return JSONResponse({
        "status": "ok",
        "shortcuts": SYSTEM_SHORTCUTS,
        "source": "system_defaults"
    })


@router.post("/api/shortcuts")
async def create_shortcut(request: Request, shortcut: ShortcutCreate):
    """Create a new shortcut."""
    supabase = get_supabase_client()
    
    if not supabase:
        return JSONResponse({"error": "Supabase not configured"}, status_code=500)
    
    try:
        result = supabase.table("user_shortcuts").insert({
            "shortcut_key": shortcut.shortcut_key,
            "label": shortcut.label,
            "message": shortcut.message,
            "emoji": shortcut.emoji,
            "tooltip": shortcut.tooltip,
            "source": shortcut.source,
        }).execute()
        
        return JSONResponse({
            "status": "ok",
            "shortcut": result.data[0] if result.data else None
        })
    
    except Exception as e:
        logger.error(f"Failed to create shortcut: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/shortcuts/track-usage")
async def track_shortcut_usage(request: Request):
    """
    Track usage of a shortcut to build frequent commands list.
    
    This is called when a user uses a shortcut or sends a command.
    """
    data = await request.json()
    message = data.get("message")
    shortcut_key = data.get("shortcut_key")
    
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)
    
    supabase = get_supabase_client()
    
    if not supabase:
        # Silent fail if Supabase not configured
        return JSONResponse({"status": "ok", "tracked": False})
    
    try:
        # Check if shortcut already exists
        if shortcut_key:
            existing = supabase.table("user_shortcuts").select("id, usage_count").eq(
                "shortcut_key", shortcut_key
            ).limit(1).execute()
            
            if existing.data:
                # Update usage count
                supabase.table("user_shortcuts").update({
                    "usage_count": existing.data[0]["usage_count"] + 1,
                    "last_used_at": datetime.now().isoformat(),
                }).eq("id", existing.data[0]["id"]).execute()
                
                return JSONResponse({"status": "ok", "tracked": True, "action": "updated"})
        
        # Check if this message is a frequent command
        existing_by_message = supabase.table("user_shortcuts").select("id, usage_count").eq(
            "message", message
        ).limit(1).execute()
        
        if existing_by_message.data:
            # Update existing frequent command
            supabase.table("user_shortcuts").update({
                "usage_count": existing_by_message.data[0]["usage_count"] + 1,
                "last_used_at": datetime.now().isoformat(),
            }).eq("id", existing_by_message.data[0]["id"]).execute()
            
            return JSONResponse({"status": "ok", "tracked": True, "action": "updated"})
        
        # Create new frequent command entry
        # Generate a key from the message
        key = f"freq-{hash(message) % 10000}"
        label = message[:20] + "..." if len(message) > 20 else message
        
        supabase.table("user_shortcuts").insert({
            "shortcut_key": key,
            "label": label,
            "message": message,
            "emoji": "💬",
            "tooltip": message,
            "source": "frequent",
            "usage_count": 1,
            "last_used_at": datetime.now().isoformat(),
            "is_active": True,
            "sort_order": 100,  # Lower priority than system shortcuts
        }).execute()
        
        return JSONResponse({"status": "ok", "tracked": True, "action": "created"})
    
    except Exception as e:
        logger.error(f"Failed to track shortcut usage: {e}")
        return JSONResponse({"status": "ok", "tracked": False})


@router.post("/api/shortcuts/generate-suggestions")
async def generate_ai_suggestions(request: Request):
    """
    Generate AI-suggested shortcuts based on:
    1. Frequent conversation patterns
    2. Common command types
    3. User's workflow patterns
    """
    supabase = get_supabase_client()
    
    if not supabase:
        return JSONResponse({"error": "Supabase not configured"}, status_code=500)
    
    try:
        # Analyze recent chat messages for patterns
        messages_result = supabase.table("career_chat_updates").select(
            "message"
        ).order("created_at", desc=True).limit(50).execute()
        
        messages = [m["message"] for m in (messages_result.data or []) if m.get("message")]
        
        # Analyze patterns
        suggestions = _analyze_message_patterns(messages)
        
        # Store suggestions in shortcuts table
        for suggestion in suggestions:
            try:
                supabase.table("user_shortcuts").upsert({
                    **suggestion,
                    "source": "ai",
                }).execute()
            except Exception as e:
                logger.debug(f"Failed to upsert suggestion: {e}")
        
        return JSONResponse({
            "status": "ok",
            "suggestions": suggestions,
            "analyzed_messages": len(messages)
        })
    
    except Exception as e:
        logger.error(f"Failed to generate AI suggestions: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def _analyze_message_patterns(messages: List[str]) -> List[dict]:
    """
    Analyze message patterns to generate shortcut suggestions.
    
    This is a rule-based analyzer. Could be enhanced with LLM later.
    """
    suggestions = []
    
    # Count pattern occurrences
    patterns = {
        "ticket_status": 0,  # Questions about ticket status
        "meeting_summary": 0,  # Requests for meeting summaries
        "standup": 0,  # Standup related
        "planning": 0,  # Planning related
        "code_review": 0,  # Code review related
        "blocked": 0,  # Blocked items
        "schedule": 0,  # Schedule/calendar
    }
    
    for msg in messages:
        lower = msg.lower()
        
        if any(w in lower for w in ["ticket", "task", "status", "progress"]):
            patterns["ticket_status"] += 1
        if any(w in lower for w in ["meeting", "summary", "notes"]):
            patterns["meeting_summary"] += 1
        if any(w in lower for w in ["standup", "stand-up", "daily"]):
            patterns["standup"] += 1
        if any(w in lower for w in ["plan", "sprint", "backlog"]):
            patterns["planning"] += 1
        if any(w in lower for w in ["review", "pr", "code"]):
            patterns["code_review"] += 1
        if any(w in lower for w in ["blocked", "blocker", "waiting"]):
            patterns["blocked"] += 1
        if any(w in lower for w in ["schedule", "calendar", "meeting"]):
            patterns["schedule"] += 1
    
    # Generate suggestions for frequent patterns
    if patterns["ticket_status"] >= 3:
        suggestions.append({
            "shortcut_key": "ai-ticket-status",
            "label": "Ticket Update",
            "message": "What's the status of my tickets?",
            "emoji": "📊",
            "tooltip": "AI suggested: You frequently ask about tickets",
            "sort_order": 10,
        })
    
    if patterns["meeting_summary"] >= 2:
        suggestions.append({
            "shortcut_key": "ai-meeting-notes",
            "label": "Recent Meetings",
            "message": "What were the key points from recent meetings?",
            "emoji": "📝",
            "tooltip": "AI suggested: You frequently review meetings",
            "sort_order": 11,
        })
    
    if patterns["standup"] >= 2:
        suggestions.append({
            "shortcut_key": "ai-standup",
            "label": "Standup Prep",
            "message": "Help me prepare my standup update",
            "emoji": "🌅",
            "tooltip": "AI suggested: You frequently do standups",
            "sort_order": 12,
        })
    
    if patterns["planning"] >= 2:
        suggestions.append({
            "shortcut_key": "ai-sprint-plan",
            "label": "Sprint Planning",
            "message": "What should I prioritize this sprint?",
            "emoji": "🏃",
            "tooltip": "AI suggested: You frequently plan sprints",
            "sort_order": 13,
        })
    
    if patterns["code_review"] >= 2:
        suggestions.append({
            "shortcut_key": "ai-code-review",
            "label": "Review Code",
            "message": "What PRs need my review?",
            "emoji": "👀",
            "tooltip": "AI suggested: You frequently do code reviews",
            "sort_order": 14,
        })
    
    return suggestions


@router.delete("/api/shortcuts/{shortcut_id}")
async def delete_shortcut(shortcut_id: str):
    """Delete a shortcut (soft delete - sets is_active to false)."""
    supabase = get_supabase_client()
    
    if not supabase:
        return JSONResponse({"error": "Supabase not configured"}, status_code=500)
    
    try:
        supabase.table("user_shortcuts").update({
            "is_active": False,
            "updated_at": datetime.now().isoformat(),
        }).eq("id", shortcut_id).execute()
        
        return JSONResponse({"status": "ok", "deleted": True})
    
    except Exception as e:
        logger.error(f"Failed to delete shortcut: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/shortcuts/initialize")
async def initialize_shortcuts():
    """
    Initialize default shortcuts for a user.
    
    Called on first use to set up system defaults.
    """
    supabase = get_supabase_client()
    
    if not supabase:
        return JSONResponse({"error": "Supabase not configured"}, status_code=500)
    
    try:
        # Insert system defaults (ignore if already exist)
        for shortcut in SYSTEM_SHORTCUTS:
            try:
                supabase.table("user_shortcuts").upsert(shortcut).execute()
            except Exception:
                pass  # Ignore duplicates
        
        return JSONResponse({
            "status": "ok",
            "initialized": len(SYSTEM_SHORTCUTS)
        })
    
    except Exception as e:
        logger.error(f"Failed to initialize shortcuts: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
