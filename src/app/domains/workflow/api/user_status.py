"""
User status API routes for the workflow domain.

Handles user status updates with AI interpretation and current status retrieval.
Extracted from main.py during Phase 2.9 refactoring.
"""
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ....repositories import get_settings_repository

router = APIRouter()

# Repository instance
settings_repo = get_settings_repository()


@router.post("/api/user-status/update")
async def update_user_status(request: Request):
    """
    AI-interpret user status and auto-start timer.

    Migration Note (P1.8): Uses ArjunaAgent adapter for status interpretation.
    Lazy imports ensure backward compatibility.
    """
    # Lazy import for backward compatibility
    from ....agents.arjuna import interpret_user_status_adapter

    data = await request.json()
    status_text = data.get("status", "").strip()

    if not status_text:
        return JSONResponse({"error": "Status text required"}, status_code=400)

    # Use ArjunaAgent adapter for AI interpretation
    interpreted = await interpret_user_status_adapter(status_text)
    mode = interpreted.get("mode", "implementation")
    activity = interpreted.get("activity", status_text)
    context_str = interpreted.get("context", "")

    # Save status using settings repository
    settings_repo.set_user_status(status_text, mode, activity, context_str)

    # Auto-start timer for the interpreted mode
    # First stop any active timers
    active_sessions = settings_repo.get_active_sessions()

    ended_at = datetime.now().isoformat()
    for session in active_sessions:
        try:
            start_time = datetime.fromisoformat(
                session["started_at"].replace("Z", "+00:00").replace("+00:00", "")
            )
            duration = int((datetime.now() - start_time).total_seconds())
            settings_repo.end_session(session["id"], ended_at, duration)
        except:
            pass

    # Start new timer
    today = datetime.now().strftime("%Y-%m-%d")
    started_at = datetime.now().isoformat()

    settings_repo.start_session(mode, started_at, today, activity)

    return JSONResponse({
        "status": "ok",
        "interpreted": {"mode": mode, "activity": activity, "context": context_str},
    })


@router.get("/api/user-status/current")
async def get_current_status():
    """Get current user status."""
    status = settings_repo.get_current_user_status()

    if not status:
        return JSONResponse({"status": None})

    return JSONResponse({
        "status": {
            "text": status.get("status_text"),
            "mode": status.get("interpreted_mode"),
            "activity": status.get("interpreted_activity"),
            "context": status.get("interpreted_context"),
            "created_at": status.get("created_at"),
        }
    })


@router.post("/api/mode-timer/calculate-stats")
async def calculate_mode_statistics():
    """Calculate and store mode statistics for analytics."""
    from datetime import timedelta

    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")

    # Calculate daily and weekly stats for each mode using settings repository
    for mode in ["grooming", "planning", "standup", "implementation"]:
        # Get daily sessions
        daily_sessions = settings_repo.get_sessions_for_date(mode, today)

        if daily_sessions:
            daily_total = sum(s["duration_seconds"] for s in daily_sessions)
            daily_count = len(daily_sessions)
            daily_avg = int(daily_total / daily_count) if daily_count > 0 else 0

            settings_repo.upsert_statistics(mode, "daily", today, daily_total, daily_count, daily_avg)

        # Get weekly sessions
        weekly_sessions = settings_repo.get_sessions_since_date(mode, week_start)

        if weekly_sessions:
            weekly_total = sum(s["duration_seconds"] for s in weekly_sessions)
            weekly_count = len(weekly_sessions)
            weekly_avg = int(weekly_total / weekly_count) if weekly_count > 0 else 0

            settings_repo.upsert_statistics(mode, "weekly", week_start, weekly_total, weekly_count, weekly_avg)

    return JSONResponse({"status": "ok", "calculated_at": datetime.now().isoformat()})
