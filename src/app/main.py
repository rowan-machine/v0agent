from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import json
import logging
import os
import re

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# SQLite imports removed - using Supabase-only mode
from .meetings import router as meetings_router
from .documents import router as documents_router
from .search import router as search_router
from .query import router as query_router
from .signals import router as signals_router
from .tickets import router as tickets_router
from .test_plans import router as test_plans_router
from .chat import models as chat_models  # Chat module functions
from .api.chat import router as chat_router
from .api.mcp import router as mcp_router
from .api.accountability import router as accountability_router
from .api.settings import router as settings_router
from .api.assistant import router as assistant_router
from .api.career import router as career_router
from .api.v1 import router as v1_router  # API v1 (Phase 3.1)
from .api.mobile import router as mobile_router  # Mobile sync (Phase 3.2)
from .api.admin import router as admin_router  # Admin endpoints (Phase 4.1)
from .api.search import router as api_search_router  # Semantic/Hybrid search (Phase 5.2)
from .api.knowledge_graph import router as knowledge_graph_router  # Knowledge graph (Phase 5.10)
from .api.shortcuts import router as shortcuts_router  # Arjuna shortcuts (Technical Debt)
from .api.dikw import router as dikw_router  # DIKW pyramid (Refactor Phase 2)
from .api.mindmap import router as mindmap_router  # Mindmap visualization (Refactor Phase 2)
from .api.notifications import router as notifications_router  # Notifications (Refactor Phase 2)
from .api.workflow import router as workflow_router  # Workflow modes & timer (Refactor Phase 2)
from .api.reports import router as reports_router  # Reports & analytics (Refactor Phase 2)
from .api.evaluations import router as evaluations_router  # LangSmith evaluations (Refactor Phase 2)
from .api.pocket import router as pocket_router  # Pocket integration (Refactor Phase 2)
from .mcp.registry import TOOL_REGISTRY
from .llm import ask as ask_llm
from .auth import (
    AuthMiddleware, get_login_page, create_session, 
    destroy_session, get_auth_password, hash_password
)
from .integrations.pocket import PocketClient, extract_latest_summary, extract_transcript_text, extract_mind_map, extract_action_items, get_all_summary_versions, get_all_mind_map_versions
from .services import meetings_supabase  # Supabase-first meeting reads
from .services import documents_supabase  # Supabase-first document reads
from .services import tickets_supabase  # Supabase-first ticket reads
from typing import Optional

# Initialize logger
logger = logging.getLogger(__name__)

# =============================================================================
# DIKW SYNTHESIZER AGENT NOTE (Checkpoint 2.5)
# =============================================================================
# DIKW endpoints have been moved to api/dikw.py router (Refactor Phase 2).
# The dikw_router is included via include_router() at the bottom of this file.
# Agent adapters are imported lazily in that router for backward compatibility.
# =============================================================================

# OpenAPI/Swagger configuration (Phase 3.3)
API_VERSION = "1.0.0"
API_DESCRIPTION = """
# SignalFlow API

A knowledge work management system built around signal extraction from meetings,
hierarchical knowledge organization, and AI-assisted workflow management.

## API Versions

- **v1** (`/api/v1/*`): RESTful API with proper pagination, HTTP status codes, and Pydantic models
- **mobile** (`/api/mobile/*`): Offline-first sync endpoints for mobile apps
- **legacy** (other routes): Original HTML-returning endpoints for web app

## Core Features

### 🎯 Signal Extraction
Extract decisions, action items, blockers, risks, and ideas from meetings.

### 📚 Knowledge Organization  
DIKW pyramid implementation with hierarchical knowledge synthesis.

### 🏃 Sprint Management
Sprint cycles, ticket management, and AI-powered standup analysis.

### 📱 Multi-Device Sync
Bidirectional sync with conflict resolution for mobile apps.

## Authentication
All endpoints require authentication. Set the `STATIC_TOKEN` environment variable.
"""

app = FastAPI(
    title="SignalFlow - Memory & Signal Intelligence",
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "v1", "description": "API v1 endpoints with proper REST semantics"},
        {"name": "meetings", "description": "Meeting CRUD operations"},
        {"name": "documents", "description": "Document CRUD operations"},
        {"name": "signals", "description": "Signal extraction and management"},
        {"name": "tickets", "description": "Ticket and sprint management"},
        {"name": "mobile", "description": "Mobile app sync endpoints"},
        {"name": "sync", "description": "Device sync operations"},
        {"name": "device", "description": "Device registration and management"},
    ]
)

# Health check endpoint (required for Railway)
@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint for Railway and other platforms."""
    return {"status": "healthy", "version": API_VERSION}

# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Serve static files (CSS, JS)
STATIC_DIR = "src/app/static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# NOTE: Uploads folder removed - attachments are stored in Supabase Storage
# See services/storage_supabase.py for file storage operations

templates = Jinja2Templates(directory="src/app/templates")

# Expose environment variables to Jinja2 templates
templates.env.globals['env'] = os.environ


# NOTE: Neo4j removed - using Supabase knowledge graph instead (Phase 5.10)


@app.on_event("startup")
def startup():
    """Initialize the application on startup."""
    print("ℹ️ Starting application with Supabase-only mode")
    
    # Initialize background job scheduler (production only)
    try:
        from .services.scheduler import init_scheduler
        scheduler = init_scheduler()
        if scheduler:
            print("✅ Background job scheduler initialized")
    except Exception as e:
        print(f"⚠️ Scheduler init failed (non-fatal): {e}")


# -------------------------
# Authentication Routes
# -------------------------

@app.get("/login")
def login_page(request: Request, error: str = None, next: str = "/"):
    """Show login page."""
    return HTMLResponse(get_login_page(error=error, next_url=next))


@app.post("/auth/login")
async def do_login(request: Request, password: str = Form(...), next: str = Form("/")):
    """Process login."""
    expected_hash = hash_password(get_auth_password())
    provided_hash = hash_password(password)
    
    if provided_hash != expected_hash:
        return HTMLResponse(get_login_page(error="Invalid access code", next_url=next))
    
    # Create session
    user_agent = request.headers.get("user-agent", "")
    token = create_session(user_agent)
    
    response = RedirectResponse(url=next, status_code=302)
    response.set_cookie(
        key="signalflow_session",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 1 week
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout(request: Request):
    """Logout and destroy session."""
    token = request.cookies.get("signalflow_session")
    if token:
        destroy_session(token)
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("signalflow_session")
    return response


# -------------------------
# Root + Dashboard
# -------------------------

def get_sprint_info():
    """Get current sprint day and info, with working days calculation."""
    # Try Supabase first
    try:
        from .infrastructure.supabase_client import get_supabase_client
        client = get_supabase_client()
        if client:
            result = client.table('sprint_settings').select('*').limit(1).execute()
            if result.data:
                row_dict = result.data[0]
                start_str = row_dict.get("sprint_start_date")
                if start_str:
                    # Handle both date formats
                    if 'T' in str(start_str):
                        start = datetime.fromisoformat(str(start_str).replace('Z', '+00:00')).replace(tzinfo=None)
                    else:
                        start = datetime.strptime(str(start_str), "%Y-%m-%d")
                    
                    today = datetime.now()
                    delta = (today - start).days + 1
                    sprint_length = row_dict.get("sprint_length_days", 14) or 14
                    
                    if delta < 1:
                        day = 0
                    elif delta > sprint_length:
                        day = sprint_length
                    else:
                        day = delta
                    
                    # Calculate total working days in sprint
                    total_working_days = 0
                    for i in range(sprint_length):
                        check_date = start + timedelta(days=i)
                        if check_date.weekday() < 5:  # Mon-Fri
                            total_working_days += 1
                    
                    # Calculate working days elapsed
                    working_days_elapsed = 0
                    for i in range(min(day, sprint_length)):
                        check_date = start + timedelta(days=i)
                        if check_date.weekday() < 5:  # Mon-Fri
                            working_days_elapsed += 1
                    
                    working_days_remaining = max(0, total_working_days - working_days_elapsed)
                    remaining_total = max(0, sprint_length - day)
                    progress = int((working_days_elapsed / total_working_days) * 100) if total_working_days > 0 else 0
                    
                    return {
                        "day": day,
                        "length": sprint_length,
                        "name": row_dict.get("sprint_name"),
                        "remaining": remaining_total,
                        "working_days_remaining": working_days_remaining,
                        "working_days_elapsed": working_days_elapsed,
                        "total_working_days": total_working_days,
                        "progress": progress,
                    }
    except Exception as e:
        logger.warning(f"Supabase sprint_settings read failed: {e}")
    
    # Return default if no sprint settings found
    return None

@app.get("/")
def dashboard(request: Request):
    """Dashboard home page with today's summary."""
    # Get time of day greeting
    hour = datetime.now().hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"
    
    today_formatted = datetime.now().strftime("%A, %B %d, %Y")
    
    # Get sprint info
    sprint = get_sprint_info()
    
    # Generate dynamic greeting based on sprint cadence
    greeting_context = ""
    if sprint:
        days_remaining = sprint.get("working_days_remaining", 0)
        progress = sprint.get("progress", 0)
        day_of_week = datetime.now().weekday()
        
        if day_of_week == 0:  # Monday
            greeting_context = "fresh start to the week"
        elif day_of_week == 4:  # Friday
            greeting_context = "let's close out strong"
        elif days_remaining <= 2 and days_remaining > 0:
            greeting_context = "sprint finish line ahead"
        elif progress < 15:
            greeting_context = "new sprint energy"
        elif progress >= 80:
            greeting_context = "home stretch"
        elif progress >= 50:
            greeting_context = "past the halfway point"
        else:
            greeting_context = "ready to dive in"
    else:
        greeting_context = "ready to dive in"
    
    # Get stats - from Supabase first
    meeting_stats = meetings_supabase.get_dashboard_stats()
    meetings_count = meeting_stats["meetings_count"]
    meetings_with_signals = meeting_stats["meetings_with_signals"]
    signals_count = meeting_stats["signals_count"]
    
    # Get docs and tickets count from Supabase
    docs_count = documents_supabase.get_documents_count()
    tickets_count = tickets_supabase.get_tickets_count(statuses=["todo", "in_progress", "in_review"])
    
    # Conversations count from Supabase
    conversations_count = 0
    try:
        conv_result = supabase.table("conversations").select("id", count="exact").execute()
        conversations_count = conv_result.count or 0
    except:
        pass
    
    # Get feedback for signals from Supabase
    feedback_map = {}
    try:
        feedback_rows = supabase.table("signal_feedback").select("meeting_id, signal_type, signal_text, feedback").execute().data
        for f in feedback_rows:
            key = f"{f['meeting_id']}:{f['signal_type']}:{f['signal_text']}"
            feedback_map[key] = f['feedback']
    except:
        pass

    # Get status for recent signals from Supabase
    status_map = {}
    try:
        meeting_ids = [m["id"] for m in meetings_with_signals[:10]]
        if meeting_ids:
            status_rows = supabase.table("signal_status").select("meeting_id, signal_type, signal_text, status").in_("meeting_id", meeting_ids).execute().data
            for s in status_rows:
                key = f"{s['meeting_id']}:{s['signal_type']}:{s['signal_text']}"
                status_map[key] = s["status"]
    except:
        pass
    
    # Build recent_signals from Supabase data
    recent_signals = []
    for m in meetings_with_signals[:10]:
        try:
            signals = m.get("signals", {})
            for stype, icon_type in [("blockers", "blocker"), ("action_items", "action"), ("decisions", "decision"), ("ideas", "idea"), ("risks", "risk")]:
                items = signals.get(stype, [])
                if isinstance(items, list):
                    for item in items[:2]:
                        if item and len(recent_signals) < 8:
                            feedback_key = f"{m['id']}:{icon_type}:{item}"
                            status_key = f"{m['id']}:{icon_type}:{item}"
                            recent_signals.append({
                                "text": item,
                                "type": icon_type,
                                "source": m["meeting_name"],
                                "meeting_id": m["id"],
                                "feedback": feedback_map.get(feedback_key),
                                "status": status_map.get(status_key)
                            })
        except:
            pass
    
    # Build highlights section from Supabase data
    highlights = []
    for m in meetings_with_signals[:5]:
        try:
            signals = m.get("signals", {})
            # Add blockers to highlights (highest priority)
            for blocker in signals.get("blockers", [])[:2]:
                if blocker:
                    highlights.append({
                        "type": "blocker",
                        "label": "🚧 Blocker",
                        "text": blocker,
                        "source": m["meeting_name"],
                        "meeting_id": m["id"],
                    })
            # Add action items
            for action in signals.get("action_items", [])[:2]:
                if action:
                    highlights.append({
                        "type": "action",
                        "label": "📋 Action Item",
                        "text": action,
                        "source": m["meeting_name"],
                        "meeting_id": m["id"],
                    })
            # Add decisions
            for decision in signals.get("decisions", [])[:1]:
                if decision:
                    highlights.append({
                        "type": "decision",
                        "label": "✅ Decision",
                        "text": decision,
                        "source": m["meeting_name"],
                        "meeting_id": m["id"],
                    })
            # Add risks
            for risk in signals.get("risks", [])[:1]:
                if risk:
                    highlights.append({
                        "type": "risk",
                        "label": "⚠️ Risk",
                        "text": risk,
                        "source": m["meeting_name"],
                        "meeting_id": m["id"],
                    })
        except:
            pass
    
    # Limit highlights (prioritize blockers first)
    blockers_first = [h for h in highlights if h["type"] == "blocker"]
    actions = [h for h in highlights if h["type"] == "action"]
    others = [h for h in highlights if h["type"] not in ("blocker", "action")]
    highlights = (blockers_first + actions + others)[:6]
    
    # Recent items (meetings and docs from Supabase)
    recent_items = []
    recent_mtgs = meetings_supabase.get_recent_meetings(limit=5)
    for m in recent_mtgs:
        recent_items.append({
            "type": "meeting",
            "title": m["meeting_name"],
            "date": m["meeting_date"],
            "url": f"/meetings/{m['id']}"
        })
    
    # Get recent docs from Supabase
    recent_docs = documents_supabase.get_recent_documents(limit=5)
    for d in recent_docs:
        recent_items.append({
            "type": "doc",
            "title": d.get("source", "Untitled"),
            "date": d.get("document_date"),
            "url": f"/documents/{d['id']}"
        })
    
    # Sort by date and take top 5
    recent_items.sort(key=lambda x: x["date"] or "", reverse=True)
    recent_items = recent_items[:5]
    
    # Get active tickets from Supabase
    active_tickets = tickets_supabase.get_active_tickets(limit=5)

    execution_ticket = None
    execution_tasks = []
    for ticket in active_tickets:
        raw_tasks = ticket["task_decomposition"] if "task_decomposition" in ticket.keys() else None
        if raw_tasks:
            try:
                parsed = json.loads(raw_tasks) if isinstance(raw_tasks, str) else raw_tasks
            except Exception:
                parsed = []
            if isinstance(parsed, list) and parsed:
                normalized = []
                for idx, item in enumerate(parsed):
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("text") or item.get("task") or item.get("name") or "Task"
                        description = item.get("description") or item.get("details") or item.get("estimate")
                        status = item.get("status", "pending")
                    else:
                        title = str(item)
                        description = None
                        status = "pending"
                    normalized.append({"index": idx, "title": title, "description": description, "status": status})
                execution_ticket = {
                    "id": ticket["id"],
                    "ticket_id": ticket.get("ticket_id"),
                    "title": ticket.get("title"),
                }
                execution_tasks = normalized
                break
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "time_of_day": time_of_day,
            "greeting_context": greeting_context,
            "today_formatted": today_formatted,
            "sprint": sprint,
            "stats": {
                "meetings": meetings_count,
                "documents": docs_count,
                "signals": signals_count,
                "conversations": conversations_count,
                "tickets": tickets_count,
            },
            "recent_signals": recent_signals[:5],
            "recent_items": recent_items,
            "active_tickets": active_tickets,
            "execution_ticket": execution_ticket,
            "execution_tasks": execution_tasks,
            "highlights": highlights,
            "layout": "wide",  # Default to wide for 34" monitor
        },
    )


@app.get("/profile")
def profile_page(request: Request):
    """Profile router page with links to settings, career, and account."""
    user_name = os.getenv("USER_NAME", "Rowan")
    return templates.TemplateResponse("profile.html", {"request": request, "user_name": user_name})


@app.get("/settings")
def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/career")
def career_page(request: Request):
    """Career development page."""
    return templates.TemplateResponse("career.html", {"request": request})


@app.get("/notifications")
def notifications_page(request: Request):
    """Notifications inbox page."""
    return templates.TemplateResponse("notifications.html", {"request": request})


@app.get("/account")
def account_page(request: Request):
    """Account page."""
    user_name = os.getenv("USER_NAME", "Rowan")
    return templates.TemplateResponse("account.html", {"request": request, "user_name": user_name})


@app.get("/dikw")
def dikw_page(request: Request):
    """DIKW Pyramid page for knowledge management."""
    return templates.TemplateResponse("dikw.html", {"request": request})


@app.get("/knowledge-graph")
def knowledge_graph_page(request: Request):
    """Knowledge Synthesis page - AI-generated synthesis from mindmaps."""
    return templates.TemplateResponse("knowledge_synthesis.html", {"request": request})


@app.post("/api/signals/feedback")
async def signal_feedback(request: Request):
    """Store thumbs up/down feedback for signals."""
    data = await request.json()
    meeting_id = data.get("meeting_id")
    signal_type = data.get("signal_type")
    signal_text = data.get("signal_text")
    feedback = data.get("feedback")  # 'up', 'down', or None to remove
    
    if feedback is None:
        # Remove feedback
        supabase.table("signal_feedback").delete().eq("meeting_id", meeting_id).eq("signal_type", signal_type).eq("signal_text", signal_text).execute()
    else:
        # Upsert feedback
        supabase.table("signal_feedback").upsert({
            "meeting_id": meeting_id,
            "signal_type": signal_type,
            "signal_text": signal_text,
            "feedback": feedback
        }, on_conflict="meeting_id,signal_type,signal_text").execute()
    
    return JSONResponse({"status": "ok"})


@app.post("/api/dashboard/quick-ask")
async def dashboard_quick_ask(request: Request):
    """
    Handle quick AI questions from dashboard.
    
    Delegates to ArjunaAgent.quick_ask() for centralized AI handling.
    Returns run_id for user feedback.
    """
    from .agents.arjuna import quick_ask
    
    data = await request.json()
    topic = data.get("topic")
    query = data.get("query")
    
    try:
        result = await quick_ask(topic=topic, query=query)
        
        if result.get("success"):
            return JSONResponse({
                "response": result.get("response", ""),
                "run_id": result.get("run_id")  # From agent.last_run_id
            })
        else:
            return JSONResponse({"error": result.get("response", "AI Error")}, status_code=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"AI Error: {str(e)}"}, status_code=500)


@app.get("/api/dashboard/highlights")
async def get_highlights(request: Request):
    """Get smart coaching highlights based on app state and user activity."""
    import hashlib
    from datetime import datetime, timedelta
    
    # Get dismissed IDs from query param (passed from frontend localStorage)
    dismissed_ids = request.query_params.get('dismissed', '').split(',')
    dismissed_ids = [d.strip() for d in dismissed_ids if d.strip()]
    
    highlights = []
    
    # 1. Check for blocked tickets (HIGH PRIORITY) - from Supabase
    blocked_tickets = tickets_supabase.get_blocked_tickets(limit=3)
    for t in blocked_tickets:
        highlight_id = f"blocked-{t.get('ticket_id')}"
        if highlight_id not in dismissed_ids:
            highlights.append({
                "id": highlight_id,
                "type": "blocker",
                "label": "🚧 Blocked Ticket",
                "text": f"{t.get('ticket_id')}: {t.get('title')}",
                "action": "Unblock this ticket to keep making progress",
                "link": f"/tickets?focus={t.get('ticket_id')}",
                "link_text": "View Ticket"
            })
    
    # 2. Check for stale in-progress tickets (> 3 days old) - from Supabase
    stale_tickets = tickets_supabase.get_stale_in_progress_tickets(days=3, limit=2)
    for t in stale_tickets:
        highlight_id = f"stale-{t.get('ticket_id')}"
        if highlight_id not in dismissed_ids:
            highlights.append({
                "id": highlight_id,
                "type": "action",
                "label": "⏰ Stale Work",
                "text": f"{t.get('ticket_id')}: {t.get('title')}",
                "action": "This has been in progress for a while. Complete or update it?",
                "link": f"/tickets?focus={t.get('ticket_id')}",
                "link_text": "Update Status"
            })
    
    # 3. Check sprint progress from Supabase
    try:
        sprint_result = supabase.table("sprint_settings").select("*").eq("id", 1).execute()
        sprint = sprint_result.data[0] if sprint_result.data else None
        if sprint and sprint.get('sprint_start_date'):
            start = datetime.strptime(sprint['sprint_start_date'], '%Y-%m-%d')
            length = sprint.get('sprint_length_days') or 14
            end = start + timedelta(days=length)
            now = datetime.now()
            progress = min(100, max(0, int((now - start).days / length * 100)))
            days_left = (end - now).days
            
            # Sprint ending soon
            if 0 < days_left <= 3 and f"sprint-ending" not in dismissed_ids:
                todo_count = tickets_supabase.get_tickets_count(statuses=["todo"])
                if todo_count > 0:
                    highlights.append({
                        "id": "sprint-ending",
                        "type": "risk",
                        "label": "⏳ Sprint Ending",
                        "text": f"{days_left} day{'s' if days_left != 1 else ''} left with {todo_count} todo items",
                        "action": "Review remaining work and prioritize",
                        "link": "/tickets",
                        "link_text": "View Tickets"
                    })
            
            # Sprint just started - set it up
            if progress < 10 and f"sprint-setup" not in dismissed_ids:
                ticket_count = tickets_supabase.get_tickets_count()
                if ticket_count == 0:
                    highlights.append({
                        "id": "sprint-setup",
                        "type": "action",
                        "label": "🚀 New Sprint",
                        "text": "Your sprint has started but no tickets yet",
                        "action": "Create tickets to track your work this sprint",
                        "link": "/tickets",
                        "link_text": "Add Tickets"
                    })
    except:
        pass
    
    # 4. Check for unreviewed signals from Supabase
    try:
        unreviewed_result = supabase.table("signal_status").select("id", count="exact").or_("status.eq.pending,status.is.null").execute()
        unreviewed_count = unreviewed_result.count or 0
        if unreviewed_count > 5 and "review-signals" not in dismissed_ids:
            highlights.append({
                "id": "review-signals",
                "type": "action",
                "label": "📥 Unreviewed Signals",
                "text": f"{unreviewed_count} signals waiting for your review",
                "action": "Validate signals to build your knowledge base",
                "link": "/signals",
                "link_text": "Review Signals"
            })
    except:
        pass
    
    # 5. Check workflow mode progress
    # (suggest moving to next mode if current is complete)
    
        # 6. Recent meeting with unprocessed signals (from Supabase)
        recent_meetings_for_highlights = meetings_supabase.get_meetings_with_signals(limit=1)
        if recent_meetings_for_highlights:
            recent_meeting = recent_meetings_for_highlights[0]
            try:
                signals = recent_meeting.get('signals', {})
                blockers = signals.get('blockers', [])
                actions = signals.get('action_items', [])
                
                # Highlight blockers from recent meeting
                for i, blocker in enumerate(blockers[:2]):
                    if blocker:
                        highlight_id = f"mtg-blocker-{recent_meeting['id']}-{i}"
                        if highlight_id not in dismissed_ids:
                            highlights.append({
                                "id": highlight_id,
                                "type": "blocker",
                                "label": "🚧 Meeting Blocker",
                                "text": blocker[:100] + ('...' if len(blocker) > 100 else ''),
                                "action": f"From: {recent_meeting['meeting_name']}",
                                "link": f"/meetings/{recent_meeting['id']}",
                                "link_text": "View Meeting"
                            })
                
                # Highlight action items from recent meeting
                for i, action in enumerate(actions[:2]):
                    if action:
                        highlight_id = f"mtg-action-{recent_meeting['id']}-{i}"
                        if highlight_id not in dismissed_ids:
                            highlights.append({
                                "id": highlight_id,
                                "type": "action",
                                "label": "📋 Action Item",
                                "text": action[:100] + ('...' if len(action) > 100 else ''),
                                "action": f"From: {recent_meeting['meeting_name']}",
                                "link": f"/meetings/{recent_meeting['id']}",
                                "link_text": "View Meeting"
                            })
            except:
                pass
        
        # 7. Accountability items (waiting for others)
        waiting = conn.execute(
            """SELECT id, description, responsible_party FROM accountability_items
               WHERE status = 'waiting'
               ORDER BY created_at DESC LIMIT 2"""
        ).fetchall()
        for w in waiting:
            highlight_id = f"waiting-{w['id']}"
            if highlight_id not in dismissed_ids:
                highlights.append({
                    "id": highlight_id,
                    "type": "waiting",
                    "label": "⏳ Waiting On",
                    "text": f"{w['responsible_party']}: {w['description'][:80]}",
                    "action": "Follow up if this is blocking you",
                    "link": "/accountability",
                    "link_text": "Waiting-For List"
                })
        
        # 8. Check for empty DIKW (encourage knowledge building)
        dikw_count = conn.execute("SELECT COUNT(*) as c FROM dikw_items").fetchone()
        if dikw_count and dikw_count['c'] == 0 and "dikw-empty" not in dismissed_ids:
            highlights.append({
                "id": "dikw-empty",
                "type": "idea",
                "label": "💡 Knowledge Base",
                "text": "Start building your knowledge pyramid",
                "action": "Promote signals to DIKW to capture learnings",
                "link": "/dikw",
                "link_text": "View DIKW"
            })
        
    # 9. No recent meetings (encourage logging) - check Supabase
    recent_meetings_check = meetings_supabase.get_meetings_with_signals_in_range(days=7)
    if len(recent_meetings_check) == 0 and "log-meeting" not in dismissed_ids:
        highlights.append({
            "id": "log-meeting",
            "type": "idea",
            "label": "📅 Log a Meeting",
            "text": "No meetings logged in the past week",
            "action": "Capture decisions and actions from recent discussions",
            "link": "/meetings/new",
            "link_text": "Add Meeting"
        })
    
    # ===== ENHANCED RECOMMENDATIONS FROM ENGINE (Technical Debt) =====
    # Add embedding-based recommendations for DIKW, mentions, grooming, etc.
    try:
        from .services.coach_recommendations import get_coach_recommendations
        engine_recs = get_coach_recommendations(
            dismissed_ids=dismissed_ids,
            user_name="Rowan"  # TODO: Get from auth context
        )
        # Add engine recommendations that aren't duplicates
        existing_ids = {h['id'] for h in highlights}
        for rec in engine_recs:
            if rec['id'] not in existing_ids:
                highlights.append(rec)
    except Exception as e:
        # Silent fail - don't break highlights if engine has issues
        import logging
        logging.getLogger(__name__).debug(f"Coach engine error: {e}")
    
    # Prioritize: blockers > mentions > risks > actions > waiting > dikw > grooming > ideas
    priority = {
        'blocker': 0, 
        'mention': 1,
        'risk': 2, 
        'action': 3, 
        'waiting': 4, 
        'dikw': 5,
        'grooming': 6,
        'transcript': 7,
        'idea': 8, 
        'decision': 9
    }
    highlights.sort(key=lambda h: priority.get(h['type'], 99))
    
    # Return top 8 items (increased from 6 for more recommendations)
    return JSONResponse({"highlights": highlights[:8]})


@app.post("/api/dashboard/highlight-context")
async def get_highlight_context(request: Request):
    """Get drill-down context for a highlight item."""
    data = await request.json()
    source = data.get("source", "")
    text = data.get("text", "")
    meeting_id = data.get("meeting_id")
    
    # Find the meeting from Supabase
    meeting = None
    if meeting_id:
        meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    
    # If not found by id, search by name (less common case)
    if not meeting and source:
        all_meetings = meetings_supabase.get_all_meetings(limit=50)
        for m in all_meetings:
            if m.get("meeting_name") == source:
                meeting = m
                break
    
    if not meeting:
        return JSONResponse({
            "summary": "Meeting not found.",
            "context": None,
            "transcript": None,
            "meeting_link": None
        })
    
    # Build progressive context levels
    summary = None
    context = None
    transcript = None
    
    # Level 1: AI-generated summary of the issue
    if meeting["synthesized_notes"]:
        # Find relevant section in notes
        notes = meeting["synthesized_notes"]
        # Try to find the specific text in notes
        text_lower = text.lower()
        lines = notes.split('\n')
        relevant_lines = []
        for i, line in enumerate(lines):
            if text_lower[:30] in line.lower() or any(word in line.lower() for word in text_lower.split()[:3]):
                # Get surrounding context
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                relevant_lines = lines[start:end]
                break
        
        if relevant_lines:
            summary = '\n'.join(relevant_lines)
        else:
            summary = notes[:500] + ('...' if len(notes) > 500 else '')
    
    # Level 2: Full context from signals
    if meeting["signals_json"]:
        try:
            signals = json.loads(meeting["signals_json"])
            context_parts = []
            for stype in ["blockers", "decisions", "action_items", "risks", "ideas"]:
                items = signals.get(stype, [])
                if items:
                    context_parts.append(f"**{stype.replace('_', ' ').title()}:**\n" + '\n'.join(f"• {item}" for item in items))
            context = '\n\n'.join(context_parts) if context_parts else None
        except:
            pass
    
    # Level 3: Transcript excerpt
    if meeting["raw_text"]:
        raw = meeting["raw_text"]
        # Try to find the text in the transcript
        text_lower = text.lower()
        if text_lower[:30] in raw.lower():
            # Find position and get surrounding context
            idx = raw.lower().find(text_lower[:30])
            start = max(0, idx - 200)
            end = min(len(raw), idx + 500)
            transcript = ('...' if start > 0 else '') + raw[start:end] + ('...' if end < len(raw) else '')
        else:
            # Just show first 500 chars of transcript
            transcript = raw[:500] + ('...' if len(raw) > 500 else '')
    
    return JSONResponse({
        "summary": summary,
        "context": context,
        "transcript": transcript,
        "meeting_link": f"/meetings/{meeting['id']}" if meeting else None
    })


# -------------------------
# Signal Status API
# -------------------------

@app.post("/api/signals/status")
async def update_signal_status(request: Request):
    """Update signal status (approve/reject/archive/complete)."""
    data = await request.json()
    meeting_id = data.get("meeting_id")
    signal_type = data.get("signal_type")
    signal_text = data.get("signal_text")
    status = data.get("status")  # pending, approved, rejected, archived, completed
    notes = data.get("notes", "")
    
    if not all([meeting_id, signal_type, signal_text, status]):
        return JSONResponse({"error": "Missing required fields"}, status_code=400)
    
    supabase.table("signal_status").upsert({
        "meeting_id": meeting_id,
        "signal_type": signal_type,
        "signal_text": signal_text,
        "status": status,
        "notes": notes
    }, on_conflict="meeting_id,signal_type,signal_text").execute()
    
    return JSONResponse({"status": "ok", "new_status": status})


@app.post("/api/signals/convert-to-ticket")
async def convert_signal_to_ticket(request: Request):
    """Convert a signal item into a ticket/action item."""
    data = await request.json()
    meeting_id = data.get("meeting_id")
    signal_type = data.get("signal_type")
    signal_text = data.get("signal_text")
    
    if not all([meeting_id, signal_type, signal_text]):
        return JSONResponse({"error": "Missing required fields"}, status_code=400)
    
    # Get meeting name from Supabase for context
    meeting_name = meetings_supabase.get_meeting_name(meeting_id) or "Unknown Meeting"
    
    # Generate ticket ID from Supabase
    next_num = tickets_supabase.get_next_ticket_number()
    ticket_id = f"SIG-{next_num}"
    
    # Determine priority based on signal type
    priority_map = {"blocker": "high", "risk": "high", "action_item": "medium", "decision": "low", "idea": "low"}
    priority = priority_map.get(signal_type, "medium")
    
    # Create ticket in Supabase
    ticket_result = supabase.table("tickets").insert({
        "ticket_id": ticket_id,
        "title": signal_text[:100],
        "description": f"Signal from: {meeting_name}\n\nOriginal Signal ({signal_type}):\n{signal_text}",
        "status": "backlog",
        "priority": priority,
        "ai_summary": f"Converted from {signal_type} signal: {signal_text[:150]}..."
    }).execute()
    
    ticket_db_id = ticket_result.data[0]["id"] if ticket_result.data else None
    
    # Update signal status in Supabase
    supabase.table("signal_status").upsert({
        "meeting_id": meeting_id,
        "signal_type": signal_type,
        "signal_text": signal_text,
        "status": "completed",
        "converted_to": "ticket",
        "converted_ref_id": ticket_db_id
    }, on_conflict="meeting_id,signal_type,signal_text").execute()
    
    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "ticket_db_id": ticket_db_id})


# -------------------------
# AI Transcript Summarization API
# -------------------------

@app.post("/api/ai/draft-summary")
async def draft_summary_from_transcript_api(request: Request):
    """
    Generate a structured meeting summary from a transcript using GPT-4o.
    
    This endpoint does not require a meeting ID - useful for Load Bundle flow
    where the meeting doesn't exist yet.
    
    Model: gpt-4o (configured in model_routing.yaml task_type: transcript_summarization)
    
    Body:
        - transcript: The meeting transcript text (required)
        - meeting_name: Name of the meeting (optional, default: "Meeting")
        - focus_areas: List of areas to emphasize (optional)
    
    Returns:
        - status: "draft_generated" or "error"
        - draft_summary: Structured summary in template format
        - model_used: "gpt-4o"
    """
    from .mcp.tools import draft_summary_from_transcript
    
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    transcript = body.get("transcript", "")
    meeting_name = body.get("meeting_name", "Meeting")
    focus_areas = body.get("focus_areas", [])
    
    if not transcript or len(transcript) < 100:
        return JSONResponse({
            "status": "error",
            "error": "Transcript too short. Provide at least 100 characters."
        }, status_code=400)
    
    # Call the MCP tool which uses GPT-4o
    result = draft_summary_from_transcript({
        "transcript": transcript,
        "meeting_name": meeting_name,
        "focus_areas": focus_areas
    })
    
    if result.get("status") == "error" or result.get("error"):
        return JSONResponse({
            "status": "error",
            "error": result.get("error", "Unknown error during summarization")
        }, status_code=500)
    
    return JSONResponse({
        "status": "draft_generated",
        "draft_summary": result.get("draft_summary"),
        "model_used": result.get("model_used", "gpt-4o"),
        "meeting_name": meeting_name,
        "instructions": "Review and edit this summary, then save with your meeting."
    })


# -------------------------
# AI Memory API
# -------------------------

@app.post("/api/ai-memory/save")
async def save_ai_memory(request: Request):
    """Save an AI response to memory (approve)."""
    data = await request.json()
    source_type = data.get("source_type", "quick_ask")
    source_query = data.get("query", "")
    content = data.get("content", "")
    tags = data.get("tags", "")
    importance = data.get("importance", 5)
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    result = supabase.table("ai_memory").insert({
        "source_type": source_type,
        "source_query": source_query,
        "content": content,
        "status": "approved",
        "tags": tags,
        "importance": importance
    }).execute()
    
    memory_id = result.data[0]["id"] if result.data else None
    
    return JSONResponse({"status": "ok", "memory_id": memory_id})


@app.post("/api/ai-memory/reject")
async def reject_ai_response(request: Request):
    """Mark an AI response as rejected (don't save to memory)."""
    data = await request.json()
    source_query = data.get("query", "")
    content = data.get("content", "")
    
    # We can optionally log rejected responses for ML training
    supabase.table("ai_memory").insert({
        "source_type": "quick_ask",
        "source_query": source_query,
        "content": content[:500],  # Store truncated for training feedback
        "status": "rejected",
        "importance": 0
    }).execute()
    
    return JSONResponse({"status": "ok"})


@app.post("/api/ai-memory/to-action")
async def convert_ai_to_action(request: Request):
    """Convert an AI response into a ticket/action item."""
    data = await request.json()
    content = data.get("content", "")
    query = data.get("query", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    # Generate ticket ID from Supabase
    next_num = tickets_supabase.get_next_ticket_number()
    ticket_id = f"AI-{next_num}"
    
    # Extract first line as title
    title = content.split('\n')[0][:100].strip('*#- ')
    if not title:
        title = query[:100] if query else "AI Generated Action Item"
    
    # Create ticket in Supabase
    result = supabase.table("tickets").insert({
        "ticket_id": ticket_id,
        "title": title,
        "description": f"From AI Query: {query}\n\nAI Response:\n{content}",
        "status": "backlog",
        "priority": "medium",
        "ai_summary": f"AI insight: {content[:150]}..."
    }).execute()
    
    ticket_db_id = result.data[0]["id"] if result.data else None
    
    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "ticket_db_id": ticket_db_id})


# ============================================
# Reports Page (HTML template only - API routes in api/reports.py)
# ============================================

@app.get("/reports")
async def reports_page(request: Request):
    """Render the sprint reports page."""
    return templates.TemplateResponse("reports.html", {"request": request})


@app.post("/api/mode-timer/calculate-stats")
async def calculate_mode_statistics():
    """Calculate and store mode statistics for analytics."""
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    
    # Calculate daily and weekly stats for each mode
    for mode in ['grooming', 'planning', 'standup', 'implementation']:
        # Get daily sessions from Supabase
        daily_result = supabase.table("mode_sessions").select("duration_seconds").eq("mode", mode).eq("date", today).not_.is_("duration_seconds", "null").execute()
        
        if daily_result.data:
            daily_total = sum(s["duration_seconds"] for s in daily_result.data)
            daily_count = len(daily_result.data)
            daily_avg = int(daily_total / daily_count) if daily_count > 0 else 0
            
            supabase.table("mode_statistics").upsert({
                "mode": mode,
                "stat_type": "daily",
                "period": today,
                "total_seconds": daily_total,
                "session_count": daily_count,
                "avg_session_seconds": daily_avg
            }, on_conflict="mode,stat_type,period").execute()
        
        # Get weekly sessions from Supabase
        weekly_result = supabase.table("mode_sessions").select("duration_seconds").eq("mode", mode).gte("date", week_start).not_.is_("duration_seconds", "null").execute()
        
        if weekly_result.data:
            weekly_total = sum(s["duration_seconds"] for s in weekly_result.data)
            weekly_count = len(weekly_result.data)
            weekly_avg = int(weekly_total / weekly_count) if weekly_count > 0 else 0
            
            supabase.table("mode_statistics").upsert({
                "mode": mode,
                "stat_type": "weekly",
                "period": week_start,
                "total_seconds": weekly_total,
                "session_count": weekly_count,
                "avg_session_seconds": weekly_avg
            }, on_conflict="mode,stat_type,period").execute()
    
    return JSONResponse({"status": "ok", "calculated_at": datetime.now().isoformat()})


# ============================================
# User Status API Endpoints (AI-Interpreted)
# ============================================

@app.post("/api/user-status/update")
async def update_user_status(request: Request):
    """
    AI-interpret user status and auto-start timer.
    
    Migration Note (P1.8): Uses ArjunaAgent adapter for status interpretation.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.arjuna import interpret_user_status_adapter
    
    data = await request.json()
    status_text = data.get("status", "").strip()
    
    if not status_text:
        return JSONResponse({"error": "Status text required"}, status_code=400)
    
    # Use ArjunaAgent adapter for AI interpretation
    interpreted = await interpret_user_status_adapter(status_text)
    mode = interpreted.get("mode", "implementation")
    activity = interpreted.get("activity", status_text)
    context_str = interpreted.get("context", "")
    
    # Save status to Supabase
    # Mark all previous statuses as not current
    supabase.table("user_status").update({"is_current": False}).eq("is_current", True).execute()
    
    # Insert new status
    supabase.table("user_status").insert({
        "status_text": status_text,
        "interpreted_mode": mode,
        "interpreted_activity": activity,
        "interpreted_context": context_str,
        "is_current": True
    }).execute()
    
    # Auto-start timer for the interpreted mode
    # First stop any active timers
    active_sessions = supabase.table("mode_sessions").select("id, mode, started_at").is_("ended_at", "null").execute()
    
    ended_at = datetime.now().isoformat()
    for session in active_sessions.data or []:
        try:
            start_time = datetime.fromisoformat(session["started_at"].replace("Z", "+00:00").replace("+00:00", ""))
            duration = int((datetime.now() - start_time).total_seconds())
            supabase.table("mode_sessions").update({
                "ended_at": ended_at,
                "duration_seconds": duration
            }).eq("id", session["id"]).execute()
        except:
            pass
    
    # Start new timer
    today = datetime.now().strftime("%Y-%m-%d")
    started_at = datetime.now().isoformat()
    
    supabase.table("mode_sessions").insert({
        "mode": mode,
        "started_at": started_at,
        "date": today,
        "notes": activity
    }).execute()
    
    return JSONResponse({
        "status": "ok",
        "interpreted": {
            "mode": mode,
            "activity": activity,
            "context": context_str
        }
    })


@app.get("/api/user-status/current")
async def get_current_status():
    """Get current user status."""
    result = supabase.table("user_status").select("*").eq("is_current", True).order("created_at", desc=True).limit(1).execute()
    
    if not result.data:
        return JSONResponse({"status": None})
    
    status = result.data[0]
    return JSONResponse({
        "status": {
            "text": status.get("status_text"),
            "mode": status.get("interpreted_mode"),
            "activity": status.get("interpreted_activity"),
            "context": status.get("interpreted_context"),
            "created_at": status.get("created_at")
        }
    })


# NOTE: DIKW Pyramid API endpoints moved to api/dikw.py router (Refactor Phase 2)
# The dikw_router is included via include_router() at the bottom of this file.

# NOTE: Mindmap API endpoints moved to api/mindmap.py router (Refactor Phase 2)
# The mindmap_router is included via include_router() at the bottom of this file.
# Removed duplicate routes: /api/mindmap/data, /api/mindmap/data-hierarchical,
# /api/mindmap/nodes-by-level/{level}, /api/mindmap/conversations, /api/mindmap/synthesize,
# /api/mindmap/synthesis, /api/mindmap/synthesize-all, /api/mindmap/generate,
# /api/mindmap/tags, /api/mindmap/status

# NOTE: Additional DIKW endpoints (backfill-tags, compress-dedupe, history, 
# normalize-categories, auto-process) moved to api/dikw.py router (Refactor Phase 2)


@app.get("/api/signals/unprocessed")
async def get_unprocessed_signals():
    """Get signals that haven't been promoted to DIKW yet."""
    # Get meetings with signals from Supabase
    meetings = meetings_supabase.get_meetings_with_signals(limit=20)
    
    # Get already processed signals from Supabase
    processed_result = supabase.table("signal_status").select("meeting_id, signal_type, signal_text").eq("converted_to", "dikw").execute()
    processed = processed_result.data or []
    
    processed_set = set(
        (p['meeting_id'], p['signal_type'], p['signal_text']) 
        for p in processed
    )
    
    unprocessed = []
    for meeting in meetings:
        try:
            signals = meeting.get('signals', {})
            for signal_type in ['decisions', 'action_items', 'blockers', 'risks', 'ideas']:
                items = signals.get(signal_type, [])
                if isinstance(items, list):
                    for item in items:
                        text = item if isinstance(item, str) else item.get('text', str(item))
                        normalized_type = signal_type.rstrip('s')  # decisions -> decision
                        if normalized_type == 'action_item':
                            normalized_type = 'action_item'
                        
                        if (meeting['id'], normalized_type, text) not in processed_set:
                            unprocessed.append({
                                'meeting_id': meeting['id'],
                                'meeting_name': meeting['meeting_name'],
                                'signal_type': normalized_type,
                                'text': text
                            })
        except:
            pass
    
    return JSONResponse(unprocessed)


@app.get("/meetings/new")
def new_meeting(request: Request):
    return templates.TemplateResponse(
        "paste_meeting.html",
        {"request": request},
    )


@app.get("/documents/new")
def new_document(request: Request):
    return templates.TemplateResponse(
        "paste_doc.html",
        {"request": request},
    )

@app.get("/meetings/load")
def load_meeting_bundle_page(request: Request):
    return templates.TemplateResponse(
        "load_meeting_bundle.html",
        {"request": request},
    )

@app.post("/meetings/load")
async def load_meeting_bundle_ui(
    request: Request,
    background_tasks: BackgroundTasks,
    meeting_name: str = Form(...),
    meeting_date: str = Form(None),
    summary_text: str = Form(...),
    pocket_recording_id: str = Form(None),
    pocket_ai_summary: str = Form(None),
    pocket_mind_map: str = Form(None),
    mindmap_level: int = Form(0),
    pocket_action_items: str = Form(None),
    pocket_transcript: str = Form(None),
    teams_transcript: str = Form(None),
):
    """
    Load a complete meeting bundle with:
    - Structured summary (canonical format)
    - Optional Pocket AI summary (creates document for signal extraction)
    - Optional Pocket Mind Map (triggers synthesis)
    - Optional Pocket Action Items (merged into signals_json)
    - Optional transcripts (merged into searchable document)
    - Optional screenshots (attached to meeting)
    """
    tool = TOOL_REGISTRY["load_meeting_bundle"]
    
    # Merge transcripts if provided
    transcript_parts = []
    if pocket_transcript and pocket_transcript.strip():
        transcript_parts.append(f"=== Pocket Transcript ===\n{pocket_transcript.strip()}")
    if teams_transcript and teams_transcript.strip():
        transcript_parts.append(f"=== Teams Transcript ===\n{teams_transcript.strip()}")
    
    merged_transcript = "\n\n".join(transcript_parts) if transcript_parts else None

    result = tool({
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "summary_text": summary_text,
        "transcript_text": merged_transcript,
        "pocket_ai_summary": pocket_ai_summary,
        "pocket_mind_map": pocket_mind_map,
        "pocket_recording_id": pocket_recording_id,
        "format": "plain",
    })
    
    meeting_id = result.get("meeting_id")
    
    # Store Pocket action items in signals if provided
    if meeting_id and pocket_action_items and pocket_action_items.strip():
        try:
            # Parse action items from the text format back to structured data
            # Parse JSON from hidden field (contains array of action item objects)
            pocket_items = json.loads(pocket_action_items.strip())
            
            # Add source marker to each item
            for item in pocket_items:
                item["source"] = "pocket"
            
            if pocket_items:
                # Get current meeting signals from Supabase
                meeting = meetings_supabase.get_meeting_by_id(meeting_id)
                if meeting:
                    signals = meeting.get("signals", {})
                    
                    # Merge Pocket action items (preserve existing)
                    existing_items = signals.get("action_items", [])
                    signals["action_items"] = existing_items + pocket_items
                    
                    # Update in Supabase
                    meetings_supabase.update_meeting(meeting_id, {"signals": signals})
                    
                logging.getLogger(__name__).info(f"Added {len(pocket_items)} Pocket action items to meeting {meeting_id}")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to parse/store Pocket action items: {e}")
    
    # Handle screenshot uploads if meeting was created successfully
    if meeting_id:
        form = await request.form()
        screenshots = form.getlist("screenshots")
        
        for screenshot in screenshots:
            if hasattr(screenshot, 'file') and screenshot.filename:
                try:
                    import uuid
                    import os
                    
                    content = await screenshot.read()
                    mime_type = screenshot.content_type or 'image/png'
                    
                    # Try Supabase Storage first
                    supabase_url = None
                    supabase_path = None
                    local_path = None
                    
                    try:
                        from .services.storage_supabase import upload_file_to_supabase
                        supabase_url, supabase_path = await upload_file_to_supabase(
                            content=content,
                            filename=screenshot.filename,
                            meeting_id=meeting_id,
                            content_type=mime_type
                        )
                    except Exception as e:
                        logger.warning(f"Supabase upload failed, using local: {e}")
                    
                    # Fallback to local storage if Supabase fails
                    if not supabase_url:
                        ext = os.path.splitext(screenshot.filename)[1] or '.png'
                        unique_name = f"{uuid.uuid4().hex}{ext}"
                        file_path = os.path.join(UPLOAD_DIR, unique_name)
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        local_path = f"uploads/{unique_name}"
                    
                    # Record in Supabase attachments table
                    supabase.table("attachments").insert({
                        "ref_type": "meeting",
                        "ref_id": meeting_id,
                        "filename": screenshot.filename,
                        "file_path": local_path or "",
                        "mime_type": mime_type,
                        "file_size": len(content),
                        "supabase_url": supabase_url,
                        "supabase_path": supabase_path
                    }).execute()
                except Exception as e:
                    logger.warning(f"Failed to upload screenshot: {e}")
        
        # Auto-trigger synthesis if mindmap was provided
        if pocket_mind_map and pocket_mind_map.strip():
            def trigger_synthesis():
                try:
                    from .services.mindmap_synthesis import MindmapSynthesizer
                    
                    # Store the mindmap for this conversation
                    MindmapSynthesizer.store_conversation_mindmap(
                        conversation_id=f"meeting_{meeting_id}",
                        title=meeting_name,
                        mindmap_data=pocket_mind_map,
                        hierarchy_level=mindmap_level
                    )
                    
                    # Regenerate synthesis
                    MindmapSynthesizer.generate_synthesis(force=True)
                    logger.info(f"✅ Mindmap synthesis triggered for new meeting {meeting_id}")
                except Exception as e:
                    logger.error(f"Failed to trigger mindmap synthesis: {e}")
            
            background_tasks.add_task(trigger_synthesis)
            logger.info(f"Scheduled mindmap synthesis for meeting {meeting_id} at level {mindmap_level}")

    return RedirectResponse(
        url="/meetings?success=meeting_loaded",
        status_code=303,
    )


# -------------------------
# Routers
# -------------------------

app.include_router(meetings_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(query_router)
app.include_router(signals_router)
app.include_router(tickets_router)
app.include_router(test_plans_router)
app.include_router(chat_router)
app.include_router(mcp_router)
app.include_router(accountability_router)
app.include_router(settings_router)
app.include_router(assistant_router)
app.include_router(career_router)
app.include_router(v1_router)  # API v1 versioned endpoints (Phase 3.1)
app.include_router(mobile_router)  # Mobile sync endpoints (Phase 3.2)
app.include_router(admin_router)  # Admin endpoints (Phase 4.1)
app.include_router(api_search_router)  # Semantic/Hybrid search (Phase 5.2)
app.include_router(knowledge_graph_router)  # Knowledge graph links (Phase 5.10)
app.include_router(shortcuts_router)  # Arjuna shortcuts (Technical Debt)
app.include_router(dikw_router)  # DIKW pyramid (Refactor Phase 2)
app.include_router(mindmap_router)  # Mindmap visualization (Refactor Phase 2)
app.include_router(notifications_router)  # Notifications (Refactor Phase 2)
app.include_router(workflow_router)  # Workflow modes & timer (Refactor Phase 2)
app.include_router(reports_router)  # Reports & analytics (Refactor Phase 2)
app.include_router(evaluations_router)  # LangSmith evaluations (Refactor Phase 2)
app.include_router(pocket_router)  # Pocket integration (Refactor Phase 2)