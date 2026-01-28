# src/app/services/jobs/base.py
"""
Background Jobs Base Module

Job configuration and shared utilities.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import logging

from ...infrastructure.supabase_client import get_supabase_client
from ...repositories import get_settings_repository, get_notifications_repository

logger = logging.getLogger(__name__)


@dataclass
class JobConfig:
    """Configuration for a background job."""
    name: str
    description: str
    schedule: str  # cron expression or description
    enabled: bool = True


# Job configuration registry
JOB_CONFIGS: Dict[str, JobConfig] = {
    "one_on_one_prep": JobConfig(
        name="1:1 Prep Digest",
        description="Biweekly prep for manager 1:1 meeting",
        schedule="0 7 * * 2",  # Every Tuesday at 7 AM
        enabled=True,
    ),
    "stale_ticket_alert": JobConfig(
        name="Stale Ticket Alert",
        description="Alert for tickets with no activity",
        schedule="0 9 * * 1-5",  # Weekdays at 9 AM
        enabled=True,
    ),
    "grooming_match": JobConfig(
        name="Grooming-to-Ticket Match",
        description="Match grooming meetings to tickets",
        schedule="0 * * * *",  # Every hour
        enabled=True,
    ),
    "sprint_mode_detect": JobConfig(
        name="Sprint Mode Auto-Detect",
        description="Suggest mode based on sprint cadence",
        schedule="0 8 * * *",  # Daily at 8 AM
        enabled=True,
    ),
    "overdue_encouragement": JobConfig(
        name="Overdue Task Encouragement",
        description="Send encouraging gut-check when overdue on tasks",
        schedule="0 14,17 * * 1-5",  # Weekdays at 2 PM and 5 PM
        enabled=True,
    ),
}


def get_supabase():
    """Get Supabase client."""
    return get_supabase_client()


def get_settings_repo():
    """Get settings repository (lazy load)."""
    try:
        return get_settings_repository()
    except Exception:
        return None


def get_notifications_repo():
    """Get notifications repository (lazy load)."""
    try:
        return get_notifications_repository()
    except Exception:
        return None


# =============================================================================
# JOB RUNNER FUNCTIONS
# =============================================================================

def run_job(job_name: str) -> Dict[str, Any]:
    """
    Run a specific background job by name.
    
    Args:
        job_name: One of 'one_on_one_prep', 'stale_ticket_alert', 
                  'grooming_match', 'sprint_mode_detect', 'overdue_encouragement'
    
    Returns:
        Job result dict
    """
    # Import here to avoid circular imports
    from .one_on_one_prep import OneOnOnePrepJob
    from .sprint_mode import SprintModeDetectJob
    from .stale_alerts import StaleTicketAlertJob
    from .grooming_match import GroomingMatchJob
    from .overdue_encouragement import OverdueEncouragementJob
    
    jobs = {
        "one_on_one_prep": OneOnOnePrepJob,
        "sprint_mode_detect": SprintModeDetectJob,
        "stale_ticket_alert": StaleTicketAlertJob,
        "grooming_match": GroomingMatchJob,
        "overdue_encouragement": OverdueEncouragementJob,
    }
    
    if job_name not in jobs:
        raise ValueError(f"Unknown job: {job_name}. Available: {list(jobs.keys())}")
    
    job_class = jobs[job_name]
    job = job_class()
    
    return job.run()


def run_all_due_jobs() -> list:
    """
    Run all jobs that are due based on their schedules.
    
    Returns:
        List of job results
    """
    from datetime import datetime
    
    # Import here to avoid circular imports
    from .one_on_one_prep import OneOnOnePrepJob
    from .sprint_mode import SprintModeDetectJob
    from .stale_alerts import StaleTicketAlertJob
    from .grooming_match import GroomingMatchJob
    
    results = []
    
    # Check 1:1 prep (biweekly Tuesday)
    one_on_one = OneOnOnePrepJob()
    if one_on_one.should_run_today():
        results.append({
            "job": "one_on_one_prep",
            "result": one_on_one.run(),
        })
    
    # Sprint mode runs daily
    sprint_mode = SprintModeDetectJob()
    results.append({
        "job": "sprint_mode_detect",
        "result": sprint_mode.run(),
    })
    
    # Stale ticket alert runs daily on weekdays
    today = datetime.now()
    if today.weekday() < 5:  # Monday-Friday
        stale_alert = StaleTicketAlertJob()
        results.append({
            "job": "stale_ticket_alert",
            "result": stale_alert.run(),
        })
    
    # Grooming match runs hourly (always check)
    grooming_match = GroomingMatchJob()
    match_result = grooming_match.run()
    if match_result.get("matches"):
        results.append({
            "job": "grooming_match",
            "result": match_result,
        })
    
    return results


__all__ = [
    "JobConfig",
    "JOB_CONFIGS",
    "get_supabase",
    "get_settings_repo",
    "get_notifications_repo",
    "run_job",
    "run_all_due_jobs",
]
