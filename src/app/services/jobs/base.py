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


__all__ = [
    "JobConfig",
    "JOB_CONFIGS",
    "get_supabase",
    "get_settings_repo",
    "get_notifications_repo",
]
