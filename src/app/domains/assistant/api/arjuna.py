# src/app/domains/assistant/api/arjuna.py
"""
Arjuna Smart Assistant Routes

Provides the chat interface for the Arjuna AI assistant.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime, date, timedelta
import json
import logging

from src.app.infrastructure.supabase_client import get_supabase_client
from src.app.agents.arjuna import (
    ArjunaAgent,
    get_arjuna_agent,
    AVAILABLE_MODELS,
    SYSTEM_PAGES as ARJUNA_SYSTEM_PAGES,
    MODEL_ALIASES,
    FOCUS_KEYWORDS,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["arjuna"])


# ===== System Knowledge =====

SYSTEM_PAGES = {
    "dashboard": {"path": "/", "desc": "Main dashboard with sprint overview, workflow modes, DIKW pyramid, and quick actions"},
    "tickets": {"path": "/tickets", "desc": "View and manage all tickets/tasks in the current sprint"},
    "signals": {"path": "/signals", "desc": "Browse extracted signals from meetings - decisions, actions, blockers, risks, ideas"},
    "meetings": {"path": "/meetings", "desc": "List of all meeting summaries with extracted signals"},
    "meetings_new": {"path": "/meetings/new", "desc": "Create a new meeting summary from notes or transcript"},
    "documents": {"path": "/documents", "desc": "Document library for storing and searching documents"},
    "documents_new": {"path": "/documents/new", "desc": "Create a new document"},
    "career": {"path": "/career", "desc": "Career development dashboard with profile, skills, and insights"},
    "standups": {"path": "/career/standups", "desc": "Daily standup logs and career journal chat"},
    "settings": {"path": "/settings", "desc": "App settings, sprint configuration, and workflow modes"},
    "sprint_settings": {"path": "/settings#sprint", "desc": "Configure sprint name, dates, and length"},
    "search": {"path": "/search", "desc": "Search across all content - meetings, documents, tickets"},
    "query": {"path": "/query", "desc": "AI-powered natural language query interface"},
    "dikw": {"path": "/dikw", "desc": "DIKW Pyramid knowledge visualization - Data, Information, Knowledge, Wisdom"},
}


def get_follow_up_suggestions(action: str, intent: str, result: dict) -> list:
    """Generate contextual follow-up suggestions based on action performed."""
    
    default_suggestions = [
        {"emoji": "📋", "text": "My Tickets", "message": "What are my open tickets?"},
        {"emoji": "🎯", "text": "Focus", "message": "What should I focus on today?"},
        {"emoji": "💡", "text": "Help", "message": "What else can you help me with?"},
    ]
    
    if action == "create_ticket":
        return [
            {"emoji": "➕", "text": "Create Another", "message": "Create a task for "},
            {"emoji": "📋", "text": "View Tickets", "message": "Show me all my tickets"},
            {"emoji": "🎯", "text": "High Priority", "message": "What are my high priority tickets?"},
        ]
    
    elif action == "list_tickets":
        tickets = result.get("tickets", [])
        suggestions = [{"emoji": "➕", "text": "New Task", "message": "Create a task for "}]
        if any(t.get("status") == "blocked" for t in tickets):
            suggestions.append({"emoji": "🚫", "text": "Unblock", "message": "Help me unblock a ticket"})
        if any(t.get("status") == "in_progress" for t in tickets):
            suggestions.append({"emoji": "✅", "text": "Complete", "message": "Mark a ticket as done"})
        suggestions.append({"emoji": "🔍", "text": "Filter", "message": "Show blocked tickets"})
        return suggestions[:4]
    
    elif action == "change_model":
        return [
            {"emoji": "🤖", "text": "Try GPT-4o", "message": "Switch to GPT-4o"},
            {"emoji": "🧠", "text": "Try Claude", "message": "Switch to Claude Sonnet"},
            {"emoji": "⚡", "text": "Fast Model", "message": "Switch to GPT-4o-mini"},
        ]
    
    elif action == "focus_recommendations":
        return [
            {"emoji": "📋", "text": "View Tickets", "message": "Show me all my tickets"},
            {"emoji": "🚫", "text": "Blockers", "message": "What are my blocked tickets?"},
            {"emoji": "➕", "text": "New Task", "message": "Create a task for "},
            {"emoji": "📊", "text": "Sprint", "message": "What is the sprint status?"},
        ]
    
    elif intent == "help" or intent == "explain":
        return [
            {"emoji": "📋", "text": "My Tickets", "message": "What are my tickets?"},
            {"emoji": "🤖", "text": "Change Model", "message": "Switch to GPT-4o"},
            {"emoji": "📅", "text": "Meetings", "message": "Search meetings for "},
            {"emoji": "➕", "text": "New Task", "message": "Create a task for "},
        ]
    
    return default_suggestions


def get_focus_recommendations() -> dict:
    """Generate smart focus recommendations based on current state."""
    recommendations = []
    
    supabase = get_supabase_client()
    if not supabase:
        return {"recommendations": [], "total_count": 0}
    
    # 1. BLOCKED TICKETS
    blocked_result = supabase.table("tickets").select("ticket_id, title, description").eq("status", "blocked").order("priority", desc=True).order("updated_at", desc=True).limit(3).execute()
    blocked = blocked_result.data or []
    if blocked:
        for t in blocked:
            recommendations.append({
                "priority": 1,
                "type": "blocker",
                "title": f"🚧 Unblock: {t.get('ticket_id')}",
                "text": t.get('title', ''),
                "reason": "Blocked tickets prevent all downstream work",
                "action": f"Review and unblock {t.get('ticket_id')}"
            })
    
    # 2. HIGH PRIORITY IN-PROGRESS
    in_progress_result = supabase.table("tickets").select("ticket_id, title").eq("status", "in_progress").order("priority", desc=True).order("updated_at").limit(2).execute()
    in_progress = in_progress_result.data or []
    if in_progress:
        for t in in_progress:
            recommendations.append({
                "priority": 2,
                "type": "active",
                "title": f"🏃 Complete: {t.get('ticket_id')}",
                "text": t.get('title', ''),
                "reason": "Finishing in-progress work reduces context switching",
                "action": "Continue working on this ticket"
            })
    
    # 3. SPRINT DEADLINE CHECK
    sprint_result = supabase.table("sprint_settings").select("*").eq("id", 1).execute()
    sprints = sprint_result.data or []
    if sprints and sprints[0].get('start_date'):
        sprint = sprints[0]
        try:
            start = datetime.strptime(sprint['start_date'], '%Y-%m-%d')
            length = sprint.get('length_days') or 14
            end = start + timedelta(days=length)
            days_left = (end - datetime.now()).days
            
            if days_left <= 3 and days_left > 0:
                todo_result = supabase.table("tickets").select("id", count="exact").eq("status", "todo").execute()
                todo_count = todo_result.count or 0
                if todo_count > 0:
                    recommendations.append({
                        "priority": 2,
                        "type": "deadline",
                        "title": f"⏰ Sprint ends in {days_left} day{'s' if days_left != 1 else ''}",
                        "text": f"{todo_count} items still in todo",
                        "reason": "Time is running out - consider scope reduction",
                        "action": "Review remaining work and prioritize ruthlessly"
                    })
        except:
            pass
    
    # 4. WAITING-FOR ITEMS
    waiting_result = supabase.table("accountability_items").select("description, responsible_party").eq("status", "waiting").order("created_at").limit(2).execute()
    waiting = waiting_result.data or []
    for w in waiting:
        recommendations.append({
            "priority": 4,
            "type": "waiting",
            "title": f"⏳ Follow up: {w.get('responsible_party', 'Unknown')}",
            "text": (w.get('description') or '')[:60],
            "reason": "Dependencies on others can become blockers",
            "action": f"Check in with {w.get('responsible_party', 'Unknown')}"
        })
    
    # Sort by priority
    recommendations.sort(key=lambda r: r['priority'])
    return {
        "recommendations": recommendations[:5],
        "total_count": len(recommendations)
    }


def get_system_context() -> dict:
    """Get current system state for assistant context."""
    supabase = get_supabase_client()
    if not supabase:
        return {
            "sprint": None,
            "current_ai_model": "gpt-4o-mini",
            "available_models": AVAILABLE_MODELS,
            "ticket_stats": {},
            "recent_tickets": [],
            "recent_meetings": [],
            "waiting_for": [],
            "todays_standups": [],
            "career_profile": None,
            "available_pages": SYSTEM_PAGES
        }
    
    # Get sprint info
    sprint_result = supabase.table("sprint_settings").select("*").eq("id", 1).execute()
    sprints = sprint_result.data or []
    sprint = sprints[0] if sprints else None
    
    # Get current AI model
    model_result = supabase.table("settings").select("value").eq("key", "ai_model").execute()
    models = model_result.data or []
    current_model = models[0]["value"] if models else "gpt-4o-mini"
    
    # Get ticket counts by status
    tickets_result = supabase.table("tickets").select("status").execute()
    tickets_all = tickets_result.data or []
    ticket_stats = {}
    for t in tickets_all:
        status = t.get("status", "unknown")
        ticket_stats[status] = ticket_stats.get(status, 0) + 1
    
    # Get recent tickets
    recent_result = supabase.table("tickets").select("ticket_id, title, status, priority").order("created_at", desc=True).limit(10).execute()
    recent_tickets = recent_result.data or []
    
    # Get recent meetings
    meetings_result = supabase.table("meetings").select("meeting_name, signals, meeting_date").not_.is_("signals", "null").order("meeting_date", desc=True).limit(3).execute()
    recent_meetings = meetings_result.data or []

    # Get accountability items
    accountability_result = supabase.table("accountability_items").select("description, responsible_party, status").eq("status", "waiting").limit(5).execute()
    waiting_for = accountability_result.data or []
    
    # Get today's standups
    today = date.today().isoformat()
    standups_result = supabase.table("standup_updates").select("standup_date, content, feedback, sentiment, created_at").eq("standup_date", today).order("created_at", desc=True).limit(3).execute()
    todays_standups = standups_result.data or []
    
    # Get career profile
    profile_result = supabase.table("career_profile").select("current_role, target_role").eq("id", 1).execute()
    profiles = profile_result.data or []
    career_profile = profiles[0] if profiles else None
    
    return {
        "sprint": sprint,
        "current_ai_model": current_model,
        "available_models": AVAILABLE_MODELS,
        "ticket_stats": ticket_stats,
        "recent_tickets": recent_tickets,
        "recent_meetings": recent_meetings,
        "waiting_for": waiting_for,
        "todays_standups": todays_standups,
        "career_profile": career_profile,
        "available_pages": SYSTEM_PAGES
    }


# ===== Routes =====

@router.post("/chat")
async def arjuna_chat(request: Request):
    """Main Arjuna chat endpoint."""
    from src.app.agents.arjuna import get_arjuna_agent
    
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        history = data.get("history", [])
        thread_id = data.get("thread_id")
        
        if not message:
            return JSONResponse({"error": "Message is required"}, status_code=400)
        
        agent = get_arjuna_agent()
        
        # Check for focus keywords
        focus_keywords = ['focus', 'should i do', 'what next', 'prioritize', 'work on today', 'start with']
        if any(kw in message.lower() for kw in focus_keywords):
            focus_data = get_focus_recommendations()
            recs = focus_data.get('recommendations', [])
            
            if recs:
                response_parts = ["Hare Krishna! 🙏 Here's what I recommend you focus on:\n"]
                for i, rec in enumerate(recs[:5], 1):
                    response_parts.append(f"**{i}. {rec['title']}**")
                    response_parts.append(f"   {rec['text']}")
                    response_parts.append(f"   _Why:_ {rec['reason']}\n")
                
                return JSONResponse({
                    "success": True,
                    "response": "\n".join(response_parts),
                    "intent": "focus_recommendations",
                    "suggestions": get_follow_up_suggestions("focus_recommendations", "focus", {}),
                })
        
        # Use ArjunaAgent for all other queries
        result = await agent.quick_ask(query=message)
        
        return JSONResponse({
            "success": result.get("success", True),
            "response": result.get("response", ""),
            "intent": "ask_question",
            "run_id": agent.last_run_id,
            "suggestions": get_follow_up_suggestions("ask_question", "ask", result),
        })
        
    except Exception as e:
        logger.error(f"Arjuna chat error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/context")
async def get_context():
    """Get current system context for the assistant."""
    context = get_system_context()
    return JSONResponse(context)


@router.get("/capabilities")
async def get_capabilities():
    """Get assistant capabilities."""
    return JSONResponse({
        "name": "Arjuna",
        "available_models": AVAILABLE_MODELS,
        "available_pages": SYSTEM_PAGES,
        "capabilities": [
            "Task Management",
            "System Settings",
            "Accountability Tracking",
            "Standups & Career",
            "Search & Query",
            "Navigation",
        ],
    })


__all__ = ["router", "get_follow_up_suggestions", "get_focus_recommendations", "get_system_context"]
