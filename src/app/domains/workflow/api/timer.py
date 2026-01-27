# src/app/domains/workflow/api/timer.py
"""
Workflow Timer API Routes

Manages mode timer sessions - start, stop, status, and statistics.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.post("/api/mode-timer/start")
async def start_mode_timer(request: Request):
    """Start a timer session for a specific mode."""
    data = await request.json()
    mode = data.get("mode", "implementation")
    
    sb = get_supabase_client()
    today = datetime.now().strftime("%Y-%m-%d")
    started_at = datetime.now().isoformat()
    
    # Check if there's an active session for this mode (no ended_at)
    active_result = sb.table("mode_sessions").select("id").eq("mode", mode).is_("ended_at", "null").execute()
    
    if active_result.data:
        # Already active, return existing session
        return JSONResponse({"status": "already_active", "session_id": active_result.data[0]["id"]})
    
    # Create new session
    result = sb.table("mode_sessions").insert({
        "mode": mode,
        "started_at": started_at,
        "date": today
    }).execute()
    session_id = result.data[0]["id"] if result.data else None
    
    return JSONResponse({"status": "ok", "session_id": session_id, "started_at": started_at})


@router.post("/api/mode-timer/stop")
async def stop_mode_timer(request: Request):
    """Stop the active timer session for a specific mode."""
    data = await request.json()
    mode = data.get("mode", "implementation")
    
    sb = get_supabase_client()
    ended_at = datetime.now().isoformat()
    
    # Find active session
    active_result = sb.table("mode_sessions").select("id, started_at").eq("mode", mode).is_("ended_at", "null").execute()
    
    if not active_result.data:
        return JSONResponse({"status": "no_active_session"})
    
    active = active_result.data[0]
    
    # Calculate duration
    start_time = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00").replace("+00:00", ""))
    end_time = datetime.now()
    duration = int((end_time - start_time).total_seconds())
    
    # Update session
    sb.table("mode_sessions").update({
        "ended_at": ended_at,
        "duration_seconds": duration
    }).eq("id", active["id"]).execute()
    
    return JSONResponse({
        "status": "ok", 
        "session_id": active["id"], 
        "duration_seconds": duration,
        "ended_at": ended_at
    })


@router.get("/api/mode-timer/status")
async def get_mode_timer_status():
    """Get current timer status for all modes."""
    sb = get_supabase_client()
    
    # Get active sessions from Supabase
    active_result = sb.table("mode_sessions").select("mode, id, started_at").is_("ended_at", "null").execute()
    
    active = {}
    for session in active_result.data or []:
        try:
            start_time = datetime.fromisoformat(session["started_at"].replace("Z", "+00:00").replace("+00:00", ""))
            elapsed = int((datetime.now() - start_time).total_seconds())
            active[session["mode"]] = {
                "session_id": session["id"],
                "started_at": session["started_at"],
                "elapsed_seconds": elapsed
            }
        except:
            pass
    
    return JSONResponse({"active_sessions": active})


@router.get("/api/mode-timer/stats")
async def get_mode_timer_stats(days: int = 7):
    """Get time statistics for all modes."""
    sb = get_supabase_client()
    
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get all sessions with duration from Supabase
    sessions_result = sb.table("mode_sessions").select("mode, duration_seconds, date").gte("date", cutoff).not_.is_("duration_seconds", "null").execute()
    
    # Process into stats
    mode_stats = {}
    today_stats = {}
    
    for s in sessions_result.data or []:
        mode = s["mode"]
        duration = s["duration_seconds"] or 0
        date = s["date"]
        
        # Aggregate by mode
        if mode not in mode_stats:
            mode_stats[mode] = {"total_seconds": 0, "session_count": 0, "durations": []}
        mode_stats[mode]["total_seconds"] += duration
        mode_stats[mode]["session_count"] += 1
        mode_stats[mode]["durations"].append(duration)
        
        # Today's stats
        if date == today:
            if mode not in today_stats:
                today_stats[mode] = {"total_seconds": 0, "session_count": 0}
            today_stats[mode]["total_seconds"] += duration
            today_stats[mode]["session_count"] += 1
    
    result = {
        "period_days": days,
        "modes": {},
        "today": {}
    }
    
    for mode, data in mode_stats.items():
        avg_seconds = int(sum(data["durations"]) / len(data["durations"])) if data["durations"] else 0
        result["modes"][mode] = {
            "session_count": data["session_count"],
            "total_seconds": data["total_seconds"],
            "avg_session_seconds": avg_seconds,
            "total_formatted": _format_duration(data["total_seconds"]),
            "avg_formatted": _format_duration(avg_seconds)
        }
    
    for mode, data in today_stats.items():
        result["today"][mode] = {
            "total_seconds": data["total_seconds"],
            "session_count": data["session_count"],
            "total_formatted": _format_duration(data["total_seconds"])
        }
    
    return JSONResponse(result)
