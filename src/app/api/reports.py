"""
Reports and Analytics API Routes

Provides reporting endpoints for sprint progress, signals,
time tracking, and weekly intelligence summaries.

Routes:
- /reports - Reports page
- /api/reports/signals - Signal statistics
- /api/reports/workflow-progress - Workflow mode progress
- /api/reports/daily - Daily breakdown
- /api/reports/sprint-burndown - Sprint burndown with task decomposition
- /api/reports/weekly-intelligence - Weekly intelligence summary
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from ..infrastructure.supabase_client import get_supabase_client
from ..services import meeting_service
from ..services import ticket_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


# Sprint burndown cache to avoid recomputing on rapid mode changes
_sprint_burndown_cache = {"data": None, "timestamp": 0}
SPRINT_BURNDOWN_CACHE_TTL = 90  # Cache for 90 seconds


def _format_duration(seconds: int) -> str:
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


# =============================================================================
# Reports Page
# =============================================================================

# NOTE: The /reports HTML page route is in main.py
# Templates setup - used by API routes if needed
templates: Optional[Jinja2Templates] = None

def set_templates(t: Jinja2Templates):
    """Set templates instance from main.py."""
    global templates
    templates = t


# =============================================================================
# Signal Reports
# =============================================================================

@router.get("/api/reports/signals")
async def get_signals_report(days: int = 14):
    """Get signal statistics for the reporting period."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Get meetings from Supabase
    meetings = meeting_service.get_meetings_with_signals_in_range(days=days)
    
    decisions = actions = blockers = risks = ideas = 0
    
    for m in meetings:
        try:
            signals = m.get("signals", {})
            decisions += len(signals.get("decisions", []))
            actions += len(signals.get("action_items", []))
            blockers += len(signals.get("blockers", []))
            risks += len(signals.get("risks", []))
            ideas += len(signals.get("ideas", []))
        except:
            continue
    
    # Count tickets created in period from Supabase
    tickets_count = ticket_service.get_tickets_created_since(cutoff)
    
    return JSONResponse({
        "decisions": decisions,
        "actions": actions,
        "blockers": blockers,
        "risks": risks,
        "ideas": ideas,
        "meetings_count": len(meetings),
        "tickets_created": tickets_count
    })


# =============================================================================
# Workflow Progress Report
# =============================================================================

@router.get("/api/reports/workflow-progress")
async def get_workflow_progress_report():
    """Get workflow mode progress for reporting."""
    sb = get_supabase_client()
    
    # Get active workflow modes from Supabase
    modes_result = sb.table("workflow_modes").select("*").eq("is_active", True).order("sort_order").execute()
    
    result = []
    for mode in modes_result.data or []:
        steps = json.loads(mode["steps_json"]) if mode.get("steps_json") else []
        total_steps = len(steps)
        
        # Get progress from settings
        progress_result = sb.table("settings").select("value").eq("key", f"workflow_progress_{mode['mode_key']}").execute()
        
        completed = 0
        if progress_result.data:
            try:
                progress = json.loads(progress_result.data[0]["value"])
                completed = sum(1 for p in progress if p)
            except:
                pass
        
        result.append({
            "mode_key": mode["mode_key"],
            "name": mode["name"],
            "icon": mode.get("icon"),
            "total_steps": total_steps,
            "progress": completed
        })
    
    return JSONResponse({"modes": result})


# =============================================================================
# Daily Report
# =============================================================================

@router.get("/api/reports/daily")
async def get_daily_report(days: int = 14):
    """Get daily breakdown for reporting."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    sb = get_supabase_client()
    
    # Get daily time tracking from Supabase
    time_result = sb.table("mode_sessions").select("date, duration_seconds").gte("date", cutoff).not_.is_("duration_seconds", "null").execute()
    
    # Aggregate by date
    daily_time_map = {}
    for row in time_result.data or []:
        date = row["date"]
        if date not in daily_time_map:
            daily_time_map[date] = {"total_seconds": 0, "sessions": 0}
        daily_time_map[date]["total_seconds"] += row["duration_seconds"] or 0
        daily_time_map[date]["sessions"] += 1
    
    # Get daily signal counts from Supabase
    daily_signals = {}
    meetings = meeting_service.get_meetings_with_signals_in_range(days=days)
    
    for m in meetings:
        date = m.get("meeting_date") or m.get("created_at", "")[:10]
        if date:
            try:
                signals = m.get("signals", {})
                count = sum(len(signals.get(k, [])) for k in ["decisions", "action_items", "blockers", "risks", "ideas"])
                daily_signals[date] = daily_signals.get(date, 0) + count
            except:
                pass
    
    result = []
    for date in sorted(daily_time_map.keys(), reverse=True):
        data = daily_time_map[date]
        result.append({
            "date": date,
            "total_seconds": data["total_seconds"],
            "sessions": data["sessions"],
            "signals": daily_signals.get(date, 0)
        })
    
    return JSONResponse({"daily": result})


# =============================================================================
# Sprint Burndown
# =============================================================================

@router.get("/api/reports/sprint-burndown")
async def get_sprint_burndown(force: bool = False):
    """Get sprint points breakdown with task decomposition progress."""
    global _sprint_burndown_cache
    
    # Check cache unless force refresh
    now = time.time()
    if not force and _sprint_burndown_cache["data"] and (now - _sprint_burndown_cache["timestamp"]) < SPRINT_BURNDOWN_CACHE_TTL:
        return JSONResponse(_sprint_burndown_cache["data"])
    
    sb = get_supabase_client()
    
    # Get sprint settings from Supabase
    sprint_result = sb.table("sprint_settings").select("*").eq("id", 1).execute()
    sprint_settings = sprint_result.data[0] if sprint_result.data else None
    working_days_remaining = None
    sprint_total_days = 14
    sprint_day = None
    
    if sprint_settings and sprint_settings.get("sprint_start_date"):
        sprint_start = datetime.strptime(sprint_settings["sprint_start_date"], "%Y-%m-%d")
        sprint_total_days = sprint_settings.get("sprint_length_days") or 14
        sprint_day = (datetime.now() - sprint_start).days + 1
        days_remaining = sprint_total_days - sprint_day
        # Estimate working days (exclude weekends roughly)
        working_days_remaining = max(0, int(days_remaining * 5 / 7))
    
    # Get all active tickets assigned to sprint from Supabase
    tickets = ticket_service.get_active_sprint_tickets()
    
    total_points = 0
    completed_points = 0
    in_progress_points = 0
    remaining_points = 0
    
    ticket_breakdown = []
    
    for ticket in tickets:
        points = ticket.get("sprint_points") or 0
        total_points += points
        
        # Parse task decomposition
        tasks = []
        total_tasks = 0
        completed_tasks = 0
        
        if ticket.get("task_decomposition"):
            try:
                parsed = json.loads(ticket["task_decomposition"]) if isinstance(ticket["task_decomposition"], str) else ticket["task_decomposition"]
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
        
        if ticket.get("status") == "in_progress":
            in_progress_points += ticket_remaining
        else:
            remaining_points += points
        
        completed_points += ticket_completed_points
        
        ticket_breakdown.append({
            "id": ticket["id"],
            "ticket_id": ticket.get("ticket_id"),
            "title": ticket.get("title"),
            "status": ticket.get("status"),
            "sprint_points": points,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "progress_pct": round(progress_pct, 1),
            "tasks": tasks
        })
    
    # Get completed tickets for total burndown context (in sprint only)
    done_points = ticket_service.get_completed_sprint_points()
    
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


# =============================================================================
# Weekly Intelligence
# =============================================================================

@router.get("/api/reports/weekly-intelligence")
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
    
    sb = get_supabase_client()
    
    # Get meetings from Supabase
    meetings_from_supabase = meeting_service.get_meetings_with_signals_in_range(days=7)
    
    meetings_data = []
    all_decisions = []
    all_actions = []
    all_blockers = []
    all_risks = []
    all_ideas = []
    
    for m in meetings_from_supabase:
        meeting_info = {
            "id": m.get("id"),
            "name": m.get("meeting_name") or "Untitled Meeting",
            "date": m.get("meeting_date") or (m.get("created_at") or "")[:10]
        }
        
        signals = m.get("signals", {})
        if signals:
            meeting_info["signal_count"] = sum(
                len(signals.get(k, [])) 
                for k in ["decisions", "action_items", "blockers", "risks", "ideas"]
            )
            
            # Collect signals with meeting context
            for d in signals.get("decisions", []):
                all_decisions.append({"text": d, "meeting": m.get("meeting_name")})
            for a in signals.get("action_items", []):
                all_actions.append({"text": a, "meeting": m.get("meeting_name")})
            for b in signals.get("blockers", []):
                all_blockers.append({"text": b, "meeting": m.get("meeting_name")})
            for r in signals.get("risks", []):
                all_risks.append({"text": r, "meeting": m.get("meeting_name")})
            for i in signals.get("ideas", []):
                all_ideas.append({"text": i, "meeting": m.get("meeting_name")})
        else:
            meeting_info["signal_count"] = 0
        
        meetings_data.append(meeting_info)
    
    # =====================================================================
    # DIKW PYRAMID ACTIVITY
    # =====================================================================
    dikw_result = sb.table("dikw_items").select("level, created_at").eq("status", "active").execute()
    
    dikw_summary = {
        "wisdom": {"total": 0, "new": 0},
        "knowledge": {"total": 0, "new": 0},
        "information": {"total": 0, "new": 0},
        "data": {"total": 0, "new": 0}
    }
    for item in dikw_result.data or []:
        level = item.get("level")
        if level in dikw_summary:
            dikw_summary[level]["total"] += 1
            if item.get("created_at", "") >= week_start:
                dikw_summary[level]["new"] += 1
    
    # Recent wisdom/knowledge items (high value)
    high_value_result = sb.table("dikw_items").select("id, level, content, summary, tags").in_("level", ["wisdom", "knowledge"]).eq("status", "active").order("created_at", desc=True).limit(5).execute()
    high_value_dikw = high_value_result.data or []
    
    # =====================================================================
    # TICKET/SPRINT PROGRESS
    # =====================================================================
    sprint_overview = ticket_service.get_sprint_ticket_stats()
    if not sprint_overview:
        sprint_overview = {
            "todo": {"count": 0, "points": 0},
            "in_progress": {"count": 0, "points": 0},
            "in_review": {"count": 0, "points": 0},
            "blocked": {"count": 0, "points": 0},
            "done": {"count": 0, "points": 0}
        }
    
    # Blocked tickets need attention
    blocked_tickets = ticket_service.get_blocked_sprint_tickets(limit=5)
    
    # =====================================================================
    # ACTION ITEMS DUE SOON
    # =====================================================================
    actions_result = sb.table("accountability_items").select("id, description, source_ref_id, status, created_at").neq("status", "complete").order("created_at", desc=True).limit(10).execute()
    recent_actions = actions_result.data or []
    
    # =====================================================================
    # CAREER STANDUPS
    # =====================================================================
    standups_result = sb.table("standup_updates").select("id, standup_date, content, feedback, sentiment, key_themes, created_at").gte("standup_date", week_start).order("standup_date", desc=True).limit(7).execute()
    
    standups_data = [
        {
            "id": s["id"],
            "date": s.get("standup_date"),
            "content": s["content"][:100] + "..." if s.get("content") and len(s["content"]) > 100 else s.get("content"),
            "sentiment": s.get("sentiment"),
            "key_themes": s.get("key_themes"),
            "has_feedback": bool(s.get("feedback"))
        }
        for s in standups_result.data or []
    ]
    
    # =====================================================================
    # TIME TRACKING SUMMARY
    # =====================================================================
    time_result = sb.table("mode_sessions").select("mode, duration_seconds").gte("date", week_start).not_.is_("duration_seconds", "null").execute()
    
    time_by_mode = {}
    for row in time_result.data or []:
        mode = row["mode"]
        if mode not in time_by_mode:
            time_by_mode[mode] = {"total_seconds": 0, "sessions": 0}
        time_by_mode[mode]["total_seconds"] += row["duration_seconds"] or 0
        time_by_mode[mode]["sessions"] += 1
    
    time_summary = [
        {
            "mode": mode,
            "total_hours": round(data["total_seconds"] / 3600, 1),
            "sessions": data["sessions"]
        }
        for mode, data in sorted(time_by_mode.items(), key=lambda x: x[1]["total_seconds"], reverse=True)
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
                    "id": item.get("id"),
                    "level": item.get("level"),
                    "content": item["content"][:200] + "..." if len(item.get("content") or "") > 200 else item.get("content"),
                    "summary": item.get("summary"),
                    "tags": item.get("tags")
                }
                for item in high_value_dikw
            ]
        },
        "sprint": {
            "overview": sprint_overview,
            "blocked_tickets": [
                {
                    "id": t["id"],
                    "ticket_id": t.get("ticket_id"),
                    "title": t.get("title")
                }
                for t in blocked_tickets
            ]
        },
        "accountability": {
            "pending_actions": [
                {
                    "id": a["id"],
                    "description": a.get("description", "")[:100],
                    "status": a.get("status"),
                    "created_at": a.get("created_at")
                }
                for a in recent_actions
            ]
        },
        "standups": standups_data,
        "time_tracking": time_summary
    })
