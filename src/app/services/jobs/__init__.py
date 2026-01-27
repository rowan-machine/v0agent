# src/app/services/jobs/__init__.py
"""
Background Jobs Package

Organized job modules for different notification types.

MIGRATION STATUS:
- base.py: Job configuration and base utilities ✅
- one_on_one.py: 1:1 prep digest job
- stale_tickets.py: Stale ticket/blocker alerts
- grooming_match.py: Grooming-to-ticket matching
- sprint_mode.py: Sprint mode auto-detection
- overdue.py: Overdue task encouragement

For now, re-exports from the original background_jobs.py for compatibility.
"""

from dataclasses import dataclass
from typing import Dict, Any, List

# Re-export from original module
from ..background_jobs import (
    JOB_CONFIGS,
    JobConfig,
    OneOnOnePrepJob,
    StaleTicketAlertJob,
    GroomingMatchJob,
    SprintModeDetectJob,
    OverdueEncouragementJob,
    run_job,
    run_all_due_jobs,
)

__all__ = [
    "JOB_CONFIGS",
    "JobConfig",
    "OneOnOnePrepJob",
    "StaleTicketAlertJob",
    "GroomingMatchJob",
    "SprintModeDetectJob",
    "OverdueEncouragementJob",
    "run_job",
    "run_all_due_jobs",
]
