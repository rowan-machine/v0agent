from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import json
import os
import re

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from .db import init_db, connect
from .meetings import router as meetings_router
from .documents import router as documents_router
from .search import router as search_router
from .query import router as query_router
from .signals import router as signals_router
from .tickets import router as tickets_router
from .test_plans import router as test_plans_router
from .chat.models import init_chat_tables
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
from .mcp.registry import TOOL_REGISTRY
from .llm import ask as ask_llm
from .auth import (
    AuthMiddleware, get_login_page, create_session, 
    destroy_session, get_auth_password, hash_password
)
from .integrations.pocket import PocketClient, extract_latest_summary, extract_transcript_text, extract_mind_map, extract_action_items, get_all_summary_versions, get_all_mind_map_versions
from typing import Optional

# =============================================================================
# DIKW SYNTHESIZER AGENT IMPORTS (Checkpoint 2.5)
# =============================================================================
# These are imported at module level for constants only.
# Agent adapters are imported lazily inside endpoint functions for:
#   1. Backward compatibility (module loads even if agent has issues)
#   2. Faster startup (defer heavy agent initialization)
#   3. Easier testing (can mock at function level)
#
# Adapter functions available via lazy import:
#   - promote_signal_to_dikw_adapter
#   - promote_dikw_item_adapter
#   - merge_dikw_items_adapter
#   - validate_dikw_item_adapter
#   - generate_dikw_tags_adapter
#   - ai_summarize_dikw_adapter
#   - ai_promote_dikw_adapter
#   - get_mindmap_data_adapter
#   - generate_dikw_tags (sync wrapper)
# =============================================================================
from .agents.dikw_synthesizer import DIKW_LEVELS as AGENT_DIKW_LEVELS

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

# Serve uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

templates = Jinja2Templates(directory="src/app/templates")

# Expose environment variables to Jinja2 templates
templates.env.globals['env'] = os.environ


# NOTE: Neo4j removed - using Supabase knowledge graph instead (Phase 5.10)


@app.on_event("startup")
def startup():
    init_db()
    init_chat_tables()
    
    # Run Phase 4.1 database migrations
    from .db_migrations import run_all_migrations
    migration_result = run_all_migrations()
    if migration_result["applied"] > 0:
        print(f"✅ Applied {migration_result['applied']} database migrations")
    
    # Sync data from Supabase in production
    try:
        from .sync_from_supabase import sync_all_from_supabase
        sync_results = sync_all_from_supabase()
        if sync_results:
            total = sum(sync_results.values())
            if total > 0:
                print(f"✅ Synced {total} items from Supabase to SQLite")
    except Exception as e:
        print(f"⚠️ Supabase sync failed (non-fatal): {e}")
    
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
    with connect() as conn:
        row = conn.execute("SELECT * FROM sprint_settings WHERE id = 1").fetchone()
    if not row:
        return None
    
    # Convert sqlite3.Row to dict for .get() access
    row_dict = dict(row)
    
    start = datetime.strptime(row_dict["sprint_start_date"], "%Y-%m-%d")
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
    
    # Calculate working days elapsed (from start to today, excluding weekends)
    working_days_elapsed = 0
    for i in range(min(day, sprint_length)):
        check_date = start + timedelta(days=i)
        if check_date.weekday() < 5:  # Mon-Fri
            working_days_elapsed += 1
    
    # Calculate working days remaining
    working_days_remaining = max(0, total_working_days - working_days_elapsed)
    
    # Calculate remaining total calendar days
    remaining_total = max(0, sprint_length - day)
    
    # Progress based on working days
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
    
    # Get stats
    with connect() as conn:
        meetings_count = conn.execute("SELECT COUNT(*) FROM meeting_summaries").fetchone()[0]
        docs_count = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        conversations_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] if table_exists(conn, 'conversations') else 0
        
        # Count total signals
        signals_count = 0
        meetings_with_signals = conn.execute(
            "SELECT signals_json FROM meeting_summaries WHERE signals_json IS NOT NULL"
        ).fetchall()
        for m in meetings_with_signals:
            try:
                signals = json.loads(m["signals_json"])
                for key in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                    items = signals.get(key, [])
                    if isinstance(items, list):
                        signals_count += len(items)
            except:
                pass
        
        # Recent signals - get meetings that actually have signal content
        recent_signals = []
        recent_meetings = conn.execute(
            """SELECT id, meeting_name, signals_json FROM meeting_summaries 
               WHERE signals_json IS NOT NULL 
               AND signals_json NOT LIKE '%"decisions": []%'
               ORDER BY COALESCE(meeting_date, created_at) DESC LIMIT 10"""
        ).fetchall()
        
        # Get feedback for signals
        feedback_map = {}
        try:
            feedback_rows = conn.execute("SELECT meeting_id, signal_type, signal_text, feedback FROM signal_feedback").fetchall()
            for f in feedback_rows:
                key = f"{f['meeting_id']}:{f['signal_type']}:{f['signal_text']}"
                feedback_map[key] = f['feedback']
        except:
            pass

        # Get status for recent signals
        status_map = {}
        try:
            meeting_ids = [m["id"] for m in recent_meetings]
            if meeting_ids:
                placeholders = ",".join(["?"] * len(meeting_ids))
                status_rows = conn.execute(
                    f"""
                    SELECT meeting_id, signal_type, signal_text, status
                    FROM signal_status
                    WHERE meeting_id IN ({placeholders})
                    """,
                    tuple(meeting_ids)
                ).fetchall()
                for s in status_rows:
                    key = f"{s['meeting_id']}:{s['signal_type']}:{s['signal_text']}"
                    status_map[key] = s["status"]
        except:
            pass
        
        for m in recent_meetings:
            try:
                signals = json.loads(m["signals_json"])
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
        
        # Build highlights section (blockers, proposals, Rowan mentions, announcements)
        highlights = []
        for m in recent_meetings[:5]:
            try:
                signals = json.loads(m["signals_json"])
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
        
        # Recent items (meetings + docs)
        recent_items = []
        recent_mtgs = conn.execute(
            "SELECT id, meeting_name, meeting_date FROM meeting_summaries ORDER BY COALESCE(meeting_date, created_at) DESC LIMIT 5"
        ).fetchall()
        for m in recent_mtgs:
            recent_items.append({
                "type": "meeting",
                "title": m["meeting_name"],
                "date": m["meeting_date"],
                "url": f"/meetings/{m['id']}"
            })
        
        recent_docs = conn.execute(
            "SELECT id, source, document_date FROM docs ORDER BY COALESCE(document_date, created_at) DESC LIMIT 5"
        ).fetchall()
        for d in recent_docs:
            recent_items.append({
                "type": "doc",
                "title": d["source"],
                "date": d["document_date"],
                "url": f"/documents/{d['id']}"
            })
        
        # Sort by date and take top 5
        recent_items.sort(key=lambda x: x["date"] or "", reverse=True)
        recent_items = recent_items[:5]
        
        # Get active tickets
        active_tickets = conn.execute(
            """SELECT * FROM tickets 
               WHERE status IN ('todo', 'in_progress', 'in_review', 'blocked')
               ORDER BY CASE status 
                   WHEN 'in_progress' THEN 1 
                   WHEN 'blocked' THEN 2
                   WHEN 'in_review' THEN 3
                   ELSE 4 END,
               created_at DESC
               LIMIT 5"""
        ).fetchall()

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
                        "ticket_id": ticket["ticket_id"],
                        "title": ticket["title"],
                    }
                    execution_tasks = normalized
                    break
        
        tickets_count = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status IN ('todo', 'in_progress', 'in_review')"
        ).fetchone()[0]
    
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


def table_exists(conn, table_name):
    """Check if a table exists in the database."""
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return result is not None


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
    
    with connect() as conn:
        if feedback is None:
            # Remove feedback
            conn.execute(
                """DELETE FROM signal_feedback 
                   WHERE meeting_id = ? AND signal_type = ? AND signal_text = ?""",
                (meeting_id, signal_type, signal_text)
            )
        else:
            # Upsert feedback
            conn.execute(
                """INSERT INTO signal_feedback (meeting_id, signal_type, signal_text, feedback)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(meeting_id, signal_type, signal_text) 
                   DO UPDATE SET feedback = ?, updated_at = CURRENT_TIMESTAMP""",
                (meeting_id, signal_type, signal_text, feedback, feedback)
            )
        conn.commit()
    
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
    
    with connect() as conn:
        # ===== COACHING SUGGESTIONS BASED ON APP STATE =====
        
        # 1. Check for blocked tickets (HIGH PRIORITY)
        blocked_tickets = conn.execute(
            """SELECT ticket_id, title FROM tickets 
               WHERE status = 'blocked' 
               ORDER BY updated_at DESC LIMIT 3"""
        ).fetchall()
        for t in blocked_tickets:
            highlight_id = f"blocked-{t['ticket_id']}"
            if highlight_id not in dismissed_ids:
                highlights.append({
                    "id": highlight_id,
                    "type": "blocker",
                    "label": "🚧 Blocked Ticket",
                    "text": f"{t['ticket_id']}: {t['title']}",
                    "action": "Unblock this ticket to keep making progress",
                    "link": f"/tickets?focus={t['ticket_id']}",
                    "link_text": "View Ticket"
                })
        
        # 2. Check for stale in-progress tickets (> 3 days old)
        stale_tickets = conn.execute(
            """SELECT ticket_id, title, updated_at FROM tickets 
               WHERE status = 'in_progress' 
               AND date(updated_at) < date('now', '-3 days')
               ORDER BY updated_at ASC LIMIT 2"""
        ).fetchall()
        for t in stale_tickets:
            highlight_id = f"stale-{t['ticket_id']}"
            if highlight_id not in dismissed_ids:
                highlights.append({
                    "id": highlight_id,
                    "type": "action",
                    "label": "⏰ Stale Work",
                    "text": f"{t['ticket_id']}: {t['title']}",
                    "action": "This has been in progress for a while. Complete or update it?",
                    "link": f"/tickets?focus={t['ticket_id']}",
                    "link_text": "Update Status"
                })
        
        # 3. Check sprint progress
        sprint = conn.execute("SELECT * FROM sprint_settings WHERE id = 1").fetchone()
        if sprint and sprint['sprint_start_date']:
            try:
                start = datetime.strptime(sprint['sprint_start_date'], '%Y-%m-%d')
                length = sprint['sprint_length_days'] or 14
                end = start + timedelta(days=length)
                now = datetime.now()
                progress = min(100, max(0, int((now - start).days / length * 100)))
                days_left = (end - now).days
                
                # Sprint ending soon
                if 0 < days_left <= 3 and f"sprint-ending" not in dismissed_ids:
                    todo_count = conn.execute(
                        "SELECT COUNT(*) as c FROM tickets WHERE status = 'todo'"
                    ).fetchone()['c']
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
                    ticket_count = conn.execute(
                        "SELECT COUNT(*) as c FROM tickets"
                    ).fetchone()['c']
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
        
        # 4. Check for unreviewed signals
        unreviewed = conn.execute(
            """SELECT COUNT(*) as c FROM signal_status 
               WHERE status = 'pending' OR status IS NULL"""
        ).fetchone()
        if unreviewed and unreviewed['c'] > 5 and "review-signals" not in dismissed_ids:
            highlights.append({
                "id": "review-signals",
                "type": "action",
                "label": "📥 Unreviewed Signals",
                "text": f"{unreviewed['c']} signals waiting for your review",
                "action": "Validate signals to build your knowledge base",
                "link": "/signals",
                "link_text": "Review Signals"
            })
        
        # 5. Check workflow mode progress
        # (suggest moving to next mode if current is complete)
        
        # 6. Recent meeting with unprocessed signals
        recent_meeting = conn.execute(
            """SELECT id, meeting_name, signals_json, meeting_date
               FROM meeting_summaries 
               WHERE signals_json IS NOT NULL
               ORDER BY COALESCE(meeting_date, created_at) DESC 
               LIMIT 1"""
        ).fetchone()
        if recent_meeting:
            try:
                signals = json.loads(recent_meeting['signals_json']) if recent_meeting['signals_json'] else {}
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
        
        # 9. No recent meetings (encourage logging)
        meeting_count = conn.execute(
            """SELECT COUNT(*) as c FROM meeting_summaries 
               WHERE date(created_at) > date('now', '-7 days')"""
        ).fetchone()
        if meeting_count and meeting_count['c'] == 0 and "log-meeting" not in dismissed_ids:
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
    
    with connect() as conn:
        # Find the meeting by id when available, fallback to name
        meeting = None
        if meeting_id:
            meeting = conn.execute(
                """SELECT id, meeting_name, synthesized_notes, raw_text, signals_json
                   FROM meeting_summaries 
                   WHERE id = ?
                   LIMIT 1""",
                (meeting_id,)
            ).fetchone()
        if not meeting:
            meeting = conn.execute(
                """SELECT id, meeting_name, synthesized_notes, raw_text, signals_json
                   FROM meeting_summaries 
                   WHERE meeting_name = ?
                   LIMIT 1""",
                (source,)
            ).fetchone()
    
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
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO signal_status (meeting_id, signal_type, signal_text, status, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(meeting_id, signal_type, signal_text) 
               DO UPDATE SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP""",
            (meeting_id, signal_type, signal_text, status, notes, status, notes)
        )
        conn.commit()
    
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
    
    # Generate ticket ID
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM tickets").fetchone()["c"]
        ticket_id = f"SIG-{count + 1}"
        
        # Determine priority based on signal type
        priority_map = {"blocker": "high", "risk": "high", "action_item": "medium", "decision": "low", "idea": "low"}
        priority = priority_map.get(signal_type, "medium")
        
        # Get meeting name for context
        meeting = conn.execute(
            "SELECT meeting_name FROM meeting_summaries WHERE id = ?", (meeting_id,)
        ).fetchone()
        meeting_name = meeting["meeting_name"] if meeting else "Unknown Meeting"
        
        # Create ticket
        conn.execute(
            """INSERT INTO tickets (ticket_id, title, description, status, priority, ai_summary, created_at)
               VALUES (?, ?, ?, 'backlog', ?, ?, CURRENT_TIMESTAMP)""",
            (ticket_id, signal_text[:100], f"Signal from: {meeting_name}\n\nOriginal Signal ({signal_type}):\n{signal_text}", 
             priority, f"Converted from {signal_type} signal: {signal_text[:150]}...")
        )
        
        ticket_row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
        ticket_db_id = ticket_row["id"]
        
        # Update signal status
        conn.execute(
            """INSERT INTO signal_status (meeting_id, signal_type, signal_text, status, converted_to, converted_ref_id, updated_at)
               VALUES (?, ?, ?, 'completed', 'ticket', ?, CURRENT_TIMESTAMP)
               ON CONFLICT(meeting_id, signal_type, signal_text) 
               DO UPDATE SET status = 'completed', converted_to = 'ticket', converted_ref_id = ?, updated_at = CURRENT_TIMESTAMP""",
            (meeting_id, signal_type, signal_text, ticket_db_id, ticket_db_id)
        )
        conn.commit()
    
    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "ticket_db_id": ticket_db_id})


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
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO ai_memory (source_type, source_query, content, status, tags, importance, created_at)
               VALUES (?, ?, ?, 'approved', ?, ?, CURRENT_TIMESTAMP)""",
            (source_type, source_query, content, tags, importance)
        )
        conn.commit()
        memory_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    
    return JSONResponse({"status": "ok", "memory_id": memory_id})


@app.post("/api/ai-memory/reject")
async def reject_ai_response(request: Request):
    """Mark an AI response as rejected (don't save to memory)."""
    data = await request.json()
    source_query = data.get("query", "")
    content = data.get("content", "")
    
    # We can optionally log rejected responses for ML training
    with connect() as conn:
        conn.execute(
            """INSERT INTO ai_memory (source_type, source_query, content, status, importance, created_at)
               VALUES ('quick_ask', ?, ?, 'rejected', 0, CURRENT_TIMESTAMP)""",
            (source_query, content[:500])  # Store truncated for training feedback
        )
        conn.commit()
    
    return JSONResponse({"status": "ok"})


# ============================================
# Notification API Endpoints
# ============================================

@app.get("/api/notifications")
async def get_notifications(limit: int = 10):
    """Get user notifications with optional limit."""
    # Try Supabase first (primary data source in production)
    supabase = get_supabase()
    
    if supabase:
        try:
            result = supabase.table("notifications").select("*").or_("actioned.eq.false,actioned.is.null").order("created_at", desc=True).limit(limit).execute()
            
            if result.data:
                notifications = []
                for row in result.data:
                    n_dict = {
                        "id": row.get("id"),
                        "type": row.get("type") or row.get("notification_type"),
                        "title": row.get("title"),
                        "message": row.get("body") or row.get("message"),
                        "data": row.get("data"),
                        "read": row.get("read", False),
                        "created_at": row.get("created_at"),
                        "actioned": row.get("actioned", False),
                        "action_taken": row.get("action_taken"),
                        "expires_at": row.get("expires_at"),
                    }
                    # Parse action_url from data JSON if available
                    if n_dict.get('data'):
                        try:
                            data = n_dict['data'] if isinstance(n_dict['data'], dict) else json.loads(n_dict['data'])
                            n_dict['action_url'] = data.get('action_url', '')
                        except:
                            pass
                    notifications.append(n_dict)
                return JSONResponse({"notifications": notifications})
        except Exception as e:
            logger.warning(f"Supabase notifications fetch failed, falling back to SQLite: {e}")
    
    # SQLite fallback
    with connect() as conn:
        # Check if notifications table exists
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
        ).fetchone()
        
        if not table_check:
            return JSONResponse({"notifications": []})
        
        # Query using new schema (notification_type, body) with fallback for old schema
        try:
            notifications = conn.execute(
                """SELECT id, notification_type as type, title, body as message, 
                          data, read, created_at, actioned, action_taken, expires_at
                   FROM notifications 
                   WHERE actioned = 0 OR actioned IS NULL
                   ORDER BY 
                     CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                     created_at DESC 
                   LIMIT ?""",
                (limit,)
            ).fetchall()
        except Exception:
            # Fall back to old schema if new columns don't exist
            notifications = conn.execute(
                """SELECT id, type, title, message, link, read, created_at 
                   FROM notifications 
                   ORDER BY created_at DESC 
                   LIMIT ?""",
                (limit,)
            ).fetchall()
        
        result = []
        for n in notifications:
            n_dict = dict(n)
            # Parse action_url from data JSON if available
            if 'data' in n_dict and n_dict['data']:
                try:
                    import json
                    data = json.loads(n_dict['data']) if isinstance(n_dict['data'], str) else n_dict['data']
                    n_dict['action_url'] = data.get('action_url', '')
                    # Include read_at for frontend compatibility
                    n_dict['read_at'] = n_dict['created_at'] if n_dict.get('read') else None
                except:
                    pass
            result.append(n_dict)
        
        return JSONResponse({"notifications": result})


@app.get("/api/notifications/count")
async def get_notification_count():
    """Get count of unread notifications."""
    # Try Supabase first
    supabase = get_supabase()
    
    if supabase:
        try:
            # Count unread
            unread_result = supabase.table("notifications").select("id", count="exact").eq("read", False).execute()
            unread = unread_result.count or 0
            
            # Count total (non-actioned)
            total_result = supabase.table("notifications").select("id", count="exact").or_("actioned.eq.false,actioned.is.null").execute()
            total = total_result.count or 0
            
            return JSONResponse({"unread": unread, "total": total})
        except Exception as e:
            logger.warning(f"Supabase notification count failed: {e}")
    
    # SQLite fallback
    with connect() as conn:
        # Check if notifications table exists
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
        ).fetchone()
        
        if not table_check:
            return JSONResponse({"unread": 0, "total": 0})
        
        result = conn.execute(
            """SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN read = 0 THEN 1 ELSE 0 END) as unread
               FROM notifications"""
        ).fetchone()
        
        return JSONResponse({
            "unread": result["unread"] or 0,
            "total": result["total"] or 0
        })


@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark a notification as read."""
    # Try Supabase first
    supabase = get_supabase()
    
    if supabase:
        try:
            supabase.table("notifications").update({"read": True}).eq("id", notification_id).execute()
            return JSONResponse({"status": "ok"})
        except Exception as e:
            logger.warning(f"Supabase mark read failed: {e}")
    
    # SQLite fallback
    with connect() as conn:
        # Check if notifications table exists
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
        ).fetchone()
        
        if not table_check:
            return JSONResponse({"status": "ok"})
        
        conn.execute(
            "UPDATE notifications SET read = 1 WHERE id = ?",
            (notification_id,)
        )
        conn.commit()
    
    return JSONResponse({"status": "ok"})


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read():
    """Mark all notifications as read."""
    # Try Supabase first
    supabase = get_supabase()
    
    if supabase:
        try:
            supabase.table("notifications").update({"read": True}).eq("read", False).execute()
            return JSONResponse({"status": "ok"})
        except Exception as e:
            logger.warning(f"Supabase mark all read failed: {e}")
    
    # SQLite fallback
    with connect() as conn:
        # Check if notifications table exists
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
        ).fetchone()
        
        if not table_check:
            return JSONResponse({"status": "ok"})
        
        conn.execute("UPDATE notifications SET read = 1 WHERE read = 0")
        conn.commit()
    
    return JSONResponse({"status": "ok"})


@app.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete a notification."""
    # Try Supabase first
    supabase = get_supabase()
    
    if supabase:
        try:
            supabase.table("notifications").delete().eq("id", notification_id).execute()
            return JSONResponse({"status": "ok"})
        except Exception as e:
            logger.warning(f"Supabase delete failed: {e}")
    
    # SQLite fallback
    with connect() as conn:
        conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
        conn.commit()
    return JSONResponse({"status": "ok"})


@app.post("/api/ai-memory/to-action")
async def convert_ai_to_action(request: Request):
    """Convert an AI response into a ticket/action item."""
    data = await request.json()
    content = data.get("content", "")
    query = data.get("query", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM tickets").fetchone()["c"]
        ticket_id = f"AI-{count + 1}"
        
        # Extract first line as title
        title = content.split('\n')[0][:100].strip('*#- ')
        if not title:
            title = query[:100] if query else "AI Generated Action Item"
        
        conn.execute(
            """INSERT INTO tickets (ticket_id, title, description, status, priority, ai_summary, created_at)
               VALUES (?, ?, ?, 'backlog', 'medium', ?, CURRENT_TIMESTAMP)""",
            (ticket_id, title, f"From AI Query: {query}\n\nAI Response:\n{content}", f"AI insight: {content[:150]}...")
        )
        conn.commit()
        ticket_db_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    
    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "ticket_db_id": ticket_db_id})


# ============================================
# Settings API Endpoints
# ============================================

@app.get("/api/settings/mode/suggested")
async def get_suggested_mode():
    """Get the suggested workflow mode based on sprint cadence.
    
    Uses SprintModeDetectJob logic to suggest A/B/C/D mode.
    Returns suggestion along with sprint context info.
    """
    from src.app.services.background_jobs import SprintModeDetectJob
    
    job = SprintModeDetectJob()
    sprint_info = job.get_current_sprint_info()
    suggested = job.detect_suggested_mode()
    mode_info = job.MODES.get(suggested, {})
    
    # Map internal mode (A/B/C/D) to UI mode (mode-a, mode-b, etc.)
    ui_mode_map = {
        "A": "mode-a",
        "B": "mode-b", 
        "C": "mode-c",
        "D": "mode-d",
    }
    ui_mode = ui_mode_map.get(suggested, "mode-a")
    
    return JSONResponse({
        "suggested_mode": ui_mode,
        "mode_letter": suggested,
        "mode_name": mode_info.get("name", ""),
        "mode_description": mode_info.get("description", ""),
        "sprint_info": sprint_info,
    })


@app.get("/api/settings/mode/expected-duration")
async def get_expected_mode_duration():
    """Get expected duration for each mode based on historical data with defaults.
    
    Returns expected minutes per mode, calculated from historical time tracking
    data with sensible defaults when insufficient data exists.
    """
    # Default expected durations (in minutes) based on typical workflow
    # These are conservative defaults that will be overridden by actual data
    defaults = {
        "mode-a": 60,   # Context Distillation: ~1 hour
        "mode-b": 45,   # Implementation Planning: ~45 min
        "mode-c": 90,   # Assisted Draft Intake: ~1.5 hours
        "mode-d": 60,   # Deep Review: ~1 hour
        "mode-e": 30,   # Promotion Readiness: ~30 min
        "mode-f": 20,   # Controlled Ingress/Egress: ~20 min
        "mode-g": 120,  # Execution: ~2 hours (variable)
    }
    
    result = {}
    
    with connect() as conn:
        # Get historical averages from mode_sessions table
        for mode, default_mins in defaults.items():
            row = conn.execute("""
                SELECT 
                    COUNT(*) as session_count,
                    AVG(duration_seconds) as avg_seconds,
                    MIN(duration_seconds) as min_seconds,
                    MAX(duration_seconds) as max_seconds
                FROM mode_sessions
                WHERE mode = ? AND duration_seconds IS NOT NULL AND duration_seconds > 0
            """, (mode,)).fetchone()
            
            session_count = row["session_count"] if row else 0
            
            if session_count >= 3:  # Need at least 3 data points to trust the average
                avg_mins = int((row["avg_seconds"] or 0) / 60)
                # Use a blend: 70% historical, 30% default (to avoid extreme values)
                expected_mins = int(avg_mins * 0.7 + default_mins * 0.3)
            else:
                expected_mins = default_mins
            
            result[mode] = {
                "expected_minutes": expected_mins,
                "default_minutes": default_mins,
                "historical_sessions": session_count,
                "has_sufficient_data": session_count >= 3,
            }
    
    return JSONResponse(result)


@app.post("/api/workflow/check-completion")
async def check_workflow_completion(request: Request):
    """Check if a mode's workflow is complete and celebrate if done early.
    
    Creates a celebration notification if:
    1. All checkboxes for the mode are complete
    2. Completed before the expected phase end time
    
    Returns celebration status and creates notification if applicable.
    """
    from src.app.services.notification_queue import (
        NotificationQueue, Notification, NotificationType, NotificationPriority
    )
    
    data = await request.json()
    mode = data.get("mode", "mode-a")
    progress = data.get("progress", [])  # List of booleans
    elapsed_seconds = data.get("elapsed_seconds", 0)  # Time spent in this mode session
    
    # Check if all checkboxes are complete
    if not progress or not all(progress):
        return JSONResponse({
            "complete": False,
            "celebrate": False,
            "message": "Workflow not complete"
        })
    
    # Get expected duration for this mode
    expected_data = await get_expected_mode_duration()
    expected_json = expected_data.body.decode()
    import json
    expected = json.loads(expected_json)
    mode_expected = expected.get(mode, {})
    expected_minutes = mode_expected.get("expected_minutes", 60)
    expected_seconds = expected_minutes * 60
    
    # Check if completed early (within expected time)
    is_early = elapsed_seconds < expected_seconds
    time_saved_seconds = max(0, expected_seconds - elapsed_seconds)
    time_saved_minutes = int(time_saved_seconds / 60)
    
    # Mode display names
    mode_names = {
        "mode-a": "Context Distillation",
        "mode-b": "Implementation Planning",
        "mode-c": "Assisted Draft Intake",
        "mode-d": "Deep Review",
        "mode-e": "Promotion Readiness",
        "mode-f": "Controlled Sync",
        "mode-g": "Execution",
    }
    mode_name = mode_names.get(mode, mode)
    
    # Create celebration notification
    queue = NotificationQueue()
    
    if is_early:
        title = f"🎉 {mode_name} Complete!"
        body = f"Amazing work! You finished {len(progress)} tasks in {int(elapsed_seconds/60)} minutes.\n\n"
        body += f"⏱️ **{time_saved_minutes} minutes ahead of schedule!**\n\n"
        body += "Keep up the excellent momentum! 🚀"
        celebration_type = "early_finish"
    else:
        title = f"✅ {mode_name} Complete"
        body = f"Great job completing all {len(progress)} tasks!\n\n"
        body += f"Time taken: {int(elapsed_seconds/60)} minutes"
        celebration_type = "complete"
    
    notification = Notification(
        notification_type=NotificationType.COACH_RECOMMENDATION,
        title=title,
        body=body,
        data={
            "type": "mode_completion",
            "celebration_type": celebration_type,
            "mode": mode,
            "tasks_completed": len(progress),
            "elapsed_seconds": elapsed_seconds,
            "expected_seconds": expected_seconds,
            "time_saved_seconds": time_saved_seconds if is_early else 0,
            "show_confetti": is_early,  # Trigger confetti on open
        },
        priority=NotificationPriority.HIGH if is_early else NotificationPriority.NORMAL,
        expires_at=datetime.now() + timedelta(days=1),
    )
    
    notification_id = queue.create(notification)
    
    return JSONResponse({
        "complete": True,
        "celebrate": is_early,
        "notification_id": notification_id,
        "time_saved_minutes": time_saved_minutes if is_early else 0,
        "message": f"Completed in {int(elapsed_seconds/60)} min (expected: {expected_minutes} min)"
    })


@app.get("/api/workflow/overdue-check")
async def check_overdue_status():
    """Check if current mode is overdue and get encouragement context.
    
    Returns overdue status and optionally triggers an encouragement notification.
    """
    from src.app.services.background_jobs import OverdueEncouragementJob
    
    job = OverdueEncouragementJob()
    
    # Get current mode info without creating notification
    mode_info = job._get_current_mode_info()
    
    if not mode_info.get("mode"):
        return JSONResponse({
            "is_overdue": False,
            "mode": None,
            "message": "No active mode"
        })
    
    overdue_info = job._check_if_overdue(mode_info)
    context = job._get_task_context(mode_info)
    
    return JSONResponse({
        "mode": mode_info["mode"],
        "elapsed_minutes": int(mode_info["elapsed_seconds"] / 60),
        "expected_minutes": overdue_info["expected_minutes"],
        "is_overdue": overdue_info["is_overdue"],
        "overdue_minutes": overdue_info["overdue_minutes"],
        "completion_pct": overdue_info["completion_pct"],
        "tasks_remaining": overdue_info["tasks_remaining"],
        "task_focus": context.get("task_focus"),
        "ticket_title": context.get("ticket_title"),
        "pending_tasks": context.get("pending_tasks", [])[:5],
    })


@app.post("/api/workflow/send-encouragement")
async def send_overdue_encouragement():
    """Manually trigger an overdue encouragement notification."""
    from src.app.services.background_jobs import OverdueEncouragementJob
    
    job = OverdueEncouragementJob()
    result = job.run()
    
    return JSONResponse(result)


# =============================================================================
# BACKGROUND JOB RUNNER API (for pg_cron integration)
# =============================================================================

@app.post("/api/v1/jobs/{job_name}/run")
async def run_background_job(job_name: str, request: Request):
    """
    Execute a background job by name.
    
    Called by Supabase pg_cron via pg_net HTTP requests.
    Also available for manual triggering.
    
    Jobs:
    - one_on_one_prep: 1:1 prep digest
    - stale_ticket_alert: Alert for stale tickets
    - grooming_match: Match grooming meetings to tickets
    - sprint_mode_detect: Detect suggested workflow mode
    - overdue_encouragement: Send encouraging messages for overdue tasks
    """
    from src.app.services.background_jobs import run_job, JOB_CONFIGS
    
    # Get optional run_id from pg_cron trigger
    run_id = request.headers.get("X-Job-Run-Id")
    
    # Validate job name
    valid_jobs = list(JOB_CONFIGS.keys())
    if job_name not in valid_jobs:
        return JSONResponse({
            "error": f"Unknown job: {job_name}",
            "available_jobs": valid_jobs,
        }, status_code=400)
    
    try:
        result = run_job(job_name)
        
        return JSONResponse({
            "job_name": job_name,
            "status": "completed",
            "run_id": run_id,
            "result": result,
            "executed_at": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Job {job_name} failed: {str(e)}")
        return JSONResponse({
            "job_name": job_name,
            "status": "failed",
            "run_id": run_id,
            "error": str(e),
            "executed_at": datetime.now().isoformat(),
        }, status_code=500)


@app.get("/api/v1/jobs")
async def list_background_jobs():
    """List all available background jobs and their schedules."""
    from src.app.services.background_jobs import JOB_CONFIGS
    
    jobs = []
    for key, config in JOB_CONFIGS.items():
        jobs.append({
            "name": key,
            "display_name": config.name,
            "description": config.description,
            "schedule": config.schedule,
            "enabled": config.enabled,
        })
    
    # Get scheduler status if available
    try:
        from src.app.services.scheduler import get_scheduler, get_next_job_runs
        scheduler = get_scheduler()
        if scheduler:
            scheduling_info = {
                "method": "apscheduler",
                "description": "Jobs are scheduled via in-app APScheduler",
                "status": "running" if scheduler.running else "stopped",
                "next_runs": get_next_job_runs(),
            }
        else:
            scheduling_info = {
                "method": "manual",
                "description": "Scheduler not running (development mode or not initialized)",
                "status": "disabled",
            }
    except Exception:
        scheduling_info = {
            "method": "supabase_pg_cron",
            "description": "Jobs are scheduled via Supabase pg_cron and triggered via pg_net HTTP requests",
        }
    
    return JSONResponse({
        "jobs": jobs,
        "scheduling": scheduling_info,
    })


@app.get("/api/v1/tracing/status")
async def get_tracing_status():
    """Debug endpoint to check LangSmith tracing status."""
    import os
    
    tracing_status = {
        "langchain_tracing_v2": os.environ.get("LANGCHAIN_TRACING_V2", "not set"),
        "langsmith_tracing": os.environ.get("LANGSMITH_TRACING", "not set"),
        "langsmith_api_key_set": bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")),
        "langsmith_project": os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "signalflow"),
        "langsmith_endpoint": os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    }
    
    # Check if tracing module is available and enabled
    try:
        from src.app.tracing import is_tracing_enabled, get_langsmith_client, get_project_name
        tracing_status["tracing_module_available"] = True
        tracing_status["tracing_enabled"] = is_tracing_enabled()
        tracing_status["project_name"] = get_project_name()
        
        # Try to get client
        client = get_langsmith_client()
        tracing_status["langsmith_client_initialized"] = client is not None
        
        if client:
            # Try a simple health check
            try:
                # List a few runs to verify connectivity
                runs = list(client.list_runs(project_name=get_project_name(), limit=1))
                tracing_status["langsmith_connectivity"] = "ok"
                tracing_status["recent_runs_count"] = len(runs)
            except Exception as e:
                tracing_status["langsmith_connectivity"] = f"error: {str(e)}"
    except ImportError as e:
        tracing_status["tracing_module_available"] = False
        tracing_status["import_error"] = str(e)
    
    return JSONResponse(tracing_status)


@app.post("/api/settings/mode")
async def set_workflow_mode(request: Request):
    """Save the current workflow mode to the database."""
    data = await request.json()
    mode = data.get("mode", "mode-a")
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO settings (key, value, updated_at) 
               VALUES ('current_mode', ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP""",
            (mode, mode)
        )
        conn.commit()
    
    return JSONResponse({"status": "ok", "mode": mode})


@app.get("/api/settings/mode")
async def get_workflow_mode():
    """Get the current workflow mode from the database."""
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'current_mode'").fetchone()
        mode = row["value"] if row else "mode-a"
    
    return JSONResponse({"mode": mode})


@app.get("/api/settings/ai-model")
async def get_ai_model():
    """Get current AI model setting."""
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'ai_model'").fetchone()
        model = row["value"] if row else "gpt-4o-mini"
    
    return JSONResponse({"model": model})


@app.post("/api/settings/ai-model")
async def set_ai_model(request: Request):
    """Set AI model to use."""
    data = await request.json()
    model = data.get("model", "gpt-4o-mini")
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO settings (key, value, updated_at) 
               VALUES ('ai_model', ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP""",
            (model, model)
        )
        conn.commit()
    
    return JSONResponse({"status": "ok", "model": model})


@app.post("/api/settings/workflow-progress")
async def save_workflow_progress(request: Request):
    """Save workflow checklist progress for a specific mode."""
    data = await request.json()
    mode = data.get("mode", "mode-a")
    progress = data.get("progress", [])
    
    import json
    progress_json = json.dumps(progress)
    key = f"workflow_progress_{mode}"
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO settings (key, value, updated_at) 
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP""",
            (key, progress_json, progress_json)
        )
        conn.commit()
    
    return JSONResponse({"status": "ok", "mode": mode, "progress": progress})


@app.get("/api/settings/workflow-progress/{mode}")
async def get_workflow_progress(mode: str):
    """Get workflow checklist progress for a specific mode."""
    import json
    key = f"workflow_progress_{mode}"
    
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row:
            try:
                progress = json.loads(row["value"])
            except:
                progress = []
        else:
            progress = []
    
    return JSONResponse({"mode": mode, "progress": progress})


# ============================================
# Mode Timer API Endpoints
# Track time spent in each workflow mode
# ============================================

@app.post("/api/mode-timer/start")
async def start_mode_timer(request: Request):
    """Start a timer session for a specific mode."""
    data = await request.json()
    mode = data.get("mode", "implementation")
    
    today = datetime.now().strftime("%Y-%m-%d")
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with connect() as conn:
        # Check if there's an active session for this mode (no ended_at)
        active = conn.execute(
            "SELECT id FROM mode_sessions WHERE mode = ? AND ended_at IS NULL",
            (mode,)
        ).fetchone()
        
        if active:
            # Already active, return existing session
            return JSONResponse({"status": "already_active", "session_id": active["id"]})
        
        # Create new session
        cur = conn.execute(
            """INSERT INTO mode_sessions (mode, started_at, date) VALUES (?, ?, ?)""",
            (mode, started_at, today)
        )
        session_id = cur.lastrowid
        conn.commit()
    
    return JSONResponse({"status": "ok", "session_id": session_id, "started_at": started_at})


@app.post("/api/mode-timer/stop")
async def stop_mode_timer(request: Request):
    """Stop the active timer session for a specific mode."""
    data = await request.json()
    mode = data.get("mode", "implementation")
    
    ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with connect() as conn:
        # Find active session
        active = conn.execute(
            "SELECT id, started_at FROM mode_sessions WHERE mode = ? AND ended_at IS NULL",
            (mode,)
        ).fetchone()
        
        if not active:
            return JSONResponse({"status": "no_active_session"})
        
        # Calculate duration
        start_time = datetime.strptime(active["started_at"], "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(ended_at, "%Y-%m-%d %H:%M:%S")
        duration = int((end_time - start_time).total_seconds())
        
        # Update session
        conn.execute(
            """UPDATE mode_sessions SET ended_at = ?, duration_seconds = ? WHERE id = ?""",
            (ended_at, duration, active["id"])
        )
        conn.commit()
    
    return JSONResponse({
        "status": "ok", 
        "session_id": active["id"], 
        "duration_seconds": duration,
        "ended_at": ended_at
    })


@app.get("/api/mode-timer/status")
async def get_mode_timer_status():
    """Get current timer status for all modes."""
    with connect() as conn:
        # Get active sessions
        active_sessions = conn.execute(
            "SELECT mode, id, started_at FROM mode_sessions WHERE ended_at IS NULL"
        ).fetchall()
        
        active = {}
        for session in active_sessions:
            start_time = datetime.strptime(session["started_at"], "%Y-%m-%d %H:%M:%S")
            elapsed = int((datetime.now() - start_time).total_seconds())
            active[session["mode"]] = {
                "session_id": session["id"],
                "started_at": session["started_at"],
                "elapsed_seconds": elapsed
            }
    
    return JSONResponse({"active_sessions": active})


@app.get("/api/mode-timer/stats")
async def get_mode_timer_stats(days: int = 7):
    """Get time statistics for all modes."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    with connect() as conn:
        # Get totals and averages for each mode
        stats = conn.execute(
            """
            SELECT 
                mode,
                COUNT(*) as session_count,
                SUM(duration_seconds) as total_seconds,
                AVG(duration_seconds) as avg_session_seconds
            FROM mode_sessions
            WHERE date >= ? AND duration_seconds IS NOT NULL
            GROUP BY mode
            """,
            (cutoff,)
        ).fetchall()
        
        # Get today's totals
        today = datetime.now().strftime("%Y-%m-%d")
        today_stats = conn.execute(
            """
            SELECT 
                mode,
                SUM(duration_seconds) as total_seconds,
                COUNT(*) as session_count
            FROM mode_sessions
            WHERE date = ? AND duration_seconds IS NOT NULL
            GROUP BY mode
            """,
            (today,)
        ).fetchall()
    
    result = {
        "period_days": days,
        "modes": {},
        "today": {}
    }
    
    for s in stats:
        result["modes"][s["mode"]] = {
            "session_count": s["session_count"],
            "total_seconds": s["total_seconds"] or 0,
            "avg_session_seconds": int(s["avg_session_seconds"]) if s["avg_session_seconds"] else 0,
            "total_formatted": format_duration(s["total_seconds"] or 0),
            "avg_formatted": format_duration(int(s["avg_session_seconds"]) if s["avg_session_seconds"] else 0)
        }
    
    for s in today_stats:
        result["today"][s["mode"]] = {
            "total_seconds": s["total_seconds"] or 0,
            "session_count": s["session_count"],
            "total_formatted": format_duration(s["total_seconds"] or 0)
        }
    
    return JSONResponse(result)


# ============================================
# LangSmith Evaluation API Endpoints
# Track agent quality and improvement feedback
# ============================================

@app.post("/api/evaluations/feedback")
async def submit_evaluation_feedback(request: Request):
    """
    Submit feedback for a LangSmith trace.
    
    Used to provide human feedback on agent outputs for improvement.
    
    Body:
        run_id: The LangSmith run ID
        key: Feedback dimension (helpfulness, accuracy, relevance)
        score: 0.0 to 1.0 (optional)
        value: Categorical value (optional)
        comment: Freeform comment
        correction: What the correct output should have been
    """
    from src.app.services.evaluations import submit_feedback
    
    data = await request.json()
    run_id = data.get("run_id")
    
    if not run_id:
        return JSONResponse({"error": "run_id is required"}, status_code=400)
    
    feedback_id = submit_feedback(
        run_id=run_id,
        key=data.get("key", "user_feedback"),
        score=data.get("score"),
        value=data.get("value"),
        comment=data.get("comment"),
        correction=data.get("correction"),
        source_info={"type": "api", "user_id": data.get("user_id")},
    )
    
    return JSONResponse({
        "status": "ok" if feedback_id else "disabled",
        "feedback_id": feedback_id,
    })


@app.post("/api/evaluations/thumbs")
async def submit_thumbs_feedback(request: Request):
    """
    Submit simple thumbs up/down feedback.
    
    Body:
        run_id: The LangSmith run ID
        is_positive: true for thumbs up, false for thumbs down (or score: 1/0)
        comment: Optional explanation
    """
    from src.app.services.evaluations import submit_thumbs_feedback as submit_thumbs
    
    data = await request.json()
    run_id = data.get("run_id")
    
    if not run_id:
        return JSONResponse({"error": "run_id is required"}, status_code=400)
    
    # Accept both is_positive (bool) and score (0/1) formats
    is_positive = data.get("is_positive")
    if is_positive is None:
        score = data.get("score")
        is_positive = bool(score) if score is not None else True
    
    feedback_id = submit_thumbs(
        run_id=run_id,
        is_positive=is_positive,
        comment=data.get("comment"),
        user_id=data.get("user_id"),
    )
    
    return JSONResponse({
        "status": "ok" if feedback_id else "disabled",
        "feedback_id": str(feedback_id) if feedback_id else None,
    })


@app.post("/api/evaluations/evaluate-signal")
async def evaluate_signal_endpoint(request: Request):
    """
    Evaluate the quality of an extracted signal.
    
    Body:
        signal_text: The signal text to evaluate
        signal_type: Type (action_item, decision, blocker, risk, idea)
        source_context: The meeting transcript context
        run_id: Optional LangSmith run ID to attach feedback
    """
    from src.app.services.evaluations import evaluate_signal_quality, submit_feedback
    
    data = await request.json()
    
    if not data.get("signal_text") or not data.get("signal_type"):
        return JSONResponse({"error": "signal_text and signal_type required"}, status_code=400)
    
    result = evaluate_signal_quality(
        signal_text=data["signal_text"],
        signal_type=data["signal_type"],
        source_context=data.get("source_context", ""),
    )
    
    # Submit to LangSmith if run_id provided
    if data.get("run_id") and result.score is not None:
        submit_feedback(
            run_id=data["run_id"],
            key="signal_quality",
            score=result.score,
            comment=result.reasoning,
            source_info={"type": "auto_evaluator", "signal_type": data["signal_type"]},
        )
    
    return JSONResponse({
        "key": result.key,
        "score": result.score,
        "reasoning": result.reasoning,
        "metadata": result.metadata,
    })


@app.post("/api/evaluations/evaluate-dikw")
async def evaluate_dikw_promotion_endpoint(request: Request):
    """
    Evaluate the quality of a DIKW promotion.
    
    Body:
        original_item: The original DIKW item text
        original_level: data/information/knowledge/wisdom
        promoted_item: The promoted item text  
        promoted_level: The new level
        run_id: Optional LangSmith run ID
    """
    from src.app.services.evaluations import evaluate_dikw_promotion, submit_feedback
    
    data = await request.json()
    
    required = ["original_item", "original_level", "promoted_item", "promoted_level"]
    if not all(data.get(k) for k in required):
        return JSONResponse({"error": f"Required fields: {required}"}, status_code=400)
    
    result = evaluate_dikw_promotion(
        original_item=data["original_item"],
        original_level=data["original_level"],
        promoted_item=data["promoted_item"],
        promoted_level=data["promoted_level"],
    )
    
    # Submit to LangSmith if run_id provided
    if data.get("run_id") and result.score is not None:
        submit_feedback(
            run_id=data["run_id"],
            key="dikw_promotion_quality",
            score=result.score,
            comment=result.reasoning,
            source_info={"type": "auto_evaluator"},
        )
    
    return JSONResponse({
        "key": result.key,
        "score": result.score,
        "reasoning": result.reasoning,
        "metadata": result.metadata,
    })


@app.get("/api/evaluations/summary")
async def get_evaluation_summary(agent_name: Optional[str] = None, days: int = 7):
    """
    Get aggregated feedback summary from LangSmith.
    
    Query params:
        agent_name: Filter by agent (optional)
        days: Number of days to look back (default 7)
    """
    from src.app.services.evaluations import get_feedback_summary
    
    summary = get_feedback_summary(agent_name=agent_name, days=days)
    return JSONResponse(summary)


@app.get("/api/evaluations/dashboard")
async def get_evaluation_dashboard():
    """
    Get a comprehensive evaluation dashboard with actionable insights.
    
    Returns:
        - Overall quality scores
        - Improvement suggestions based on low scores
        - Recent traces with issues
        - Recommended actions
    """
    from src.app.services.evaluations import get_feedback_summary, is_evaluation_enabled
    
    if not is_evaluation_enabled():
        return JSONResponse({
            "enabled": False,
            "message": "LangSmith evaluation not configured. Set LANGSMITH_API_KEY to enable."
        })
    
    try:
        from langsmith import Client
        from datetime import timedelta
        
        client = Client()
        project_name = os.environ.get("LANGSMITH_PROJECT", "signalflow")
        
        # Get recent runs with low scores
        start_time = datetime.now() - timedelta(days=7)
        
        runs = list(client.list_runs(
            project_name=project_name,
            start_time=start_time,
            limit=100,
        ))
        
        # Analyze runs
        total_runs = len(runs)
        runs_with_feedback = 0
        low_score_runs = []
        score_breakdown = {}
        
        for run in runs:
            if run.feedback_stats:
                runs_with_feedback += 1
                for key, stats in run.feedback_stats.items():
                    if key not in score_breakdown:
                        score_breakdown[key] = {"scores": [], "count": 0}
                    score_breakdown[key]["count"] += stats.get('n', 0)
                    if stats.get('avg') is not None:
                        score_breakdown[key]["scores"].append(stats['avg'])
                        # Track low-scoring runs
                        if stats['avg'] < 0.6:
                            low_score_runs.append({
                                "run_id": str(run.id),
                                "name": run.name,
                                "metric": key,
                                "score": stats['avg'],
                                "created_at": run.start_time.isoformat() if run.start_time else None,
                            })
        
        # Calculate averages and generate insights
        insights = []
        for key, data in score_breakdown.items():
            avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else None
            score_breakdown[key]["average"] = round(avg, 3) if avg else None
            
            if avg and avg < 0.6:
                if key == "helpfulness":
                    insights.append({
                        "metric": key,
                        "score": round(avg, 3),
                        "severity": "high" if avg < 0.4 else "medium",
                        "recommendation": "Responses may not be addressing user needs. Review prompts to ensure they focus on actionable, relevant answers.",
                        "action": "Review system prompts for clarity and user focus",
                    })
                elif key == "relevance":
                    insights.append({
                        "metric": key,
                        "score": round(avg, 3),
                        "severity": "high" if avg < 0.4 else "medium",
                        "recommendation": "Responses may be off-topic. Ensure context is properly passed to agents.",
                        "action": "Check context retrieval and prompt engineering",
                    })
                elif key == "accuracy":
                    insights.append({
                        "metric": key,
                        "score": round(avg, 3),
                        "severity": "high" if avg < 0.4 else "medium",
                        "recommendation": "Factual accuracy issues detected. Consider adding RAG or fact-checking.",
                        "action": "Add source verification or ground truth checks",
                    })
        
        return JSONResponse({
            "enabled": True,
            "project": project_name,
            "period_days": 7,
            "stats": {
                "total_runs": total_runs,
                "runs_with_feedback": runs_with_feedback,
                "evaluation_coverage": f"{(runs_with_feedback/total_runs*100):.1f}%" if total_runs else "0%",
            },
            "scores": {k: {"average": v["average"], "count": v["count"]} for k, v in score_breakdown.items()},
            "insights": insights,
            "low_score_runs": low_score_runs[:10],  # Top 10 issues
            "recommended_actions": [
                "Add thumbs up/down buttons to UI for user feedback",
                "Review low-scoring traces in LangSmith",
                "Update prompts based on feedback patterns",
            ] if insights else [
                "Quality looks good! Consider adding more evaluation dimensions.",
            ],
        })
        
    except Exception as e:
        return JSONResponse({
            "enabled": True,
            "error": str(e),
        })


# ============================================
# Reports API Endpoints
# ============================================

@app.get("/reports")
async def reports_page(request: Request):
    """Render the sprint reports page."""
    return templates.TemplateResponse("reports.html", {"request": request})


@app.get("/api/reports/signals")
async def get_signals_report(days: int = 14):
    """Get signal statistics for the reporting period."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    with connect() as conn:
        # Count signals from meetings
        meetings = conn.execute(
            """
            SELECT signals_json FROM meeting_summaries 
            WHERE (meeting_date >= ? OR (meeting_date IS NULL AND created_at >= ?))
            AND signals_json IS NOT NULL
            """,
            (cutoff, cutoff)
        ).fetchall()
        
        decisions = actions = blockers = risks = ideas = 0
        
        for m in meetings:
            try:
                signals = json.loads(m["signals_json"])
                decisions += len(signals.get("decisions", []))
                actions += len(signals.get("action_items", []))
                blockers += len(signals.get("blockers", []))
                risks += len(signals.get("risks", []))
                ideas += len(signals.get("ideas", []))
            except:
                continue
        
        # Count tickets created in period
        tickets_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM tickets WHERE created_at >= ?",
            (cutoff,)
        ).fetchone()["cnt"]
        
        return JSONResponse({
            "decisions": decisions,
            "actions": actions,
            "blockers": blockers,
            "risks": risks,
            "ideas": ideas,
            "meetings_count": len(meetings),
            "tickets_created": tickets_count
        })


@app.get("/api/reports/workflow-progress")
async def get_workflow_progress_report():
    """Get workflow mode progress for reporting."""
    import json as json_module
    
    with connect() as conn:
        modes = conn.execute(
            "SELECT * FROM workflow_modes WHERE is_active = 1 ORDER BY sort_order"
        ).fetchall()
        
        result = []
        for mode in modes:
            steps = json_module.loads(mode["steps_json"]) if mode["steps_json"] else []
            total_steps = len(steps)
            
            # Get progress from settings
            progress_row = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (f"workflow_progress_{mode['mode_key']}",)
            ).fetchone()
            
            completed = 0
            if progress_row:
                try:
                    progress = json_module.loads(progress_row["value"])
                    completed = sum(1 for p in progress if p)
                except:
                    pass
            
            result.append({
                "mode_key": mode["mode_key"],
                "name": mode["name"],
                "icon": mode["icon"],
                "total_steps": total_steps,
                "progress": completed
            })
        
        return JSONResponse({"modes": result})


@app.get("/api/reports/daily")
async def get_daily_report(days: int = 14):
    """Get daily breakdown for reporting."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    with connect() as conn:
        # Get daily time tracking
        daily_time = conn.execute(
            """
            SELECT date, 
                   SUM(duration_seconds) as total_seconds,
                   COUNT(*) as sessions
            FROM mode_sessions
            WHERE date >= ? AND duration_seconds IS NOT NULL
            GROUP BY date
            ORDER BY date DESC
            """,
            (cutoff,)
        ).fetchall()
        
        # Get daily signal counts
        daily_signals = {}
        meetings = conn.execute(
            """
            SELECT COALESCE(meeting_date, date(created_at)) as date, signals_json 
            FROM meeting_summaries 
            WHERE (meeting_date >= ? OR (meeting_date IS NULL AND created_at >= ?))
            AND signals_json IS NOT NULL
            """,
            (cutoff, cutoff)
        ).fetchall()
        
        for m in meetings:
            date = m["date"]
            if date:
                try:
                    signals = json.loads(m["signals_json"])
                    count = sum(len(signals.get(k, [])) for k in ["decisions", "action_items", "blockers", "risks", "ideas"])
                    daily_signals[date] = daily_signals.get(date, 0) + count
                except:
                    pass
        
        result = []
        for row in daily_time:
            result.append({
                "date": row["date"],
                "total_seconds": row["total_seconds"] or 0,
                "sessions": row["sessions"],
                "signals": daily_signals.get(row["date"], 0)
            })
        
        return JSONResponse({"daily": result})


# Sprint burndown cache to avoid recomputing on rapid mode changes
_sprint_burndown_cache = {"data": None, "timestamp": 0}
SPRINT_BURNDOWN_CACHE_TTL = 90  # Cache for 90 seconds (improved from 30)


@app.get("/api/reports/sprint-burndown")
async def get_sprint_burndown(force: bool = False):
    """Get sprint points breakdown with task decomposition progress."""
    import time
    
    # Check cache unless force refresh
    now = time.time()
    if not force and _sprint_burndown_cache["data"] and (now - _sprint_burndown_cache["timestamp"]) < SPRINT_BURNDOWN_CACHE_TTL:
        return JSONResponse(_sprint_burndown_cache["data"])
    
    with connect() as conn:
        # Get sprint settings for jeopardy calculation
        sprint_settings = conn.execute("SELECT * FROM sprint_settings WHERE id = 1").fetchone()
        working_days_remaining = None
        sprint_total_days = 14
        sprint_day = None
        
        if sprint_settings:
            from datetime import datetime, timedelta
            sprint_start = datetime.strptime(sprint_settings["sprint_start_date"], "%Y-%m-%d")
            sprint_total_days = sprint_settings["sprint_length_days"] or 14
            sprint_day = (datetime.now() - sprint_start).days + 1
            days_remaining = sprint_total_days - sprint_day
            # Estimate working days (exclude weekends roughly)
            working_days_remaining = max(0, int(days_remaining * 5 / 7))
        
        # Get all active tickets assigned to sprint (not done)
        tickets = conn.execute(
            """
            SELECT id, ticket_id, title, status, sprint_points, in_sprint, task_decomposition
            FROM tickets 
            WHERE status IN ('todo', 'in_progress', 'in_review', 'blocked')
            AND in_sprint = 1
            ORDER BY 
                CASE status
                    WHEN 'blocked' THEN 0
                    WHEN 'in_progress' THEN 1
                    WHEN 'in_review' THEN 2
                    WHEN 'todo' THEN 3
                END,
                sprint_points DESC
            """
        ).fetchall()
        
        total_points = 0
        completed_points = 0
        in_progress_points = 0
        remaining_points = 0
        
        ticket_breakdown = []
        
        for ticket in tickets:
            points = ticket["sprint_points"] or 0
            total_points += points
            
            # Parse task decomposition
            tasks = []
            total_tasks = 0
            completed_tasks = 0
            
            if ticket["task_decomposition"]:
                try:
                    parsed = json.loads(ticket["task_decomposition"])
                    if isinstance(parsed, list):
                        for idx, item in enumerate(parsed):
                            if isinstance(item, dict):
                                title = item.get("title") or item.get("text") or item.get("task") or item.get("name") or "Task"
                                description = item.get("description") or item.get("details") or ""
                                status = item.get("status", "pending")
                            else:
                                title = str(item)
                                description = ""
                                status = "pending"
                            
                            is_done = status in ("done", "completed")
                            total_tasks += 1
                            if is_done:
                                completed_tasks += 1
                            
                            tasks.append({
                                "index": idx,
                                "title": title,
                                "description": description,
                                "status": status,
                                "done": is_done
                            })
                except:
                    pass
            
            # Calculate progress percentage for this ticket
            progress_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Estimate points based on progress
            ticket_completed_points = (points * progress_pct / 100)
            ticket_remaining = points - ticket_completed_points
            
            if ticket["status"] == "in_progress":
                in_progress_points += ticket_remaining
            else:
                remaining_points += points
            
            completed_points += ticket_completed_points
            
            ticket_breakdown.append({
                "id": ticket["id"],
                "ticket_id": ticket["ticket_id"],
                "title": ticket["title"],
                "status": ticket["status"],
                "sprint_points": points,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "progress_pct": round(progress_pct, 1),
                "tasks": tasks
            })
        
        # Get completed tickets for total burndown context (in sprint only)
        completed_tickets = conn.execute(
            """
            SELECT SUM(COALESCE(sprint_points, 0)) as points
            FROM tickets 
            WHERE status IN ('done', 'complete')
            AND in_sprint = 1
            AND updated_at >= date('now', '-14 days')
            """
        ).fetchone()
        
        done_points = completed_tickets["points"] or 0
        
        # Count total remaining tasks
        total_remaining_tasks = sum(
            t["total_tasks"] - t["completed_tasks"] for t in ticket_breakdown
        )
        
        # Calculate jeopardy status
        jeopardy_status = None
        jeopardy_message = None
        
        if working_days_remaining is not None:
            remaining_points_value = remaining_points + in_progress_points
            # Assume ~2 tasks per working day as velocity
            estimated_capacity_tasks = working_days_remaining * 3  # 3 tasks per day rough estimate
            # Assume ~3 points per working day as velocity
            estimated_capacity_points = working_days_remaining * 3
            
            if remaining_points_value > estimated_capacity_points * 1.5:
                jeopardy_status = "critical"
                jeopardy_message = f"🚨 Sprint at risk: {remaining_points_value:.0f} points remaining with only {working_days_remaining} working days left"
            elif remaining_points_value > estimated_capacity_points:
                jeopardy_status = "warning"
                jeopardy_message = f"⚠️ Sprint may be at risk: {remaining_points_value:.0f} points remaining"
            elif total_remaining_tasks > estimated_capacity_tasks:
                jeopardy_status = "warning"
                jeopardy_message = f"⚠️ High task count: {total_remaining_tasks} subtasks remaining with {working_days_remaining} days left"
        
        result = {
            "total_points": total_points,
            "completed_points": round(completed_points, 1),
            "in_progress_points": round(in_progress_points, 1),
            "remaining_points": round(remaining_points, 1),
            "done_this_sprint": done_points,
            "total_remaining_tasks": total_remaining_tasks,
            "working_days_remaining": working_days_remaining,
            "sprint_day": sprint_day,
            "sprint_total_days": sprint_total_days,
            "jeopardy_status": jeopardy_status,
            "jeopardy_message": jeopardy_message,
            "tickets": ticket_breakdown
        }
        
        # Update cache
        _sprint_burndown_cache["data"] = result
        _sprint_burndown_cache["timestamp"] = now
        
        return JSONResponse(result)


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


@app.get("/api/reports/weekly-intelligence")
async def get_weekly_intelligence():
    """
    Weekly Intelligence Summary - High-value synthesis of the week's activity.
    
    Provides:
    - Meeting summary with key decisions
    - Top signals by category
    - DIKW pyramid activity
    - Ticket/sprint progress
    - Action items due soon
    - Career standups overview
    """
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    
    with connect() as conn:
        # =====================================================================
        # MEETINGS THIS WEEK
        # =====================================================================
        meetings = conn.execute(
            """
            SELECT id, meeting_name, meeting_date, signals_json, created_at
            FROM meeting_summaries 
            WHERE (meeting_date >= ? OR (meeting_date IS NULL AND created_at >= ?))
            ORDER BY COALESCE(meeting_date, created_at) DESC
            LIMIT 20
            """,
            (week_start, week_start)
        ).fetchall()
        
        meetings_data = []
        all_decisions = []
        all_actions = []
        all_blockers = []
        all_risks = []
        all_ideas = []
        
        for m in meetings:
            meeting_info = {
                "id": m["id"],
                "name": m["meeting_name"] or "Untitled Meeting",
                "date": m["meeting_date"] or m["created_at"][:10]
            }
            
            if m["signals_json"]:
                try:
                    signals = json.loads(m["signals_json"])
                    meeting_info["signal_count"] = sum(
                        len(signals.get(k, [])) 
                        for k in ["decisions", "action_items", "blockers", "risks", "ideas"]
                    )
                    
                    # Collect signals with meeting context
                    for d in signals.get("decisions", []):
                        all_decisions.append({"text": d, "meeting": meeting_info["name"], "meeting_id": m["id"]})
                    for a in signals.get("action_items", []):
                        all_actions.append({"text": a, "meeting": meeting_info["name"], "meeting_id": m["id"]})
                    for b in signals.get("blockers", []):
                        all_blockers.append({"text": b, "meeting": meeting_info["name"], "meeting_id": m["id"]})
                    for r in signals.get("risks", []):
                        all_risks.append({"text": r, "meeting": meeting_info["name"], "meeting_id": m["id"]})
                    for i in signals.get("ideas", []):
                        all_ideas.append({"text": i, "meeting": meeting_info["name"], "meeting_id": m["id"]})
                except:
                    meeting_info["signal_count"] = 0
            
            meetings_data.append(meeting_info)
        
        # =====================================================================
        # DIKW PYRAMID ACTIVITY (using dikw_items table)
        # =====================================================================
        dikw_items = conn.execute(
            """
            SELECT level, COUNT(*) as count,
                   SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) as new_this_week
            FROM dikw_items
            WHERE status = 'active'
            GROUP BY level
            ORDER BY 
                CASE level 
                    WHEN 'wisdom' THEN 1 
                    WHEN 'knowledge' THEN 2 
                    WHEN 'information' THEN 3 
                    WHEN 'data' THEN 4 
                END
            """,
            (week_start,)
        ).fetchall()
        
        dikw_summary = {
            row["level"]: {"total": row["count"], "new": row["new_this_week"] or 0}
            for row in dikw_items
        }
        
        # Recent wisdom/knowledge items (high value)
        high_value_dikw = conn.execute(
            """
            SELECT id, level, content, summary, tags
            FROM dikw_items
            WHERE level IN ('wisdom', 'knowledge') AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 5
            """
        ).fetchall()
        
        # =====================================================================
        # TICKET/SPRINT PROGRESS
        # =====================================================================
        ticket_stats = conn.execute(
            """
            SELECT 
                status,
                COUNT(*) as count,
                SUM(COALESCE(sprint_points, 0)) as points
            FROM tickets
            WHERE in_sprint = 1
            GROUP BY status
            """
        ).fetchall()
        
        sprint_overview = {
            "todo": {"count": 0, "points": 0},
            "in_progress": {"count": 0, "points": 0},
            "in_review": {"count": 0, "points": 0},
            "blocked": {"count": 0, "points": 0},
            "done": {"count": 0, "points": 0}
        }
        for row in ticket_stats:
            if row["status"] in sprint_overview:
                sprint_overview[row["status"]] = {
                    "count": row["count"],
                    "points": row["points"] or 0
                }
        
        # Blocked tickets need attention
        blocked_tickets = conn.execute(
            """
            SELECT id, ticket_id, title
            FROM tickets
            WHERE status = 'blocked' AND in_sprint = 1
            LIMIT 5
            """
        ).fetchall()
        
        # =====================================================================
        # ACTION ITEMS DUE SOON (from accountability_items table)
        # =====================================================================
        recent_actions = conn.execute(
            """
            SELECT id, description as content, source_ref_id as meeting_id, status, created_at
            FROM accountability_items
            WHERE status != 'complete'
            ORDER BY created_at DESC
            LIMIT 10
            """
        ).fetchall()
        
        # =====================================================================
        # CAREER STANDUPS (from standup_updates table)
        # =====================================================================
        standups = conn.execute(
            """
            SELECT id, standup_date, content, feedback, sentiment, key_themes, created_at
            FROM standup_updates
            WHERE standup_date >= ?
            ORDER BY standup_date DESC
            LIMIT 7
            """,
            (week_start,)
        ).fetchall()
        
        standups_data = [
            {
                "id": s["id"],
                "date": s["standup_date"],
                "content": s["content"][:100] + "..." if s["content"] and len(s["content"]) > 100 else s["content"],
                "sentiment": s["sentiment"],
                "key_themes": s["key_themes"],
                "has_feedback": bool(s["feedback"])
            }
            for s in standups
        ]
        
        # =====================================================================
        # TIME TRACKING SUMMARY
        # =====================================================================
        time_by_mode = conn.execute(
            """
            SELECT mode, SUM(duration_seconds) as total_seconds, COUNT(*) as sessions
            FROM mode_sessions
            WHERE date >= ? AND duration_seconds IS NOT NULL
            GROUP BY mode
            ORDER BY total_seconds DESC
            """,
            (week_start,)
        ).fetchall()
        
        time_summary = [
            {
                "mode": row["mode"],
                "total_hours": round(row["total_seconds"] / 3600, 1),
                "sessions": row["sessions"]
            }
            for row in time_by_mode
        ]
        
        # =====================================================================
        # BUILD RESPONSE
        # =====================================================================
        return JSONResponse({
            "period": {
                "start": week_start,
                "end": today
            },
            "meetings": {
                "count": len(meetings_data),
                "list": meetings_data[:10],
                "total_signals": len(all_decisions) + len(all_actions) + len(all_blockers) + len(all_risks) + len(all_ideas)
            },
            "signals": {
                "decisions": all_decisions[:5],
                "decisions_count": len(all_decisions),
                "action_items": all_actions[:5],
                "action_items_count": len(all_actions),
                "blockers": all_blockers[:5],
                "blockers_count": len(all_blockers),
                "risks": all_risks[:3],
                "risks_count": len(all_risks),
                "ideas": all_ideas[:3],
                "ideas_count": len(all_ideas)
            },
            "dikw": {
                "summary": dikw_summary,
                "high_value_items": [
                    {
                        "id": item["id"],
                        "level": item["level"],
                        "content": item["content"][:200] + "..." if len(item["content"] or "") > 200 else item["content"],
                        "summary": item["summary"],
                        "tags": item["tags"]
                    }
                    for item in high_value_dikw
                ]
            },
            "sprint": {
                "overview": sprint_overview,
                "blocked_tickets": [
                    {
                        "id": t["id"],
                        "ticket_id": t["ticket_id"],
                        "title": t["title"]
                    }
                    for t in blocked_tickets
                ]
            },
            "action_items_pending": [
                {
                    "id": a["id"],
                    "content": a["content"][:150] + "..." if len(a["content"] or "") > 150 else a["content"],
                    "meeting_id": a["meeting_id"],
                    "created": a["created_at"]
                }
                for a in recent_actions
            ],
            "standups": {
                "count": len(standups_data),
                "list": standups_data
            },
            "time_tracking": time_summary
        })


@app.post("/api/mode-timer/calculate-stats")
async def calculate_mode_statistics():
    """Calculate and store mode statistics for analytics."""
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    
    with connect() as conn:
        # Calculate daily stats
        for mode in ['grooming', 'planning', 'standup', 'implementation']:
            daily = conn.execute(
                """
                SELECT 
                    SUM(duration_seconds) as total,
                    COUNT(*) as count,
                    AVG(duration_seconds) as avg
                FROM mode_sessions
                WHERE mode = ? AND date = ? AND duration_seconds IS NOT NULL
                """,
                (mode, today)
            ).fetchone()
            
            if daily["total"]:
                conn.execute(
                    """INSERT INTO mode_statistics (mode, stat_type, period, total_seconds, session_count, avg_session_seconds)
                       VALUES (?, 'daily', ?, ?, ?, ?)
                       ON CONFLICT(mode, stat_type, period) DO UPDATE SET
                       total_seconds = ?, session_count = ?, avg_session_seconds = ?, calculated_at = CURRENT_TIMESTAMP""",
                    (mode, today, daily["total"], daily["count"], int(daily["avg"] or 0),
                     daily["total"], daily["count"], int(daily["avg"] or 0))
                )
            
            # Calculate weekly stats
            weekly = conn.execute(
                """
                SELECT 
                    SUM(duration_seconds) as total,
                    COUNT(*) as count,
                    AVG(duration_seconds) as avg
                FROM mode_sessions
                WHERE mode = ? AND date >= ? AND duration_seconds IS NOT NULL
                """,
                (mode, week_start)
            ).fetchone()
            
            if weekly["total"]:
                conn.execute(
                    """INSERT INTO mode_statistics (mode, stat_type, period, total_seconds, session_count, avg_session_seconds)
                       VALUES (?, 'weekly', ?, ?, ?, ?)
                       ON CONFLICT(mode, stat_type, period) DO UPDATE SET
                       total_seconds = ?, session_count = ?, avg_session_seconds = ?, calculated_at = CURRENT_TIMESTAMP""",
                    (mode, week_start, weekly["total"], weekly["count"], int(weekly["avg"] or 0),
                     weekly["total"], weekly["count"], int(weekly["avg"] or 0))
                )
        
        conn.commit()
    
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
    
    # Save status
    with connect() as conn:
        # Mark all previous statuses as not current
        conn.execute("UPDATE user_status SET is_current = 0")
        
        # Insert new status
        conn.execute("""
            INSERT INTO user_status (status_text, interpreted_mode, interpreted_activity, interpreted_context)
            VALUES (?, ?, ?, ?)
        """, (status_text, mode, activity, context_str))
        conn.commit()
    
    # Auto-start timer for the interpreted mode
    # First stop any active timers
    with connect() as conn:
        active = conn.execute(
            "SELECT mode FROM mode_sessions WHERE ended_at IS NULL"
        ).fetchall()
        
        for session in active:
            # Stop the active session
            ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                UPDATE mode_sessions 
                SET ended_at = ?, 
                    duration_seconds = CAST((julianday(?) - julianday(started_at)) * 86400 AS INTEGER)
                WHERE mode = ? AND ended_at IS NULL
            """, (ended_at, ended_at, session["mode"]))
        
        conn.commit()
    
    # Start new timer
    today = datetime.now().strftime("%Y-%m-%d")
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO mode_sessions (mode, started_at, date, notes) VALUES (?, ?, ?, ?)""",
            (mode, started_at, today, activity)
        )
        conn.commit()
    
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
    with connect() as conn:
        status = conn.execute(
            "SELECT * FROM user_status WHERE is_current = 1 ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    
    if not status:
        return JSONResponse({"status": None})
    
    return JSONResponse({
        "status": {
            "text": status["status_text"],
            "mode": status["interpreted_mode"],
            "activity": status["interpreted_activity"],
            "context": status["interpreted_context"],
            "created_at": status["created_at"]
        }
    })


# ============================================
# DIKW Pyramid API Endpoints
# Data → Information → Knowledge → Wisdom
# DIKWSynthesizerAgent integration (Checkpoint 2.5)
# ============================================

# DIKW_LEVELS now imported from agents/dikw_synthesizer.py as AGENT_DIKW_LEVELS
DIKW_LEVELS = AGENT_DIKW_LEVELS  # Re-export for backward compatibility
DIKW_NEXT_LEVEL = {'data': 'information', 'information': 'knowledge', 'knowledge': 'wisdom'}

@app.get("/api/dikw")
async def get_dikw_items(level: str = None, status: str = "active"):
    """Get DIKW items, optionally filtered by level."""
    with connect() as conn:
        if level:
            items = conn.execute(
                """SELECT d.*, m.meeting_name, m.meeting_date 
                   FROM dikw_items d 
                   LEFT JOIN meeting_summaries m ON d.meeting_id = m.id
                   WHERE d.level = ? AND d.status = ? 
                   ORDER BY d.created_at DESC""",
                (level, status)
            ).fetchall()
        else:
            items = conn.execute(
                """SELECT d.*, m.meeting_name, m.meeting_date 
                   FROM dikw_items d 
                   LEFT JOIN meeting_summaries m ON d.meeting_id = m.id
                   WHERE d.status = ? 
                   ORDER BY d.level, d.created_at DESC""",
                (status,)
            ).fetchall()
    
    # Group by level for pyramid view
    pyramid = {level: [] for level in DIKW_LEVELS}
    for item in items:
        item_dict = dict(item)
        # Normalize signal type
        if item_dict.get('original_signal_type'):
            item_dict['original_signal_type'] = normalize_signal_type(item_dict['original_signal_type'])
        pyramid[item['level']].append(item_dict)
    
    return JSONResponse({
        "pyramid": pyramid,
        "counts": {level: len(pyramid[level]) for level in DIKW_LEVELS}
    })


@app.post("/api/dikw/promote-signal")
async def promote_signal_to_dikw(request: Request):
    """
    Promote a signal to the DIKW pyramid (starts as Data level).
    
    Migration Note (P1.8): Uses DIKWSynthesizerAgent adapter for AI summary generation.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import ai_summarize_dikw_adapter, generate_dikw_tags
    
    data = await request.json()
    signal_text = data.get("signal_text", "")
    signal_type = data.get("signal_type", "")
    meeting_id = data.get("meeting_id")
    target_level = data.get("level", "data")  # Can promote directly to higher level
    
    if not signal_text:
        return JSONResponse({"error": "Signal text is required"}, status_code=400)
    
    # Use DIKWSynthesizerAgent adapter for AI summary generation
    try:
        summary = await ai_summarize_dikw_adapter(signal_text, target_level)
    except Exception:
        summary = signal_text[:200]
    
    # Auto-generate tags based on content and signal type
    tags = generate_dikw_tags(signal_text, target_level, signal_type)
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO dikw_items 
               (level, content, summary, source_type, original_signal_type, meeting_id, validation_count, tags)
               VALUES (?, ?, ?, 'signal', ?, ?, 1, ?)""",
            (target_level, signal_text, summary, signal_type, meeting_id, tags)
        )
        conn.commit()
        item_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        
        # Also update signal_status to mark as promoted
        conn.execute(
            """INSERT INTO signal_status (meeting_id, signal_type, signal_text, status, converted_to, converted_ref_id)
               VALUES (?, ?, ?, 'approved', 'dikw', ?)
               ON CONFLICT(meeting_id, signal_type, signal_text) 
               DO UPDATE SET status = 'approved', converted_to = 'dikw', converted_ref_id = ?, updated_at = CURRENT_TIMESTAMP""",
            (meeting_id, signal_type, signal_text, item_id, item_id)
        )
        conn.commit()
    
    return JSONResponse({"status": "ok", "id": item_id, "level": target_level, "tags": tags})


@app.post("/api/dikw/promote")
async def promote_dikw_item(request: Request):
    """
    Promote a DIKW item to the next level (with AI synthesis).
    
    Migration Note (P1.8): Uses DIKWSynthesizerAgent adapter for AI synthesis.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import ai_promote_dikw_adapter, generate_dikw_tags
    
    data = await request.json()
    item_id = data.get("item_id")
    to_level = data.get("to_level")  # Optional: force specific target level
    promoted_content = data.get("promoted_content")  # Optional: pre-generated content
    provided_summary = data.get("summary")  # Optional: pre-generated summary
    
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    with connect() as conn:
        item = conn.execute("SELECT * FROM dikw_items WHERE id = ?", (item_id,)).fetchone()
        
        if not item:
            return JSONResponse({"error": "Item not found"}, status_code=404)
        
        current_level = item['level']
        if current_level == 'wisdom' and not to_level:
            return JSONResponse({"error": "Already at highest level"}, status_code=400)
        
        # Use provided target level or default to next level
        next_level = to_level if to_level else DIKW_NEXT_LEVEL.get(current_level, 'wisdom')
        
        # Use provided content or keep original
        new_content = promoted_content if promoted_content else item['content']
        
        # Generate AI synthesis for summary if not provided
        if provided_summary:
            new_summary = provided_summary
        else:
            # Use DIKWSynthesizerAgent adapter for AI promotion
            try:
                result = await ai_promote_dikw_adapter(new_content, current_level, next_level)
                new_summary = result.get('summary', f"Promoted from {current_level}: {item['summary'] or ''}")
            except Exception:
                new_summary = f"Promoted from {current_level}: {item['summary'] or ''}"
        
        # Normalize confidence (handle both 0-1 and 0-100 ranges)
        current_confidence = item['confidence'] or 70
        if current_confidence <= 1:
            current_confidence = current_confidence * 100
        new_confidence = min(95, current_confidence + 5)  # Slight boost on promotion
        
        # Auto-generate tags for the promoted content
        existing_tags = item['tags'] or ''
        new_tags = generate_dikw_tags(new_content, next_level, existing_tags)
        
        # Create new item at higher level with the refined content
        conn.execute(
            """INSERT INTO dikw_items 
               (level, content, summary, source_type, source_ref_ids, original_signal_type, meeting_id, confidence, validation_count, tags)
               VALUES (?, ?, ?, 'synthesis', ?, ?, ?, ?, ?, ?)""",
            (next_level, new_content, new_summary, json.dumps([item_id]), 
             item['original_signal_type'], item['meeting_id'],
             new_confidence, (item['validation_count'] or 0) + 1, new_tags)
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        
        # Record evolution history for the promotion
        conn.execute("""
            INSERT INTO dikw_evolution 
            (item_id, event_type, from_level, to_level, source_item_ids, content_snapshot, created_at)
            VALUES (?, 'promoted', ?, ?, ?, ?, datetime('now'))
        """, (
            new_id,
            current_level,
            next_level,
            json.dumps([item_id]),
            item['content']  # Snapshot of original content
        ))
        
        # Update original item to show it was promoted
        conn.execute(
            """UPDATE dikw_items SET promoted_to = ?, promoted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (new_id, item_id)
        )
        conn.commit()
    
    return JSONResponse({
        "status": "ok", 
        "new_id": new_id, 
        "from_level": current_level, 
        "to_level": next_level,
        "content": new_content,
        "summary": new_summary,
        "tags": new_tags
    })


@app.post("/api/dikw/merge")
async def merge_dikw_items(request: Request):
    """
    Merge multiple items at the same level into a synthesized higher-level item.
    
    Migration Note (P1.8): Uses DIKWSynthesizerAgent adapter for merge synthesis.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import merge_dikw_items_adapter
    
    data = await request.json()
    item_ids = data.get("item_ids", [])
    
    if len(item_ids) < 2:
        return JSONResponse({"error": "Need at least 2 items to merge"}, status_code=400)
    
    with connect() as conn:
        items = conn.execute(
            f"SELECT * FROM dikw_items WHERE id IN ({','.join('?' * len(item_ids))})",
            item_ids
        ).fetchall()
        
        if len(items) < 2:
            return JSONResponse({"error": "Items not found"}, status_code=404)
        
        # All items must be at same level
        levels = set(item['level'] for item in items)
        if len(levels) > 1:
            return JSONResponse({"error": "All items must be at the same level"}, status_code=400)
        
        current_level = items[0]['level']
        if current_level == 'wisdom':
            # Merge wisdom items into a mega-wisdom
            next_level = 'wisdom'
        else:
            next_level = DIKW_NEXT_LEVEL[current_level]
        
        # Combine content for AI synthesis
        combined_content = "\n\n".join([f"- {item['content']}" for item in items])
        
        # Use DIKWSynthesizerAgent adapter for merge synthesis
        try:
            items_for_adapter = [dict(item) for item in items]
            result = await merge_dikw_items_adapter(items_for_adapter)
            merged_summary = result.get('merged_content', '') or result.get('summary', '')
            if not merged_summary:
                merged_summary = f"Merged {len(items)} items: " + "; ".join([i['summary'][:50] for i in items if i['summary']])
        except Exception:
            merged_summary = f"Merged {len(items)} items: " + "; ".join([i['summary'][:50] for i in items if i['summary']])
        
        # Create merged item
        avg_confidence = sum(item['confidence'] or 0.5 for item in items) / len(items)
        total_validations = sum(item['validation_count'] or 0 for item in items)
        
        conn.execute(
            """INSERT INTO dikw_items 
               (level, content, summary, source_type, source_ref_ids, confidence, validation_count)
               VALUES (?, ?, ?, 'synthesis', ?, ?, ?)""",
            (next_level, combined_content, merged_summary, json.dumps(item_ids),
             min(1.0, avg_confidence + 0.15), total_validations)
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        
        # Mark source items as merged
        for item_id in item_ids:
            conn.execute(
                """UPDATE dikw_items SET status = 'merged', promoted_to = ?, promoted_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (new_id, item_id)
            )
        conn.commit()
    
    return JSONResponse({
        "status": "ok",
        "new_id": new_id,
        "merged_count": len(items),
        "to_level": next_level,
        "summary": merged_summary
    })


@app.post("/api/dikw/validate")
async def validate_dikw_item(request: Request):
    """Validate/upvote a DIKW item (increases confidence)."""
    data = await request.json()
    item_id = data.get("item_id")
    action = data.get("action", "validate")  # 'validate' | 'invalidate' | 'archive'
    
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    with connect() as conn:
        if action == "validate":
            conn.execute(
                """UPDATE dikw_items 
                   SET validation_count = validation_count + 1,
                       confidence = MIN(1.0, confidence + 0.1),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (item_id,)
            )
        elif action == "invalidate":
            conn.execute(
                """UPDATE dikw_items 
                   SET validation_count = MAX(0, validation_count - 1),
                       confidence = MAX(0.0, confidence - 0.1),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (item_id,)
            )
        elif action == "archive":
            conn.execute(
                """UPDATE dikw_items SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (item_id,)
            )
        conn.commit()
    
    return JSONResponse({"status": "ok", "action": action})


# generate_dikw_tags is now imported from agents/dikw_synthesizer.py (Checkpoint 2.5)
# The imported version handles both sync and async contexts


@app.post("/api/dikw/generate-tags")
async def generate_tags_endpoint(request: Request):
    """Generate tags for DIKW content."""
    data = await request.json()
    content = data.get("content", "")
    level = data.get("level", "data")
    existing_tags = data.get("existing_tags", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    tags = generate_dikw_tags(content, level, existing_tags)
    return JSONResponse({"status": "ok", "tags": tags})


@app.post("/api/dikw")
async def create_dikw_item(request: Request):
    """Create a new DIKW item."""
    data = await request.json()
    level = data.get("level", "data")
    content = data.get("content", "").strip()
    summary = data.get("summary", "").strip()
    tags = data.get("tags", "")
    auto_tags = data.get("auto_tags", True)  # Auto-generate tags by default
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    # Auto-generate tags if not provided and auto_tags is enabled
    if auto_tags and not tags:
        tags = generate_dikw_tags(content, level)
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO dikw_items (level, content, summary, tags, source_type)
               VALUES (?, ?, ?, ?, 'manual')""",
            (level, content, summary or None, tags or None)
        )
        conn.commit()
        item_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    
    return JSONResponse({"status": "ok", "id": item_id, "tags": tags})


@app.put("/api/dikw/{item_id}")
async def update_dikw_item(item_id: int, request: Request):
    """Update an existing DIKW item."""
    data = await request.json()
    
    with connect() as conn:
        # Get current item to preserve unchanged fields
        current = conn.execute("SELECT * FROM dikw_items WHERE id = ?", (item_id,)).fetchone()
        if not current:
            return JSONResponse({"error": "Item not found"}, status_code=404)
        
        # Extract fields with fallback to existing values
        level = data.get("level", current['level'])
        content = data.get("content", current['content'])
        summary = data.get("summary", current['summary'])
        tags = data.get("tags", current['tags'])
        confidence = data.get("confidence")
        
        # Check if content or level changed to record evolution
        content_changed = content != current['content']
        level_changed = level != current['level']
        
        # Record evolution history if significant changes
        if content_changed or level_changed:
            # Snapshot the old state before updating
            conn.execute("""
                INSERT INTO dikw_evolution 
                (item_id, event_type, from_level, to_level, content_snapshot, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (
                item_id,
                'edited' if not level_changed else 'promoted',
                current['level'],
                level,
                current['content']  # Snapshot of OLD content before change
            ))
        
        # Handle confidence update (support both 0-1 and 0-100 ranges)
        if confidence is not None:
            if confidence <= 1:
                confidence = confidence * 100
            conn.execute(
                """UPDATE dikw_items 
                   SET level = ?, content = ?, summary = ?, tags = ?, confidence = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (level, content, summary, tags, confidence, item_id)
            )
        else:
            conn.execute(
                """UPDATE dikw_items 
                   SET level = ?, content = ?, summary = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (level, content, summary, tags, item_id)
            )
        conn.commit()
    
    return JSONResponse({"status": "ok"})


@app.delete("/api/dikw/{item_id}")
async def delete_dikw_item(item_id: int):
    """Delete a DIKW item."""
    with connect() as conn:
        item = conn.execute("SELECT * FROM dikw_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return JSONResponse({"error": "Item not found"}, status_code=404)
        
        conn.execute("DELETE FROM dikw_items WHERE id = ?", (item_id,))
        conn.commit()
    
    return JSONResponse({"status": "ok"})


@app.post("/api/dikw/ai-review")
async def ai_review_dikw(request: Request):
    """AI review and update existing DIKW item names/summaries."""
    data = await request.json()
    pyramid = data.get("pyramid", {})
    
    reviews = []
    
    # Collect all items for context-aware review
    all_items = []
    for level in ['data', 'information', 'knowledge', 'wisdom']:
        for item in pyramid.get(level, []):
            all_items.append({
                "id": item.get("id"),
                "level": level,
                "content": item.get("content", ""),
                "summary": item.get("summary", ""),
            })
    
    if not all_items:
        return JSONResponse({"status": "ok", "reviews": []})
    
    # Use DIKWSynthesizerAgent for AI review
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import get_dikw_synthesizer
    
    try:
        agent = get_dikw_synthesizer()
        result = await agent.run(
            action='ai_review',
            data={'items': all_items[:20]}
        )
        reviews = result.get('reviews', [])[:10]
    except Exception as e:
        print(f"Error in AI review: {e}")
        import traceback
        traceback.print_exc()
    
    return JSONResponse({"status": "ok", "reviews": reviews})


@app.post("/api/dikw/ai-refine")
async def ai_refine_dikw(request: Request):
    """
    Use AI to refine/improve DIKW content.
    
    Migration Note (P1.8): Uses DIKWSynthesizerAgent for content refinement.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import get_dikw_synthesizer
    
    data = await request.json()
    content = data.get("content", "")
    action = data.get("action", "clarify")
    custom_prompt = data.get("prompt")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    try:
        agent = get_dikw_synthesizer()
        result = await agent.run(
            action='refine',
            data={
                'content': content,
                'action': action,
                'custom_prompt': custom_prompt
            }
        )
        refined = result.get('refined_content', content)
        return JSONResponse({"status": "ok", "refined": refined})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dikw/ai-summarize")
async def ai_summarize_dikw(request: Request):
    """
    Generate AI summary for DIKW content.
    
    Migration Note (P1.8): Uses DIKWSynthesizerAgent adapter for summarization.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import ai_summarize_dikw_adapter
    
    data = await request.json()
    content = data.get("content", "")
    level = data.get("level", "data")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    try:
        summary = await ai_summarize_dikw_adapter(content, level)
        return JSONResponse({"status": "ok", "summary": summary})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dikw/ai-promote")
async def ai_promote_dikw(request: Request):
    """
    Use AI to promote content to the next DIKW level.
    
    Migration Note (P1.8): Uses DIKWSynthesizerAgent adapter for AI promotion.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import ai_promote_dikw_adapter
    
    data = await request.json()
    content = data.get("content", "")
    from_level = data.get("from_level", "data")
    to_level = data.get("to_level", "information")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    try:
        result = await ai_promote_dikw_adapter(content, from_level, to_level)
        
        return JSONResponse({
            "status": "ok",
            "promoted_content": result.get('promoted_content', ''),
            "summary": result.get('summary', ''),
            "from_level": from_level,
            "to_level": to_level
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# -------------------------
# Mindmap API Endpoints
# -------------------------

# In-memory store for mindmap data (can be persisted to DB later)
_mindmap_cache = {
    "last_generated": None,
    "last_item_count": 0,
    "data": None
}


@app.get("/api/mindmap/data")
async def get_mindmap_data():
    """Get mindmap data for visualization.
    
    Returns both DIKW pyramid structure and hierarchical mindmaps from conversations.
    """
    with connect() as conn:
        items = conn.execute(
            """SELECT * FROM dikw_items WHERE status = 'active' 
               ORDER BY level, created_at DESC"""
        ).fetchall()
        
        # Get hierarchical mindmaps from conversations
        mindmaps = conn.execute(
            """SELECT id, conversation_id, mindmap_json, hierarchy_levels, 
                      node_count, root_node_id FROM conversation_mindmaps
               ORDER BY updated_at DESC LIMIT 5"""
        ).fetchall()
    
    # Build DIKW tree structure for mindmap
    tree = {
        "name": "Knowledge",
        "type": "root",
        "children": []
    }
    
    # Group by level
    levels = {level: [] for level in DIKW_LEVELS}
    for item in items:
        levels[item['level']].append(dict(item))
    
    # Build hierarchical tree structure
    for level in ['data', 'information', 'knowledge', 'wisdom']:
        level_node = {
            "name": level.capitalize(),
            "type": "level",
            "level": level,
            "children": []
        }
        for item in levels[level][:20]:  # Limit per level
            level_node["children"].append({
                "id": item['id'],
                "name": (item['content'] or '')[:40] + ('...' if len(item.get('content', '')) > 40 else ''),
                "type": "item",
                "level": level,
                "summary": item.get('summary', ''),
                "tags": item.get('tags', '')
            })
        tree["children"].append(level_node)
    
    # Build flat nodes and links for force graph
    nodes = [{"id": "root", "name": "Knowledge", "type": "root", "level": "root"}]
    links = []
    
    for level in ['data', 'information', 'knowledge', 'wisdom']:
        level_id = f"level_{level}"
        nodes.append({"id": level_id, "name": level.capitalize(), "type": "level", "level": level})
        links.append({"source": "root", "target": level_id})
        
        for item in levels[level][:15]:
            item_id = f"item_{item['id']}"
            nodes.append({
                "id": item_id,
                "name": (item['content'] or '')[:30] + ('...' if len(item['content'] or '') > 30 else ''),
                "type": "item",
                "level": level,
                "summary": item['summary'] if 'summary' in item.keys() else ''
            })
            links.append({"source": level_id, "target": item_id})
    
    # Add hierarchical mindmap nodes
    hierarchical_mindmaps = []
    for mindmap in mindmaps:
        try:
            mindmap_json = json.loads(mindmap['mindmap_json'])
            hierarchical_mindmaps.append({
                "id": mindmap['id'],
                "conversation_id": mindmap['conversation_id'],
                "hierarchy_levels": mindmap['hierarchy_levels'],
                "node_count": mindmap['node_count'],
                "root_node_id": mindmap['root_node_id'],
                "nodes": mindmap_json.get('nodes', []),
                "edges": mindmap_json.get('edges', [])
            })
        except Exception as e:
            logger.warning(f"Error processing mindmap {mindmap['id']}: {e}")
    
    # Build tag clusters (normalize to lowercase for consistency)
    tag_clusters = {}
    for item in items:
        tags = (item['tags'] or '').split(',') if item['tags'] else []
        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                if tag not in tag_clusters:
                    tag_clusters[tag] = []
                tag_clusters[tag].append({
                    "id": item['id'],
                    "level": item['level'],
                    "content": (item['content'] or '')[:50]
                })
    
    # Count stats
    counts = {
        "data": len(levels['data']),
        "information": len(levels['information']),
        "knowledge": len(levels['knowledge']),
        "wisdom": len(levels['wisdom']),
        "tags": len(tag_clusters),
        "connections": len(links),
        "hierarchical_mindmaps": len(hierarchical_mindmaps),
        "total_mindmap_nodes": sum(m.get('node_count', 0) for m in hierarchical_mindmaps)
    }
    
    return JSONResponse({
        "tree": tree,
        "nodes": nodes,
        "links": links,
        "tagClusters": tag_clusters,
        "hierarchicalMindmaps": hierarchical_mindmaps,
        "counts": counts
    })


@app.get("/api/mindmap/data-hierarchical")
async def get_mindmap_data_hierarchical():
    """Get all hierarchical mindmaps with full hierarchy information.
    
    Returns:
        - All conversation mindmaps with preserved parent-child relationships
        - Hierarchy depth levels for each node
        - Node metadata and conversation context
    """
    from .services.mindmap_synthesis import MindmapSynthesizer
    
    with connect() as conn:
        mindmaps = conn.execute(
            """SELECT id, conversation_id, mindmap_json, hierarchy_levels,
                      node_count, root_node_id, created_at, updated_at
               FROM conversation_mindmaps
               ORDER BY updated_at DESC"""
        ).fetchall()
    
    hierarchical_data = []
    for mindmap in mindmaps:
        try:
            mindmap_json = json.loads(mindmap['mindmap_json'])
            hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_json)
            
            # Add metadata to each node
            enhanced_nodes = []
            for node in mindmap_json.get('nodes', []):
                enhanced_node = dict(node)
                enhanced_node['conversation_id'] = mindmap['conversation_id']
                enhanced_node['mindmap_id'] = mindmap['id']
                enhanced_node['level'] = node.get('level', 0)
                enhanced_node['depth'] = hierarchy['nodes_by_level'].get(node.get('level', 0), []).index(node) if node in hierarchy['nodes_by_level'].get(node.get('level', 0), []) else 0
                enhanced_nodes.append(enhanced_node)
            
            hierarchical_data.append({
                "id": mindmap['id'],
                "conversation_id": mindmap['conversation_id'],
                "nodes": enhanced_nodes,
                "edges": mindmap_json.get('edges', []),
                "hierarchy": {
                    "levels": hierarchy.get('levels'),
                    "max_depth": hierarchy.get('max_depth'),
                    "root_node_id": mindmap['root_node_id'],
                    "node_count": mindmap['node_count'],
                    "nodes_by_level": {
                        str(level): [n.get('id') for n in nodes]
                        for level, nodes in hierarchy.get('nodes_by_level', {}).items()
                    }
                },
                "created_at": mindmap['created_at'],
                "updated_at": mindmap['updated_at']
            })
        except Exception as e:
            logger.error(f"Error processing hierarchical mindmap {mindmap['id']}: {e}")
    
    return JSONResponse({
        "mindmaps": hierarchical_data,
        "total": len(hierarchical_data),
        "summary": {
            "total_mindmaps": len(hierarchical_data),
            "total_nodes": sum(len(m.get('nodes', [])) for m in hierarchical_data),
            "total_edges": sum(len(m.get('edges', [])) for m in hierarchical_data)
        }
    })


@app.get("/api/mindmap/nodes-by-level/{level}")
async def get_mindmap_nodes_by_level(level: int):
    """Get all mindmap nodes at a specific hierarchy level.
    
    Args:
        level: Hierarchy level (0 = root, 1 = first level, etc.)
        
    Returns:
        All nodes at that level across all mindmaps with context
    """
    from .services.mindmap_synthesis import MindmapSynthesizer
    
    nodes_at_level = MindmapSynthesizer.get_mindmap_by_hierarchy_level(level)
    
    return JSONResponse({
        "level": level,
        "nodes": nodes_at_level,
        "count": len(nodes_at_level)
    })


@app.get("/api/mindmap/conversations")
async def get_aggregated_conversation_mindmaps():
    """Get all mindmaps aggregated from conversations.
    
    Returns conversation mindmaps grouped by conversation with
    aggregated statistics and hierarchy information.
    """
    from .services.mindmap_synthesis import MindmapSynthesizer
    
    with connect() as conn:
        # Get conversations with their mindmaps
        result = conn.execute("""
            SELECT c.id as conversation_id, c.title, c.created_at,
                   GROUP_CONCAT(cm.id) as mindmap_ids,
                   COUNT(cm.id) as mindmap_count
            FROM conversations c
            LEFT JOIN conversation_mindmaps cm ON c.id = cm.conversation_id
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """).fetchall()
    
    conversation_data = []
    for conv in result:
        if conv['mindmap_ids']:
            # Get hierarchy summary for each conversation
            summary = MindmapSynthesizer.get_hierarchy_summary()
            conversation_data.append({
                "conversation_id": conv['conversation_id'],
                "title": conv['title'],
                "created_at": conv['created_at'],
                "mindmap_count": conv['mindmap_count'],
                "mindmap_ids": [int(m) for m in conv['mindmap_ids'].split(',')],
                "statistics": {
                    "total_nodes": summary.get('total_nodes', 0),
                    "avg_depth": summary.get('avg_depth', 0),
                    "levels_distribution": summary.get('levels_distribution', {})
                }
            })
    
    return JSONResponse({
        "conversations": conversation_data,
        "total_conversations": len(conversation_data),
        "summary": MindmapSynthesizer.get_hierarchy_summary()
    })


@app.post("/api/mindmap/synthesize")
async def synthesize_mindmaps(request: Request):
    """Generate AI synthesis of all conversation mindmaps.
    
    Creates or updates the master synthesis that aggregates all mindmap data
    across conversations into a unified knowledge structure.
    
    Query params:
        - force: bool - Force regeneration even if recent synthesis exists
        
    Returns:
        {
            "synthesis_id": int,
            "synthesis_text": str,
            "source_mindmaps": int,
            "source_conversations": int,
            "key_topics": [...],
            "hierarchies_analyzed": int,
            "total_nodes_synthesized": int
        }
    """
    from .services.mindmap_synthesis import MindmapSynthesizer
    
    try:
        # Get optional force parameter
        force = request.query_params.get("force", "false").lower() == "true"
        
        # Generate synthesis
        synthesis_id = MindmapSynthesizer.generate_synthesis(force=force)
        
        if not synthesis_id:
            return JSONResponse({
                "error": "Failed to generate synthesis - no mindmaps found or synthesis generation failed",
                "synthesis_id": None
            }, status_code=400)
        
        # Get the generated synthesis
        synthesis = MindmapSynthesizer.get_current_synthesis()
        
        if synthesis:
            source_mindmap_ids = json.loads(synthesis.get('source_mindmap_ids', '[]'))
            source_conv_ids = json.loads(synthesis.get('source_conversation_ids', '[]'))
            key_topics = json.loads(synthesis.get('key_topics', '[]'))
            
            return JSONResponse({
                "success": True,
                "synthesis_id": synthesis['id'],
                "synthesis_text": synthesis['synthesis_text'][:500] + "..." if len(synthesis['synthesis_text']) > 500 else synthesis['synthesis_text'],
                "source_mindmaps": len(source_mindmap_ids),
                "source_conversations": len(set(source_conv_ids)),
                "key_topics": key_topics[:20],
                "created_at": synthesis['created_at'],
                "updated_at": synthesis['updated_at']
            })
        else:
            return JSONResponse({
                "error": "Synthesis generated but could not be retrieved",
                "synthesis_id": synthesis_id
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"Error synthesizing mindmaps: {e}")
        return JSONResponse({
            "error": f"Error during synthesis: {str(e)}",
            "synthesis_id": None
        }, status_code=500)


@app.get("/api/mindmap/synthesis")
async def get_mindmap_synthesis(type: str = None):
    """Get the current mindmap synthesis.
    
    Args:
        type: Synthesis type (default, executive, technical, timeline, action_focus)
    
    Returns the most recent AI-generated synthesis of all conversation mindmaps.
    """
    from .services.mindmap_synthesis import MindmapSynthesizer
    
    if type:
        synthesis = MindmapSynthesizer.get_synthesis_by_type(type)
    else:
        synthesis = MindmapSynthesizer.get_current_synthesis()
    
    if synthesis:
        return JSONResponse({
            "success": True,
            "synthesis": synthesis
        })
    else:
        return JSONResponse({
            "success": False,
            "message": "No synthesis available - run /api/mindmap/synthesize to generate one"
        }, status_code=404)


@app.post("/api/mindmap/synthesize-all")
async def generate_all_syntheses(force: str = "false"):
    """Generate all synthesis types (executive, technical, timeline, action_focus).
    
    This creates multiple views of the knowledge structure for different audiences.
    """
    from .services.mindmap_synthesis import MindmapSynthesizer
    
    try:
        force_regen = force.lower() == "true"
        results = MindmapSynthesizer.generate_multiple_syntheses(force=force_regen)
        
        return JSONResponse({
            "success": True,
            "message": f"Generated {len([r for r in results.values() if r])} synthesis views",
            "syntheses": results
        })
    except Exception as e:
        logger.error(f"Error generating multiple syntheses: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/mindmap/generate")
async def generate_mindmap(request: Request):
    """Generate or update mindmap data."""
    data = await request.json()
    full_regenerate = data.get("full", True)
    
    with connect() as conn:
        items = conn.execute(
            """SELECT * FROM dikw_items WHERE status = 'active' 
               ORDER BY created_at DESC"""
        ).fetchall()
    
    new_items_count = 0
    
    if not full_regenerate:
        # Only count items newer than last generation
        if _mindmap_cache.get("last_generated"):
            new_items_count = len([i for i in items if i not in _mindmap_cache.get("processed_ids", [])])
        else:
            new_items_count = len(items)
    else:
        new_items_count = len(items)
    
    # Update cache
    _mindmap_cache["last_generated"] = datetime.now().isoformat()
    _mindmap_cache["last_item_count"] = len(items)
    _mindmap_cache["processed_ids"] = [i['id'] for i in items]
    
    return JSONResponse({
        "status": "ok",
        "new_items": new_items_count,
        "total_items": len(items),
        "last_generated": _mindmap_cache["last_generated"]
    })


@app.get("/api/mindmap/tags")
async def get_mindmap_tags():
    """Get tag cloud data for mindmap."""
    with connect() as conn:
        items = conn.execute(
            """SELECT tags FROM dikw_items WHERE status = 'active' AND tags IS NOT NULL AND tags != ''"""
        ).fetchall()
    
    tag_counts = {}
    for item in items:
        tags = (item['tags'] or '').split(',')
        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Sort by count descending
    sorted_tags = sorted(
        [{"name": tag, "count": count} for tag, count in tag_counts.items()],
        key=lambda x: x['count'],
        reverse=True
    )
    
    return JSONResponse(sorted_tags)


@app.get("/api/mindmap/status")
async def get_mindmap_status():
    """Get mindmap generation status."""
    return JSONResponse({
        "last_generated": _mindmap_cache.get("last_generated"),
        "last_item_count": _mindmap_cache.get("last_item_count", 0)
    })


@app.post("/api/dikw/backfill-tags")
async def backfill_dikw_tags():
    """Backfill tags for existing DIKW items that don't have tags."""
    with connect() as conn:
        items = conn.execute(
            """SELECT id, content, level, tags FROM dikw_items 
               WHERE status = 'active' AND (tags IS NULL OR tags = '')"""
        ).fetchall()
    
    updated_count = 0
    errors = []
    
    for item in items:
        try:
            tags = generate_dikw_tags(item['content'] or '', item['level'], '')
            if tags:
                with connect() as conn:
                    conn.execute(
                        "UPDATE dikw_items SET tags = ? WHERE id = ?",
                        (tags, item['id'])
                    )
                    conn.commit()
                updated_count += 1
        except Exception as e:
            errors.append({"id": item['id'], "error": str(e)})
    
    return JSONResponse({
        "status": "ok",
        "total_without_tags": len(items),
        "updated": updated_count,
        "errors": errors[:5]  # Limit error reports
    })


# Signal type normalization map
SIGNAL_TYPE_NORMALIZE = {
    'action': 'action_item',
    'action_items': 'action_item',
    'actions': 'action_item',
    'decisions': 'decision',
    'blockers': 'blocker',
    'risks': 'risk',
    'ideas': 'idea',
    'insights': 'insight',
}


def normalize_signal_type(signal_type: str) -> str:
    """Normalize signal type to consistent format."""
    if not signal_type:
        return ''
    normalized = signal_type.lower().strip()
    return SIGNAL_TYPE_NORMALIZE.get(normalized, normalized)


@app.post("/api/dikw/compress-dedupe")
async def compress_and_dedupe_dikw():
    """Compress similar items and remove duplicates using AI analysis."""
    with connect() as conn:
        items = conn.execute(
            """SELECT id, level, content, summary, original_signal_type, tags, confidence
               FROM dikw_items WHERE status = 'active' 
               ORDER BY level, created_at DESC"""
        ).fetchall()
    
    if len(items) < 2:
        return JSONResponse({"status": "ok", "message": "Not enough items to compress", "merged": 0, "normalized": 0})
    
    # Normalize signal types first
    normalized_count = 0
    with connect() as conn:
        for item in items:
            if item['original_signal_type']:
                normalized = normalize_signal_type(item['original_signal_type'])
                if normalized != item['original_signal_type']:
                    conn.execute(
                        "UPDATE dikw_items SET original_signal_type = ? WHERE id = ?",
                        (normalized, item['id'])
                    )
                    normalized_count += 1
        conn.commit()
    
    # Group items by level for duplicate detection
    levels = {}
    for item in items:
        if item['level'] not in levels:
            levels[item['level']] = []
        levels[item['level']].append(dict(item))
    
    # Use DIKWSynthesizerAgent adapter to find duplicates
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import find_duplicates_adapter
    
    duplicates = []
    for level, level_items in levels.items():
        if len(level_items) < 2:
            continue
        
        try:
            groups = await find_duplicates_adapter(level_items, level)
            for group in groups:
                if len(group) >= 2:
                    duplicates.append({
                        "level": level,
                        "ids": group,
                        "items": [i for i in level_items if i['id'] in group]
                    })
        except Exception as e:
            print(f"Error finding duplicates in {level}: {e}")
    
    # Merge duplicates - keep the one with highest confidence, merge content
    merged_count = 0
    for dup_group in duplicates[:10]:  # Limit merges per run
        ids = dup_group['ids']
        items_to_merge = dup_group['items']
        
        # Find the best item (highest confidence) to keep
        best_item = max(items_to_merge, key=lambda x: x.get('confidence', 0) or 0)
        other_ids = [i['id'] for i in items_to_merge if i['id'] != best_item['id']]
        
        if not other_ids:
            continue
        
        # Merge tags
        all_tags = set()
        for item in items_to_merge:
            if item.get('tags'):
                all_tags.update(t.strip() for t in item['tags'].split(',') if t.strip())
        merged_tags = ','.join(sorted(all_tags)[:10])
        
        # Archive the duplicate items
        with connect() as conn:
            conn.execute(
                f"UPDATE dikw_items SET status = 'merged', updated_at = CURRENT_TIMESTAMP WHERE id IN ({','.join('?' * len(other_ids))})",
                other_ids
            )
            # Update the kept item with merged tags
            conn.execute(
                "UPDATE dikw_items SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (merged_tags, best_item['id'])
            )
            conn.commit()
        merged_count += len(other_ids)
    
    return JSONResponse({
        "status": "ok",
        "normalized": normalized_count,
        "duplicate_groups_found": len(duplicates),
        "merged": merged_count,
        "message": f"Normalized {normalized_count} signal types, found {len(duplicates)} duplicate groups, merged {merged_count} items"
    })


@app.get("/api/dikw/{item_id}/history")
async def get_dikw_item_history(item_id: int):
    """Get the evolution history of a DIKW item."""
    with connect() as conn:
        # Get the item itself
        item = conn.execute("SELECT * FROM dikw_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return JSONResponse({"error": "Item not found"}, status_code=404)
        
        # Get evolution history
        history = conn.execute(
            """SELECT * FROM dikw_evolution WHERE item_id = ? ORDER BY created_at ASC""",
            (item_id,)
        ).fetchall()
        
        # Get source meeting info if available
        meeting_info = None
        if item['meeting_id']:
            meeting = conn.execute(
                "SELECT id, meeting_name, meeting_date FROM meetings WHERE id = ?",
                (item['meeting_id'],)
            ).fetchone()
            if meeting:
                meeting_info = dict(meeting)
        
        # Get source items if this was promoted/merged
        source_items = []
        if item['source_ref_ids']:
            try:
                source_ids = json.loads(item['source_ref_ids'])
                if source_ids:
                    sources = conn.execute(
                        f"SELECT id, level, content, created_at FROM dikw_items WHERE id IN ({','.join('?' * len(source_ids))})",
                        source_ids
                    ).fetchall()
                    source_items = [dict(s) for s in sources]
            except:
                pass
        
        # Build evolution timeline
        timeline = []
        
        # Add creation event
        timeline.append({
            "event": "created",
            "level": item['level'] if not source_items else (source_items[0]['level'] if source_items else 'data'),
            "date": item['created_at'],
            "source": meeting_info['meeting_name'] if meeting_info else item['source_type'],
            "source_date": meeting_info['meeting_date'] if meeting_info else None,
            "content_snapshot": None  # No prior content for creation
        })
        
        # Add history events with content snapshots
        for h in history:
            timeline.append({
                "event": h['event_type'],
                "from_level": h['from_level'],
                "to_level": h['to_level'],
                "date": h['created_at'],
                "source": h['source_meeting_name'] or h['source_document_name'],
                "content_snapshot": h['content_snapshot']  # Old content before change
            })
        
        # If promoted, add that event
        if item['promoted_to']:
            timeline.append({
                "event": "promoted",
                "to_level": "next",
                "date": item['promoted_at']
            })
        
        return JSONResponse({
            "item": dict(item),
            "meeting": meeting_info,
            "source_items": source_items,
            "timeline": timeline
        })


@app.post("/api/dikw/normalize-categories")
async def normalize_dikw_categories():
    """Normalize all signal type categories to consistent format."""
    with connect() as conn:
        items = conn.execute(
            """SELECT id, original_signal_type FROM dikw_items 
               WHERE original_signal_type IS NOT NULL AND original_signal_type != ''"""
        ).fetchall()
    
    updated = 0
    changes = []
    
    with connect() as conn:
        for item in items:
            normalized = normalize_signal_type(item['original_signal_type'])
            if normalized != item['original_signal_type']:
                conn.execute(
                    "UPDATE dikw_items SET original_signal_type = ? WHERE id = ?",
                    (normalized, item['id'])
                )
                changes.append({
                    "id": item['id'],
                    "from": item['original_signal_type'],
                    "to": normalized
                })
                updated += 1
        conn.commit()
    
    return JSONResponse({
        "status": "ok",
        "total_checked": len(items),
        "updated": updated,
        "changes": changes[:20]
    })


@app.post("/api/dikw/auto-process")
async def dikw_auto_process(request: Request):
    """
    AI auto-process: suggest new items, promote existing, adjust confidence, assess wisdom candidates.
    
    Migration Note (P1.8): Uses DIKWSynthesizerAgent adapters for all AI operations.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from .agents.dikw_synthesizer import (
        suggest_from_signals_adapter,
        analyze_for_suggestions_adapter,
        generate_promoted_content_adapter,
        generate_wisdom_content_adapter,
    )
    
    data = await request.json()
    pyramid = data.get("pyramid", {})
    
    suggested = []
    promoted = []
    confidence_updates = []
    wisdom_candidates = []
    
    # Collect all existing items for context
    all_items = []
    for level in ['data', 'information', 'knowledge', 'wisdom']:
        for item in pyramid.get(level, []):
            all_items.append({
                "id": item.get("id"),
                "level": level,
                "content": item.get("content", ""),
                "summary": item.get("summary", ""),
                "confidence": item.get("confidence", 70),
                "created_at": item.get("created_at", ""),
                "tags": item.get("tags", "")
            })
    
    if not all_items:
        # If no items, suggest some based on recent signals
        with connect() as conn:
            recent_signals = conn.execute(
                """SELECT signals_json, meeting_name FROM meeting_summaries 
                   WHERE signals_json IS NOT NULL 
                   ORDER BY COALESCE(meeting_date, created_at) DESC LIMIT 5"""
            ).fetchall()
        
        signal_context = ""
        for row in recent_signals:
            try:
                signals = json.loads(row["signals_json"]) if isinstance(row["signals_json"], str) else row["signals_json"]
                for sig_type, items in signals.items():
                    for item in items[:2]:
                        signal_context += f"- {sig_type}: {item}\n"
            except:
                pass
        
        if signal_context:
            try:
                suggested = await suggest_from_signals_adapter(signal_context)
            except Exception as e:
                print(f"Error generating suggestions: {e}")
    else:
        try:
            # Use adapter for comprehensive analysis
            analysis = await analyze_for_suggestions_adapter(all_items)
            
            # Process promotions with enhanced content generation
            for promo in analysis.get("promote", []):
                item_id = promo.get("id")
                item = next((i for i in all_items if i["id"] == item_id), None)
                if item:
                    to_level = promo.get("to_level", "information")
                    # Skip if already at target level or higher
                    level_order = {'data': 0, 'information': 1, 'knowledge': 2, 'wisdom': 3}
                    if level_order.get(item["level"], 0) >= level_order.get(to_level, 1):
                        continue
                    
                    # Generate promoted content using adapter
                    content_result = await generate_promoted_content_adapter(item['content'], to_level)
                    
                    promoted.append({
                        "id": item_id,
                        "from_level": item["level"],
                        "to_level": to_level,
                        "original_content": item["content"][:100],
                        "promoted_content": content_result.get('promoted_content', ''),
                        "summary": content_result.get('summary', ''),
                        "reason": promo.get("reason", "Ready for promotion based on content maturity")
                    })
            
            # Process confidence adjustments with validation
            for conf in analysis.get("confidence", []):
                item_id = conf.get("id")
                item = next((i for i in all_items if i["id"] == item_id), None)
                if item:
                    new_conf = conf.get("new_confidence", item["confidence"])
                    # Validate confidence is reasonable
                    new_conf = max(10, min(95, new_conf))
                    # Only include if there's a meaningful change
                    if abs(new_conf - item["confidence"]) >= 5:
                        confidence_updates.append({
                            "id": item_id,
                            "level": item["level"],
                            "content": item["content"],
                            "old_confidence": item["confidence"],
                            "new_confidence": new_conf,
                            "reason": conf.get("reason", "Confidence adjusted based on content analysis")
                        })
            
            # Process wisdom candidates
            for wc in analysis.get("wisdom_candidates", []):
                item_id = wc.get("id")
                item = next((i for i in all_items if i["id"] == item_id and i["level"] == "knowledge"), None)
                if item:
                    readiness = wc.get("readiness_score", 5)
                    if readiness >= 6:  # Only show high-readiness candidates
                        # Generate the wisdom content using adapter
                        wisdom_content = await generate_wisdom_content_adapter(
                            item['content'], 
                            wc.get('potential_wisdom', '')
                        )
                        
                        wisdom_candidates.append({
                            "id": item_id,
                            "original_content": item["content"],
                            "potential_wisdom": wisdom_content,
                            "readiness_score": readiness,
                            "reason": wc.get("reason", "Shows potential for strategic principle")
                        })
            
            # Add new suggestions
            suggested = analysis.get("suggest", [])
            
        except Exception as e:
            print(f"Error in auto-process: {e}")
            import traceback
            traceback.print_exc()
    
    return JSONResponse({
        "status": "ok",
        "suggested": suggested,
        "promoted": promoted,
        "confidence_updates": confidence_updates,
        "wisdom_candidates": wisdom_candidates
    })


@app.get("/api/signals/unprocessed")
async def get_unprocessed_signals():
    """Get signals that haven't been promoted to DIKW yet."""
    with connect() as conn:
        # Get all signals from meetings that haven't been processed
        meetings = conn.execute(
            """SELECT id, meeting_name, signals_json 
               FROM meeting_summaries 
               WHERE signals_json IS NOT NULL
               ORDER BY COALESCE(meeting_date, created_at) DESC
               LIMIT 20"""
        ).fetchall()
        
        # Get already processed signals
        processed = conn.execute(
            """SELECT meeting_id, signal_type, signal_text 
               FROM signal_status 
               WHERE converted_to = 'dikw'"""
        ).fetchall()
        
        processed_set = set(
            (p['meeting_id'], p['signal_type'], p['signal_text']) 
            for p in processed
        )
        
        unprocessed = []
        for meeting in meetings:
            try:
                signals = json.loads(meeting['signals_json'])
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
        "format": "plain",
    })
    
    meeting_id = result.get("meeting_id")
    
    # Store Pocket action items in signals_json if provided
    if meeting_id and pocket_action_items and pocket_action_items.strip():
        try:
            # Parse action items from the text format back to structured data
            # Parse JSON from hidden field (contains array of action item objects)
            pocket_items = json.loads(pocket_action_items.strip())
            
            # Add source marker to each item
            for item in pocket_items:
                item["source"] = "pocket"
            
            if pocket_items:
                # Update the meeting's signals_json to include action items
                with connect() as conn:
                    row = conn.execute(
                        "SELECT signals_json FROM meeting_summaries WHERE id = ?",
                        (meeting_id,)
                    ).fetchone()
                    
                    signals = json.loads(row["signals_json"]) if row and row["signals_json"] else {}
                    
                    # Merge Pocket action items (preserve existing)
                    existing_items = signals.get("action_items", [])
                    signals["action_items"] = existing_items + pocket_items
                    
                    conn.execute(
                        "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
                        (json.dumps(signals), meeting_id)
                    )
                    
                logger.info(f"Added {len(pocket_items)} Pocket action items to meeting {meeting_id}")
        except Exception as e:
            logger.warning(f"Failed to parse/store Pocket action items: {e}")
    
    # Handle screenshot uploads if meeting was created successfully
    if meeting_id:
        form = await request.form()
        screenshots = form.getlist("screenshots")
        
        for screenshot in screenshots:
            if hasattr(screenshot, 'file') and screenshot.filename:
                try:
                    import uuid
                    import os
                    
                    # Generate unique filename
                    ext = os.path.splitext(screenshot.filename)[1] or '.png'
                    unique_name = f"{uuid.uuid4().hex}{ext}"
                    file_path = os.path.join(UPLOAD_DIR, unique_name)
                    
                    # Save file
                    content = await screenshot.read()
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    # Record in database
                    with connect() as conn:
                        conn.execute("""
                            INSERT INTO attachments (ref_type, ref_id, filename, file_path, mime_type, file_size)
                            VALUES ('meeting', ?, ?, ?, ?, ?)
                        """, (meeting_id, screenshot.filename, f"uploads/{unique_name}", 
                              screenshot.content_type or 'image/png', len(content)))
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


# Pocket integration: list recent recordings
@app.get("/api/integrations/pocket/recordings")
async def pocket_list_recordings(
    page: int = 1,
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """List recent Pocket recordings for selection.

    Returns paginated list with id, title, created_at for UI display.
    """
    try:
        client = PocketClient()
        resp = client.list_recordings(
            page=page,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Extract recordings from response
        data = resp.get("data") or {}
        items = data if isinstance(data, list) else data.get("items") or []
        pagination = resp.get("pagination") or {}
        
        # Build clean list for UI
        recordings = []
        for item in items:
            rec_id = item.get("id") or item.get("recording_id")
            title = item.get("title") or "(untitled)"
            created = item.get("created_at") or item.get("recording_at") or "unknown"
            if rec_id:
                recordings.append({
                    "id": rec_id,
                    "title": title,
                    "created_at": created,
                })
        
        return JSONResponse({
            "success": True,
            "recordings": recordings,
            "pagination": {
                "page": pagination.get("page", 1),
                "total_pages": pagination.get("total_pages", 1),
                "has_more": pagination.get("has_more", False),
            },
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)


# Pocket integration: fetch summary/transcript by recording ID
@app.post("/api/integrations/pocket/fetch")
async def pocket_fetch(request: Request):
    """Fetch Pocket summary, transcript, mind map, and action items for a given recording.

    Accepts JSON or form with `recording_id` and optional version selectors:
    - `summary_key`: specific summary version to fetch (e.g., 'v2_summary', 'v1_summary')
    - `mind_map_key`: specific mind map version to fetch (e.g., 'v2_mind_map')
    
    Returns `summary_text`, `transcript_text`, `mind_map_text`, and `action_items` if available.
    """
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)

    recording_id = (body.get("recording_id") or "").strip()
    if not recording_id:
        return JSONResponse({"success": False, "error": "recording_id required"}, status_code=400)

    summary_key = (body.get("summary_key") or "").strip() or None
    mind_map_key = (body.get("mind_map_key") or "").strip() or None

    try:
        client = PocketClient()
        details = client.get_recording(recording_id, include_transcript=True, include_summarizations=True)
        
        # If specific versions requested, fetch those; otherwise fetch latest
        if summary_key or mind_map_key:
            # Fetch specific versions
            payload = details.get("data", {})
            rec = payload if isinstance(payload, dict) else {}
            summ_dict = rec.get("summarizations", {}) if isinstance(rec.get("summarizations"), dict) else {}
            
            # Get selected summary
            summary_text = None
            if summary_key and summary_key in summ_dict:
                summ_obj = summ_dict[summary_key]
                if isinstance(summ_obj, dict):
                    summary_text = summ_obj.get("markdown") or summ_obj.get("text") or summ_obj.get("content")
            
            # Get selected mind map
            mind_map_text = None
            if mind_map_key and mind_map_key in summ_dict:
                mm_obj = summ_dict[mind_map_key]
                if isinstance(mm_obj, dict):
                    # Format the mind map nodes
                    nodes = mm_obj.get("nodes", [])
                    if isinstance(nodes, list):
                        lines = []
                        for node in nodes:
                            if isinstance(node, dict):
                                title = (node.get("title") or "").strip()
                                if title:
                                    node_id = node.get("node_id", "")
                                    parent_id = node.get("parent_node_id", "")
                                    indent = "  " if node_id != parent_id else ""
                                    lines.append(f"{indent}• {title}")
                        if lines:
                            mind_map_text = "\n".join(lines)
                    elif "markdown" in mm_obj:
                        mind_map_text = mm_obj.get("markdown")
        else:
            # Fetch latest versions (original behavior)
            summary_text, _summary_obj = extract_latest_summary(details)
            mind_map_text = extract_mind_map(details)
        
        transcript_text = extract_transcript_text(details)
        action_items = extract_action_items(details)

        return JSONResponse({
            "success": True,
            "recording_id": recording_id,
            "summary_text": summary_text,
            "transcript_text": transcript_text,
            "mind_map_text": mind_map_text,
            "action_items": action_items,
        })
    except Exception as e:
        # Surface any API or parsing error
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)


# Pocket integration: fetch all available versions (summaries, mind maps)
@app.post("/api/integrations/pocket/fetch-versions")
async def pocket_fetch_versions(request: Request):
    """Fetch all available summary and mind map versions for a recording.
    
    Returns lists of available versions so user can choose which to use.
    Accepts JSON or form with `recording_id`.
    """
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)

    recording_id = (body.get("recording_id") or "").strip()
    if not recording_id:
        return JSONResponse({"success": False, "error": "recording_id required"}, status_code=400)

    try:
        client = PocketClient()
        details = client.get_recording(recording_id, include_transcript=True, include_summarizations=True)
        
        # Extract all available versions
        summary_versions = get_all_summary_versions(details)
        mind_map_versions = get_all_mind_map_versions(details)
        
        # Also get transcript and action items
        transcript_text = extract_transcript_text(details)
        action_items = extract_action_items(details)

        return JSONResponse({
            "success": True,
            "recording_id": recording_id,
            "summary_versions": summary_versions,
            "mind_map_versions": mind_map_versions,
            "transcript_text": transcript_text,
            "action_items": action_items,
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)


# Pocket webhook endpoint (payload URL)
@app.post("/api/integrations/pocket/webhook")
async def pocket_webhook(request: Request):
    """Webhook endpoint for Pocket to notify of new/updated recordings.

    Body should include a `recording_id`. We fetch details immediately and return 200.
    """
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)

    recording_id = (body.get("recording_id") or "").strip()
    if not recording_id:
        return JSONResponse({"success": False, "error": "recording_id required"}, status_code=400)

    try:
        client = PocketClient()
        details = client.get_recording(recording_id, include_transcript=True, include_summarizations=True)
        summary_text, _summary_obj = extract_latest_summary(details)
        transcript_text = extract_transcript_text(details)

        # TODO: persist to DB and link to meeting if mapping exists
        return JSONResponse({
            "success": True,
            "recording_id": recording_id,
            "summary_text": summary_text,
            "transcript_text": transcript_text,
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)

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