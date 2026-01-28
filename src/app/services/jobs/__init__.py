# src/app/services/jobs/__init__.py
"""
Background Jobs Module - Phase F4

Scheduled jobs that generate proactive notifications:
- F4a: 1:1 Prep Digest (biweekly Tuesday 7 AM)
- F4b: Stale Ticket/Blocker Alert (daily 9 AM weekdays)
- F4c: Grooming-to-Ticket Match (hourly)
- F4d: Sprint Mode Auto-Detect (daily)
- F4f: Overdue Task Encouragement (weekdays 2 PM, 5 PM)

Jobs create notifications via NotificationQueue service.
Can be triggered manually via CLI or scheduled via cron/APScheduler.
"""

from .base import JobConfig, JOB_CONFIGS, run_job, run_all_due_jobs
from .one_on_one_prep import OneOnOnePrepJob
from .sprint_mode import SprintModeDetectJob
from .stale_alerts import StaleTicketAlertJob
from .grooming_match import GroomingMatchJob
from .overdue_encouragement import OverdueEncouragementJob

__all__ = [
    # Configuration
    "JobConfig",
    "JOB_CONFIGS",
    # Job classes
    "OneOnOnePrepJob",
    "SprintModeDetectJob",
    "StaleTicketAlertJob",
    "GroomingMatchJob",
    "OverdueEncouragementJob",
    # Runner functions
    "run_job",
    "run_all_due_jobs",
]
