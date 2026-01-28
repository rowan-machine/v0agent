# src/app/services/background_jobs.py
"""
Background Jobs Service - Phase F4

DEPRECATED: This module re-exports from src/app/services/jobs/ for backward compatibility.
Import directly from src.app.services.jobs instead.

Scheduled jobs that generate proactive notifications:
- F4a: 1:1 Prep Digest (biweekly Tuesday 7 AM)
- F4b: Stale Ticket/Blocker Alert (daily 9 AM weekdays)
- F4c: Grooming-to-Ticket Match (hourly)
- F4d: Sprint Mode Auto-Detect (daily)
- F4f: Overdue Task Encouragement (weekdays 2 PM, 5 PM)

Jobs create notifications via NotificationQueue service.
Can be triggered manually via CLI or scheduled via cron/APScheduler.
"""

# Re-export from new modular structure for backward compatibility
from .jobs import (
    JobConfig,
    JOB_CONFIGS,
    OneOnOnePrepJob,
    SprintModeDetectJob,
    StaleTicketAlertJob,
    GroomingMatchJob,
    OverdueEncouragementJob,
    run_job,
    run_all_due_jobs,
)

__all__ = [
    "JobConfig",
    "JOB_CONFIGS",
    "OneOnOnePrepJob",
    "SprintModeDetectJob",
    "StaleTicketAlertJob",
    "GroomingMatchJob",
    "OverdueEncouragementJob",
    "run_job",
    "run_all_due_jobs",
]
