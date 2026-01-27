"""
Workflow Mode and Timer API Routes

Manages workflow modes (A-G), timer sessions, background jobs,
and workflow progress tracking.

Routes:
- /api/settings/mode - Get/set current workflow mode
- /api/settings/mode/suggested - Get suggested mode based on sprint cadence
- /api/settings/mode/expected-duration - Get expected durations per mode
- /api/settings/workflow-progress - Save/get workflow checklist progress
- /api/workflow/check-completion - Check if mode workflow is complete
- /api/workflow/overdue-check - Check overdue status
- /api/workflow/send-encouragement - Trigger encouragement notification
- /api/mode-timer/* - Timer session management
- /api/v1/jobs/* - Background job execution
- /api/v1/tracing/status - LangSmith tracing status
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflow"])


# =============================================================================
# Mode Settings
# =============================================================================

@router.post("/api/settings/mode")
async def set_workflow_mode(request: Request):
    """Save the current workflow mode to Supabase."""
    data = await request.json()
    mode = data.get("mode", "mode-a")
    
    try:
        sb = get_supabase_client()
        if sb:
            sb.table("settings").upsert({
                "key": "current_mode",
                "value": mode
            }, on_conflict="key").execute()
            return JSONResponse({"status": "ok", "mode": mode})
    except Exception as e:
        logger.error(f"Supabase settings save failed: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
    
    return JSONResponse({"status": "ok", "mode": mode})


@router.get("/api/settings/mode")
async def get_workflow_mode():
    """Get the current workflow mode from Supabase."""
    try:
        sb = get_supabase_client()
        if sb:
            result = sb.table("settings").select("value").eq("key", "current_mode").single().execute()
            if result.data:
                return JSONResponse({"mode": result.data["value"]})
    except Exception as e:
        logger.debug(f"Supabase settings read failed: {e}")
    
    return JSONResponse({"mode": "mode-a"})


@router.get("/api/settings/mode/suggested")
async def get_suggested_mode():
    """Get the suggested workflow mode based on sprint cadence.
    
    Uses SprintModeDetectJob logic to suggest A/B/C/D mode.
    Returns suggestion along with sprint context info.
    """
    from ..services.background_jobs import SprintModeDetectJob
    
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


@router.get("/api/settings/mode/expected-duration")
async def get_expected_mode_duration():
    """Get expected duration for each mode based on historical data with defaults.
    
    Returns expected minutes per mode, calculated from historical time tracking
    data with sensible defaults when insufficient data exists.
    """
    sb = get_supabase_client()
    
    # Default expected durations (in minutes) based on typical workflow
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
    
    # Get historical averages from Supabase mode_sessions table
    for mode, default_mins in defaults.items():
        try:
            rows = sb.table("mode_sessions").select("duration_seconds").eq("mode", mode).not_.is_("duration_seconds", "null").gt("duration_seconds", 0).execute().data
            session_count = len(rows) if rows else 0
            
            if session_count >= 3:  # Need at least 3 data points to trust the average
                avg_seconds = sum(r["duration_seconds"] for r in rows) / session_count
                avg_mins = int(avg_seconds / 60)
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
        except:
            result[mode] = {
                "expected_minutes": default_mins,
                "default_minutes": default_mins,
                "historical_sessions": 0,
                "has_sufficient_data": False,
            }
    
    return JSONResponse(result)


# =============================================================================
# AI Model Settings
# =============================================================================

@router.get("/api/settings/ai-model")
async def get_ai_model():
    """Get current AI model setting from Supabase."""
    try:
        sb = get_supabase_client()
        if sb:
            result = sb.table("settings").select("value").eq("key", "ai_model").single().execute()
            if result.data:
                return JSONResponse({"model": result.data["value"]})
    except Exception as e:
        logger.debug(f"Supabase AI model read failed: {e}")
    
    return JSONResponse({"model": "gpt-4o-mini"})


@router.post("/api/settings/ai-model")
async def set_ai_model(request: Request):
    """Set AI model to use in Supabase."""
    data = await request.json()
    model = data.get("model", "gpt-4o-mini")
    
    try:
        sb = get_supabase_client()
        if sb:
            sb.table("settings").upsert({
                "key": "ai_model",
                "value": model
            }, on_conflict="key").execute()
            return JSONResponse({"status": "ok", "model": model})
    except Exception as e:
        logger.error(f"Supabase AI model save failed: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
    
    return JSONResponse({"status": "ok", "model": model})


# =============================================================================
# Workflow Progress
# =============================================================================

@router.post("/api/settings/workflow-progress")
async def save_workflow_progress(request: Request):
    """Save workflow checklist progress for a specific mode."""
    data = await request.json()
    mode = data.get("mode", "mode-a")
    progress = data.get("progress", [])
    
    progress_json = json.dumps(progress)
    key = f"workflow_progress_{mode}"
    
    sb = get_supabase_client()
    sb.table("settings").upsert({
        "key": key,
        "value": progress_json
    }, on_conflict="key").execute()
    
    return JSONResponse({"status": "ok", "mode": mode, "progress": progress})


@router.get("/api/settings/workflow-progress/{mode}")
async def get_workflow_progress(mode: str):
    """Get workflow checklist progress for a specific mode."""
    key = f"workflow_progress_{mode}"
    
    sb = get_supabase_client()
    result = sb.table("settings").select("value").eq("key", key).execute()
    progress = []
    if result.data:
        try:
            progress = json.loads(result.data[0]["value"])
        except:
            progress = []
    
    return JSONResponse({"mode": mode, "progress": progress})


# =============================================================================
# Workflow Completion
# =============================================================================

@router.post("/api/workflow/check-completion")
async def check_workflow_completion(request: Request):
    """Check if a mode's workflow is complete and celebrate if done early.
    
    Creates a celebration notification if:
    1. All checkboxes for the mode are complete
    2. Completed before the expected phase end time
    
    Returns celebration status and creates notification if applicable.
    """
    from ..services.notification_queue import (
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


@router.get("/api/workflow/overdue-check")
async def check_overdue_status():
    """Check if current mode is overdue and get encouragement context.
    
    Returns overdue status and optionally triggers an encouragement notification.
    """
    from ..services.background_jobs import OverdueEncouragementJob
    
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


@router.post("/api/workflow/send-encouragement")
async def send_overdue_encouragement():
    """Manually trigger an overdue encouragement notification."""
    from ..services.background_jobs import OverdueEncouragementJob
    
    job = OverdueEncouragementJob()
    result = job.run()
    
    return JSONResponse(result)


# =============================================================================
# Mode Timer
# =============================================================================

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


# =============================================================================
# Background Jobs API
# =============================================================================

@router.post("/api/v1/jobs/{job_name}/run")
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
    from ..services.background_jobs import run_job, JOB_CONFIGS
    
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


@router.get("/api/v1/jobs")
async def list_background_jobs():
    """List all available background jobs and their schedules."""
    from ..services.background_jobs import JOB_CONFIGS
    
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
        from ..services.scheduler import get_scheduler, get_next_job_runs
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


# =============================================================================
# LangSmith Tracing Status
# =============================================================================

@router.get("/api/v1/tracing/status")
async def get_tracing_status():
    """Debug endpoint to check LangSmith tracing status."""
    tracing_status = {
        "langchain_tracing_v2": os.environ.get("LANGCHAIN_TRACING_V2", "not set"),
        "langsmith_tracing": os.environ.get("LANGSMITH_TRACING", "not set"),
        "langsmith_api_key_set": bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")),
        "langsmith_project": os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "signalflow"),
        "langsmith_endpoint": os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    }
    
    # Check if tracing module is available and enabled
    try:
        from ..tracing import is_tracing_enabled, get_langsmith_client, get_project_name
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
