from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import json
import os

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
from .chat.models import init_chat_tables
from .api.chat import router as chat_router
from .api.mcp import router as mcp_router
from .api.accountability import router as accountability_router
from .api.settings import router as settings_router
from .api.assistant import router as assistant_router
from .api.career import router as career_router
from .api.neo4j_graph import router as neo4j_router
from .mcp.registry import TOOL_REGISTRY
from .llm import ask as ask_llm
from .auth import (
    AuthMiddleware, get_login_page, create_session, 
    destroy_session, get_auth_password, hash_password
)

app = FastAPI(title="Hare Krishna - Memory & Signal Intelligence")

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


def init_neo4j_background():
    """Initialize Neo4j schema and backfill data in background (non-blocking)."""
    import threading
    def _init():
        try:
            from .api.neo4j_graph import is_neo4j_available, run_write, SCHEMA_QUERIES
            if not is_neo4j_available():
                print("Neo4j not available - skipping knowledge graph initialization")
                return
            
            # Initialize schema
            for query in SCHEMA_QUERIES:
                try:
                    run_write(query)
                except Exception as e:
                    print(f"Schema query failed (may already exist): {e}")
            
            # Trigger background sync
            from .api.neo4j_graph import sync_meetings_to_neo4j, sync_documents_to_neo4j
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(sync_meetings_to_neo4j())
                loop.run_until_complete(sync_documents_to_neo4j())
                print("Neo4j knowledge graph synced successfully")
            except Exception as e:
                print(f"Neo4j sync failed: {e}")
            finally:
                loop.close()
        except Exception as e:
            print(f"Neo4j initialization skipped: {e}")
    
    thread = threading.Thread(target=_init, daemon=True)
    thread.start()


@app.on_event("startup")
def startup():
    init_db()
    init_chat_tables()
    # Initialize Neo4j in background (non-blocking)
    init_neo4j_background()


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


@app.get("/settings")
def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/career")
def career_page(request: Request):
    """Career development page."""
    return templates.TemplateResponse("career.html", {"request": request})


@app.get("/dikw")
def dikw_page(request: Request):
    """DIKW Pyramid page for knowledge management."""
    return templates.TemplateResponse("dikw.html", {"request": request})


@app.get("/knowledge-graph")
def knowledge_graph_page(request: Request):
    """Neo4j Knowledge Graph visualization and management page."""
    return templates.TemplateResponse("knowledge_graph.html", {"request": request})


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
    """Handle quick AI questions from dashboard."""
    data = await request.json()
    topic = data.get("topic")
    query = data.get("query")
    
    # Build the question based on topic or custom query
    if topic:
        topic_prompts = {
            "blockers": "What are the current blockers or obstacles mentioned in recent meetings?",
            "decisions": "What key decisions were made in recent meetings?",
            "action_items": "What are the outstanding action items from recent meetings?",
            "ideas": "What new ideas or suggestions came up in recent meetings?",
            "risks": "What risks were identified in recent meetings?",
            "this_week": "Summarize what happened this week based on recent meetings and documents.",
            "rowan_mentions": "What mentions of Rowan or items assigned to Rowan are there in recent meetings?",
            "reach_outs": "Who needs to be contacted or reached out to based on recent meetings? What follow-ups are needed?",
            "announcements": "What team-wide announcements or important updates were shared in recent meetings?",
        }
        question = topic_prompts.get(topic, f"Tell me about {topic} from recent meetings.")
    else:
        question = query or "What's most important right now?"
    
    # Get context from recent meetings
    with connect() as conn:
        recent = conn.execute(
            """SELECT meeting_name, synthesized_notes, signals_json 
               FROM meeting_summaries 
               ORDER BY COALESCE(meeting_date, created_at) DESC 
               LIMIT 5"""
        ).fetchall()
    
    context_parts = []
    for m in recent:
        context_parts.append(f"Meeting: {m['meeting_name']}\n{m['synthesized_notes'][:1000]}")
        if m["signals_json"]:
            try:
                signals = json.loads(m["signals_json"])
                for stype in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                    items = signals.get(stype, [])
                    if items:
                        context_parts.append(f"{stype}: {', '.join(items[:3])}")
            except:
                pass
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""Based on this context from recent meetings and documents:

{context}

Question: {question}

Provide a concise, helpful answer. Focus on the most relevant information. Use bullet points where appropriate."""

    try:
        response = ask_llm(prompt)
        return JSONResponse({"response": response})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"AI Error: {str(e)}"}, status_code=500)


@app.get("/api/dashboard/highlights")
async def get_highlights():
    """Get current attention highlights for refresh."""
    with connect() as conn:
        recent_meetings = conn.execute(
            """SELECT id, meeting_name, signals_json 
               FROM meeting_summaries 
               ORDER BY COALESCE(meeting_date, created_at) DESC 
               LIMIT 5"""
        ).fetchall()
    
    highlights = []
    for m in recent_meetings:
        try:
            signals = json.loads(m["signals_json"]) if m["signals_json"] else {}
            # Add blockers (highest priority)
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
    
    # Prioritize blockers first
    blockers_first = [h for h in highlights if h["type"] == "blocker"]
    actions = [h for h in highlights if h["type"] == "action"]
    others = [h for h in highlights if h["type"] not in ("blocker", "action")]
    highlights = (blockers_first + actions + others)[:6]
    
    return JSONResponse({"highlights": highlights})


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
               VALUES (?, ?, ?, 'todo', ?, ?, CURRENT_TIMESTAMP)""",
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
               VALUES (?, ?, ?, 'todo', 'medium', ?, CURRENT_TIMESTAMP)""",
            (ticket_id, title, f"From AI Query: {query}\n\nAI Response:\n{content}", f"AI insight: {content[:150]}...")
        )
        conn.commit()
        ticket_db_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    
    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "ticket_db_id": ticket_db_id})


# ============================================
# Settings API Endpoints
# ============================================

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


@app.get("/api/reports/sprint-burndown")
async def get_sprint_burndown():
    """Get sprint points breakdown with task decomposition progress."""
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
        
        return JSONResponse({
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
        })


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
    """AI-interpret user status and auto-start timer."""
    from .llm import ask
    
    data = await request.json()
    status_text = data.get("status", "").strip()
    
    if not status_text:
        return JSONResponse({"error": "Status text required"}, status_code=400)
    
    # Use AI to interpret the status
    prompt = f"""Interpret this user status and extract structured data:
Status: "{status_text}"

Return ONLY a JSON object with these fields:
- mode: one of [grooming, planning, standup, implementation]
- activity: short description of what they're doing
- context: any relevant context or details

Examples:
"Working on the airflow DAG refactor" -> {{"mode": "implementation", "activity": "refactoring airflow DAG", "context": "airflow"}}
"Preparing for sprint planning" -> {{"mode": "planning", "activity": "sprint planning prep", "context": "sprint planning"}}
"In standup" -> {{"mode": "standup", "activity": "daily standup", "context": "standup meeting"}}

Return only valid JSON, no markdown or explanation."""
    
    try:
        result = ask(prompt, model="gpt-4o-mini")
        # Clean up markdown if present
        result = result.strip()
        if result.startswith("```json"):
            result = result.split("```json")[1].split("```")[0].strip()
        elif result.startswith("```"):
            result = result.split("```")[1].split("```")[0].strip()
        
        import json
        parsed = json.loads(result)
        
        mode = parsed.get("mode", "implementation")
        activity = parsed.get("activity", "")
        context_str = parsed.get("context", "")
        
    except Exception as e:
        # Fallback: default to implementation mode
        mode = "implementation"
        activity = status_text
        context_str = ""
    
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
# ============================================

DIKW_LEVELS = ['data', 'information', 'knowledge', 'wisdom']
DIKW_NEXT_LEVEL = {'data': 'information', 'information': 'knowledge', 'knowledge': 'wisdom'}

@app.get("/api/dikw")
async def get_dikw_items(level: str = None, status: str = "active"):
    """Get DIKW items, optionally filtered by level."""
    with connect() as conn:
        if level:
            items = conn.execute(
                """SELECT * FROM dikw_items WHERE level = ? AND status = ? 
                   ORDER BY created_at DESC""",
                (level, status)
            ).fetchall()
        else:
            items = conn.execute(
                """SELECT * FROM dikw_items WHERE status = ? 
                   ORDER BY level, created_at DESC""",
                (status,)
            ).fetchall()
    
    # Group by level for pyramid view
    pyramid = {level: [] for level in DIKW_LEVELS}
    for item in items:
        pyramid[item['level']].append(dict(item))
    
    return JSONResponse({
        "pyramid": pyramid,
        "counts": {level: len(pyramid[level]) for level in DIKW_LEVELS}
    })


@app.post("/api/dikw/promote-signal")
async def promote_signal_to_dikw(request: Request):
    """Promote a signal to the DIKW pyramid (starts as Data level)."""
    data = await request.json()
    signal_text = data.get("signal_text", "")
    signal_type = data.get("signal_type", "")
    meeting_id = data.get("meeting_id")
    target_level = data.get("level", "data")  # Can promote directly to higher level
    
    if not signal_text:
        return JSONResponse({"error": "Signal text is required"}, status_code=400)
    
    # Generate AI summary appropriate for the level
    level_prompts = {
        'data': f"Briefly describe this raw signal in one sentence: {signal_text}",
        'information': f"Explain the context and meaning of this signal: {signal_text}",
        'knowledge': f"What actionable insight or pattern does this represent? {signal_text}",
        'wisdom': f"What strategic principle or lesson can be derived from this? {signal_text}"
    }
    
    try:
        summary = ask_llm(level_prompts.get(target_level, level_prompts['data']))
    except:
        summary = signal_text[:200]
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO dikw_items 
               (level, content, summary, source_type, original_signal_type, meeting_id, validation_count)
               VALUES (?, ?, ?, 'signal', ?, ?, 1)""",
            (target_level, signal_text, summary, signal_type, meeting_id)
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
    
    return JSONResponse({"status": "ok", "id": item_id, "level": target_level})


@app.post("/api/dikw/promote")
async def promote_dikw_item(request: Request):
    """Promote a DIKW item to the next level (with AI synthesis)."""
    data = await request.json()
    item_id = data.get("item_id")
    
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    with connect() as conn:
        item = conn.execute("SELECT * FROM dikw_items WHERE id = ?", (item_id,)).fetchone()
        
        if not item:
            return JSONResponse({"error": "Item not found"}, status_code=404)
        
        current_level = item['level']
        if current_level == 'wisdom':
            return JSONResponse({"error": "Already at highest level"}, status_code=400)
        
        next_level = DIKW_NEXT_LEVEL[current_level]
        
        # Generate AI synthesis for next level
        synthesis_prompts = {
            'information': f"Transform this raw data into structured information. What does it mean in context?\n\nData: {item['content']}",
            'knowledge': f"Extract actionable knowledge from this information. What patterns or insights emerge?\n\nInformation: {item['content']}\n\nPrevious summary: {item['summary']}",
            'wisdom': f"Distill strategic wisdom from this knowledge. What principles should guide future decisions?\n\nKnowledge: {item['content']}\n\nInsight: {item['summary']}"
        }
        
        try:
            new_summary = ask_llm(synthesis_prompts[next_level])
        except:
            new_summary = f"Promoted from {current_level}: {item['summary']}"
        
        # Create new item at higher level
        conn.execute(
            """INSERT INTO dikw_items 
               (level, content, summary, source_type, source_ref_ids, original_signal_type, meeting_id, confidence, validation_count)
               VALUES (?, ?, ?, 'synthesis', ?, ?, ?, ?, ?)""",
            (next_level, item['content'], new_summary, json.dumps([item_id]), 
             item['original_signal_type'], item['meeting_id'],
             min(1.0, item['confidence'] + 0.1), item['validation_count'] + 1)
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        
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
        "summary": new_summary
    })


@app.post("/api/dikw/merge")
async def merge_dikw_items(request: Request):
    """Merge multiple items at the same level into a synthesized higher-level item."""
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
        combined_summaries = "\n".join([f"- {item['summary']}" for item in items if item['summary']])
        
        merge_prompt = f"""Synthesize these {len(items)} {current_level}-level items into a single {next_level}-level insight:

Items:
{combined_content}

Previous summaries:
{combined_summaries}

Create a unified {next_level}-level synthesis that captures the essence of all these items."""

        try:
            merged_summary = ask_llm(merge_prompt)
        except:
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


@app.post("/api/dikw")
async def create_dikw_item(request: Request):
    """Create a new DIKW item."""
    data = await request.json()
    level = data.get("level", "data")
    content = data.get("content", "").strip()
    summary = data.get("summary", "").strip()
    tags = data.get("tags", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO dikw_items (level, content, summary, tags, source_type)
               VALUES (?, ?, ?, ?, 'manual')""",
            (level, content, summary or None, tags or None)
        )
        conn.commit()
        item_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    
    return JSONResponse({"status": "ok", "id": item_id})


@app.put("/api/dikw/{item_id}")
async def update_dikw_item(item_id: int, request: Request):
    """Update an existing DIKW item."""
    data = await request.json()
    level = data.get("level")
    content = data.get("content", "").strip()
    summary = data.get("summary", "").strip()
    tags = data.get("tags", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    with connect() as conn:
        conn.execute(
            """UPDATE dikw_items 
               SET level = ?, content = ?, summary = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (level, content, summary or None, tags or None, item_id)
        )
        conn.commit()
    
    return JSONResponse({"status": "ok"})


@app.post("/api/dikw/ai-refine")
async def ai_refine_dikw(request: Request):
    """Use AI to refine/improve DIKW content."""
    data = await request.json()
    content = data.get("content", "")
    action = data.get("action", "clarify")
    custom_prompt = data.get("prompt")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    try:
        prompt = custom_prompt or f"Refine this content ({action}): {content}"
        refined = ask_llm(prompt)
        return JSONResponse({"status": "ok", "refined": refined})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dikw/ai-summarize")
async def ai_summarize_dikw(request: Request):
    """Generate AI summary for DIKW content."""
    data = await request.json()
    content = data.get("content", "")
    level = data.get("level", "data")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    level_prompts = {
        'data': f"Briefly describe this raw data point in one clear sentence:\n\n{content}",
        'information': f"Explain the context and significance of this information:\n\n{content}",
        'knowledge': f"What actionable insight or pattern does this represent?\n\n{content}",
        'wisdom': f"What strategic principle or lesson can be derived from this?\n\n{content}"
    }
    
    try:
        summary = ask_llm(level_prompts.get(level, level_prompts['data']))
        return JSONResponse({"status": "ok", "summary": summary})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dikw/ai-promote")
async def ai_promote_dikw(request: Request):
    """Use AI to promote content to the next DIKW level."""
    data = await request.json()
    content = data.get("content", "")
    from_level = data.get("from_level", "data")
    to_level = data.get("to_level", "information")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    promotion_prompts = {
        'information': f"""Transform this raw data into structured information. Explain what it means in context and why it matters.

Data: {content}

Provide the promoted information-level content:""",
        'knowledge': f"""Extract actionable knowledge from this information. What patterns, insights, or principles emerge that can guide decisions?

Information: {content}

Provide the promoted knowledge-level content:""",
        'wisdom': f"""Distill strategic wisdom from this knowledge. What fundamental principle or timeless lesson should guide future actions and decisions?

Knowledge: {content}

Provide the promoted wisdom-level content:"""
    }
    
    try:
        promoted = ask_llm(promotion_prompts.get(to_level, promotion_prompts['information']))
        
        # Also generate a summary for the new level
        summary_prompt = f"Summarize this {to_level}-level insight in one sentence:\n\n{promoted}"
        summary = ask_llm(summary_prompt)
        
        return JSONResponse({
            "status": "ok",
            "promoted_content": promoted,
            "summary": summary,
            "from_level": from_level,
            "to_level": to_level
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dikw/auto-process")
async def dikw_auto_process(request: Request):
    """AI auto-process: suggest new items, promote existing, adjust confidence."""
    data = await request.json()
    pyramid = data.get("pyramid", {})
    
    suggested = []
    promoted = []
    confidence_updates = []
    
    # Collect all existing items for context
    all_items = []
    for level in ['data', 'information', 'knowledge', 'wisdom']:
        for item in pyramid.get(level, []):
            all_items.append({
                "id": item.get("id"),
                "level": level,
                "content": item.get("content", ""),
                "confidence": item.get("confidence", 70),
                "created_at": item.get("created_at", "")
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
                import json
                signals = json.loads(row["signals_json"]) if isinstance(row["signals_json"], str) else row["signals_json"]
                for sig_type, items in signals.items():
                    for item in items[:2]:
                        signal_context += f"- {sig_type}: {item}\n"
            except:
                pass
        
        if signal_context:
            try:
                prompt = f"""Based on these recent signals from meetings, suggest 2-3 DIKW items to add:

{signal_context}

Return a JSON array of objects with: level (data/information/knowledge/wisdom), content, summary
Example: [{{"level": "data", "content": "Team velocity decreased 20% this sprint", "summary": "Velocity tracking observation"}}]

JSON array only:"""
                response = ask_llm(prompt)
                import json
                suggestions = json.loads(response.strip().strip('```json').strip('```'))
                suggested = suggestions[:3]
            except Exception as e:
                print(f"Error generating suggestions: {e}")
    else:
        # Analyze existing items for promotions and confidence adjustments
        items_summary = "\n".join([
            f"[{i['level']}] (id:{i['id']}, confidence:{i['confidence']}%) {i['content'][:200]}"
            for i in all_items[:20]
        ])
        
        try:
            prompt = f"""Analyze these DIKW pyramid items and suggest:
1. Which items are ready to be promoted to the next level (data->information->knowledge->wisdom)
2. Which items need confidence adjustments based on their content quality/certainty

Current items:
{items_summary}

Return JSON with three arrays:
- "promote": items ready for promotion [{{"id": <id>, "from_level": "data", "to_level": "information", "reason": "why"}}]
- "confidence": items needing confidence adjustment [{{"id": <id>, "old_confidence": 70, "new_confidence": 85, "reason": "why"}}]
- "suggest": new items to add [{{"level": "knowledge", "content": "...", "summary": "..."}}]

Focus on actionable improvements. JSON only:"""
            
            response = ask_llm(prompt)
            import json
            result = json.loads(response.strip().strip('```json').strip('```'))
            
            # Process promotions
            for promo in result.get("promote", [])[:3]:
                item_id = promo.get("id")
                item = next((i for i in all_items if i["id"] == item_id), None)
                if item:
                    to_level = promo.get("to_level", "information")
                    # Generate promoted content
                    promo_result = await ai_promote_dikw(Request(scope={"type": "http"}))
                    # Actually call the promotion logic directly
                    promotion_prompts = {
                        'information': f"Transform this data into structured information:\n{item['content']}",
                        'knowledge': f"Extract actionable knowledge:\n{item['content']}",
                        'wisdom': f"Distill strategic wisdom:\n{item['content']}"
                    }
                    promoted_content = ask_llm(promotion_prompts.get(to_level, promotion_prompts['information']))
                    summary = ask_llm(f"Summarize in one sentence: {promoted_content}")
                    
                    promoted.append({
                        "id": item_id,
                        "from_level": item["level"],
                        "to_level": to_level,
                        "promoted_content": promoted_content,
                        "summary": summary,
                        "reason": promo.get("reason", "")
                    })
            
            # Process confidence adjustments
            for conf in result.get("confidence", [])[:5]:
                item_id = conf.get("id")
                item = next((i for i in all_items if i["id"] == item_id), None)
                if item:
                    confidence_updates.append({
                        "id": item_id,
                        "level": item["level"],
                        "content": item["content"],
                        "old_confidence": item["confidence"],
                        "new_confidence": conf.get("new_confidence", item["confidence"]),
                        "reason": conf.get("reason", "")
                    })
            
            # Add new suggestions
            suggested = result.get("suggest", [])[:3]
            
        except Exception as e:
            print(f"Error in auto-process: {e}")
            import traceback
            traceback.print_exc()
    
    return JSONResponse({
        "status": "ok",
        "suggested": suggested,
        "promoted": promoted,
        "confidence_updates": confidence_updates
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
def load_meeting_bundle_ui(
    meeting_name: str = Form(...),
    meeting_date: str = Form(None),
    summary_text: str = Form(...),
    pocket_transcript: str = Form(None),
    teams_transcript: str = Form(None),
):
    tool = TOOL_REGISTRY["load_meeting_bundle"]
    
    # Merge transcripts if provided
    transcript_parts = []
    if pocket_transcript and pocket_transcript.strip():
        transcript_parts.append(f"=== Pocket Transcript ===\n{pocket_transcript.strip()}")
    if teams_transcript and teams_transcript.strip():
        transcript_parts.append(f"=== Teams Transcript ===\n{teams_transcript.strip()}")
    
    merged_transcript = "\n\n".join(transcript_parts) if transcript_parts else None

    tool({
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "summary_text": summary_text,
        "transcript_text": merged_transcript,
        "format": "plain",
    })

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
app.include_router(chat_router)
app.include_router(mcp_router)
app.include_router(accountability_router)
app.include_router(settings_router)
app.include_router(assistant_router)
app.include_router(career_router)
app.include_router(neo4j_router)