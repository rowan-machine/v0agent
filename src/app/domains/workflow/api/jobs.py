# src/app/domains/workflow/api/jobs.py
"""
Background Jobs API Routes

Manages background job execution and listing.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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
    from ....services.background_jobs import run_job, JOB_CONFIGS
    
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
    from ....services.background_jobs import JOB_CONFIGS
    
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
        from ....services.scheduler import get_scheduler, get_next_job_runs
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
