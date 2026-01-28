"""
Dashboard page route for the SignalFlow application.

Renders the main dashboard HTML page with summary data.
Extracted from main.py during Phase 2.9 refactoring.

Note: API routes for dashboard are in domains/dashboard/api/
This file only contains the HTML page render route.
"""
import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from ..infrastructure.supabase_client import get_supabase_client
from ..repositories import get_signal_repository
from ..services import meeting_service, document_service, ticket_service

router = APIRouter(tags=["Dashboard"])

templates = Jinja2Templates(directory="src/app/templates")
templates.env.globals["env"] = os.environ

# Get supabase client for direct table access
supabase = get_supabase_client()

# Repository instance
signal_repo = get_signal_repository()


def get_sprint_info():
    """Get current sprint day and info, with working days calculation."""
    try:
        client = get_supabase_client()
        if client:
            result = client.table("sprint_settings").select("*").limit(1).execute()
            if result.data:
                row_dict = result.data[0]
                start_str = row_dict.get("sprint_start_date")
                if start_str:
                    # Handle both date formats
                    if "T" in str(start_str):
                        start = datetime.fromisoformat(
                            str(start_str).replace("Z", "+00:00")
                        ).replace(tzinfo=None)
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
                    progress = (
                        int((working_days_elapsed / total_working_days) * 100)
                        if total_working_days > 0
                        else 0
                    )

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
    except Exception:
        pass

    # Return default if no sprint settings found
    return None


def _get_greeting_context(sprint: dict | None) -> str:
    """Generate dynamic greeting based on sprint cadence."""
    if sprint:
        days_remaining = sprint.get("working_days_remaining", 0)
        progress = sprint.get("progress", 0)
        day_of_week = datetime.now().weekday()

        if day_of_week == 0:  # Monday
            return "fresh start to the week"
        elif day_of_week == 4:  # Friday
            return "let's close out strong"
        elif days_remaining <= 2 and days_remaining > 0:
            return "sprint finish line ahead"
        elif progress < 15:
            return "new sprint energy"
        elif progress >= 80:
            return "home stretch"
        elif progress >= 50:
            return "past the halfway point"
    return "ready to dive in"


def _build_recent_signals(meetings_with_signals: list, feedback_map: dict, status_map: dict) -> list:
    """Build recent signals list from meeting data."""
    recent_signals = []
    for m in meetings_with_signals[:10]:
        try:
            signals = m.get("signals", {})
            for stype, icon_type in [
                ("blockers", "blocker"),
                ("action_items", "action"),
                ("decisions", "decision"),
                ("ideas", "idea"),
                ("risks", "risk"),
            ]:
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
                                "status": status_map.get(status_key),
                            })
        except:
            pass
    return recent_signals


def _build_highlights(meetings_with_signals: list) -> list:
    """Build highlights section from meeting signals."""
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

    # Prioritize blockers first
    blockers_first = [h for h in highlights if h["type"] == "blocker"]
    actions = [h for h in highlights if h["type"] == "action"]
    others = [h for h in highlights if h["type"] not in ("blocker", "action")]
    return (blockers_first + actions + others)[:6]


def _build_recent_items() -> list:
    """Build recent items list (meetings and docs)."""
    recent_items = []

    # Recent meetings
    recent_mtgs = meeting_service.get_recent_meetings(limit=5)
    for m in recent_mtgs:
        recent_items.append({
            "type": "meeting",
            "title": m["meeting_name"],
            "date": m["meeting_date"],
            "url": f"/meetings/{m['id']}",
        })

    # Recent docs
    recent_docs = document_service.get_recent_documents(limit=5)
    for d in recent_docs:
        recent_items.append({
            "type": "doc",
            "title": d.get("source", "Untitled"),
            "date": d.get("document_date"),
            "url": f"/documents/{d['id']}",
        })

    # Sort by date and take top 5
    recent_items.sort(key=lambda x: x["date"] or "", reverse=True)
    return recent_items[:5]


def _get_execution_context(active_tickets: list) -> tuple:
    """Extract execution ticket and tasks from active tickets."""
    execution_ticket = None
    execution_tasks = []

    for ticket in active_tickets:
        raw_tasks = ticket.get("task_decomposition")
        if raw_tasks:
            try:
                parsed = json.loads(raw_tasks) if isinstance(raw_tasks, str) else raw_tasks
            except Exception:
                parsed = []

            if isinstance(parsed, list) and parsed:
                normalized = []
                for idx, item in enumerate(parsed):
                    if isinstance(item, dict):
                        title = (
                            item.get("title")
                            or item.get("text")
                            or item.get("task")
                            or item.get("name")
                            or "Task"
                        )
                        description = (
                            item.get("description") or item.get("details") or item.get("estimate")
                        )
                        status = item.get("status", "pending")
                    else:
                        title = str(item)
                        description = None
                        status = "pending"
                    normalized.append({
                        "index": idx,
                        "title": title,
                        "description": description,
                        "status": status,
                    })

                execution_ticket = {
                    "id": ticket["id"],
                    "ticket_id": ticket.get("ticket_id"),
                    "title": ticket.get("title"),
                }
                execution_tasks = normalized
                break

    return execution_ticket, execution_tasks


@router.get("/")
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
    greeting_context = _get_greeting_context(sprint)

    # Get stats from services
    meeting_stats = meeting_service.get_dashboard_stats()
    meetings_count = meeting_stats["meetings_count"]
    meetings_with_signals = meeting_stats["meetings_with_signals"]
    signals_count = meeting_stats["signals_count"]

    docs_count = document_service.get_documents_count()
    tickets_count = ticket_service.get_tickets_count(statuses=["todo", "in_progress", "in_review"])

    # Conversations count
    conversations_count = 0
    try:
        conv_result = supabase.table("conversations").select("id", count="exact").execute()
        conversations_count = conv_result.count or 0
    except:
        pass

    # Get feedback and status maps
    feedback_map = {}
    try:
        feedback_rows = signal_repo.get_all_feedback()
        for f in feedback_rows:
            key = f"{f['meeting_id']}:{f['signal_type']}:{f['signal_text']}"
            feedback_map[key] = f["feedback"]
    except:
        pass

    status_map = {}
    try:
        meeting_ids = [m["id"] for m in meetings_with_signals[:10]]
        if meeting_ids:
            status_result = signal_repo.get_status_for_meetings(meeting_ids)
            for key, s in status_result.items():
                status_map[key] = s.get("status")
    except:
        pass

    # Build dashboard components
    recent_signals = _build_recent_signals(meetings_with_signals, feedback_map, status_map)
    highlights = _build_highlights(meetings_with_signals)
    recent_items = _build_recent_items()

    # Get active tickets and execution context
    active_tickets = ticket_service.get_active_tickets(limit=5)
    execution_ticket, execution_tasks = _get_execution_context(active_tickets)

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
