# src/app/domains/workflow/api/progress.py
"""
Workflow Progress API Routes

Handles workflow checklist progress tracking and completion detection.
"""

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ....infrastructure.supabase_client import get_supabase_client
from .modes import get_expected_mode_duration

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.post("/api/workflow/check-completion")
async def check_workflow_completion(request: Request):
    """Check if a mode's workflow is complete and celebrate if done early.
    
    Creates a celebration notification if:
    1. All checkboxes for the mode are complete
    2. Completed before the expected phase end time
    
    Returns celebration status and creates notification if applicable.
    """
    from ....services.notification_queue import (
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
    from ....services.background_jobs import OverdueEncouragementJob
    
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
    from ....services.background_jobs import OverdueEncouragementJob
    
    job = OverdueEncouragementJob()
    result = job.run()
    
    return JSONResponse(result)
