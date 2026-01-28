# src/app/services/jobs/sprint_mode.py
"""
F4d: Sprint Mode Auto-Detect Job

Auto-detect sprint phase and suggest mode change.

Sprint cadence (2-week sprints starting Monday):
- Wed/Thu before sprint start: Mode A (Context Distillation / Prep)
- Mon-Tue of sprint week 1: Mode B (Execution ramp-up)
- Wed-Fri week 1, Mon-Wed week 2: Mode C (Deep execution)
- Thu-Fri week 2: Mode D (Wrap-up / Demo prep)

Schedule: Daily at 8 AM
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ...repositories import get_settings_repository
from ..notification_queue import (
    NotificationQueue,
    NotificationType,
    NotificationPriority,
    Notification,
)

logger = logging.getLogger(__name__)


def _get_settings_repo():
    """Get settings repository (lazy load)."""
    try:
        return get_settings_repository()
    except Exception:
        return None


class SprintModeDetectJob:
    """
    Auto-detect sprint phase and suggest mode change.
    
    Sprint cadence (2-week sprints starting Monday):
    - Wed/Thu before sprint start: Mode A (Context Distillation / Prep)
    - Mon-Tue of sprint week 1: Mode B (Execution ramp-up)
    - Wed-Fri week 1, Mon-Wed week 2: Mode C (Deep execution)
    - Thu-Fri week 2: Mode D (Wrap-up / Demo prep)
    
    Schedule: Daily at 8 AM
    """
    
    # Sprint start dates (Mondays) - configure based on team calendar
    # Assuming 2-week sprints starting Jan 6, 2026
    SPRINT_EPOCH = datetime(2026, 1, 6)  # First sprint start
    SPRINT_LENGTH_DAYS = 14
    
    MODES = {
        "A": {
            "name": "Context Distillation",
            "description": "Pre-sprint prep: review backlog, refine tickets, distill context",
            "days_before_sprint": [3, 4],  # Wed, Thu before Monday
        },
        "B": {
            "name": "Execution Ramp-up",
            "description": "Sprint start: pick up tickets, clarify requirements",
            "sprint_days": [0, 1],  # Mon, Tue of week 1
        },
        "C": {
            "name": "Deep Execution",
            "description": "Core sprint work: focused coding, minimal meetings",
            "sprint_days": [2, 3, 4, 7, 8, 9],  # Wed-Fri week 1, Mon-Wed week 2
        },
        "D": {
            "name": "Wrap-up",
            "description": "Sprint end: finish PRs, prep demo, retrospective",
            "sprint_days": [10, 11],  # Thu-Fri week 2
        },
    }
    
    def __init__(self, queue: Optional[NotificationQueue] = None):
        self.queue = queue or NotificationQueue()
    
    def get_current_sprint_info(self) -> Dict[str, Any]:
        """Get information about the current sprint."""
        today = datetime.now()
        
        days_since_epoch = (today.date() - self.SPRINT_EPOCH.date()).days
        current_sprint_number = days_since_epoch // self.SPRINT_LENGTH_DAYS + 1
        day_of_sprint = days_since_epoch % self.SPRINT_LENGTH_DAYS
        
        # Calculate sprint start and end
        sprint_start = self.SPRINT_EPOCH + timedelta(
            days=(current_sprint_number - 1) * self.SPRINT_LENGTH_DAYS
        )
        sprint_end = sprint_start + timedelta(days=self.SPRINT_LENGTH_DAYS - 1)
        
        # Days until next sprint
        next_sprint_start = sprint_start + timedelta(days=self.SPRINT_LENGTH_DAYS)
        days_until_next_sprint = (next_sprint_start.date() - today.date()).days
        
        return {
            "sprint_number": current_sprint_number,
            "day_of_sprint": day_of_sprint,
            "sprint_start": sprint_start.date().isoformat(),
            "sprint_end": sprint_end.date().isoformat(),
            "days_until_next_sprint": days_until_next_sprint,
            "next_sprint_start": next_sprint_start.date().isoformat(),
        }
    
    def detect_suggested_mode(self) -> str:
        """Detect the suggested mode based on sprint cadence.
        
        Sprint is 0-indexed (0-13 for 14 days):
        - Days 0-1 (Mon-Tue week 1): Mode B - Ramp-up
        - Days 2-4 (Wed-Fri week 1): Mode C - Deep execution
        - Days 5-6 (Sat-Sun week 1): Weekend (defaults to C)
        - Days 7-8 (Mon-Tue week 2): Mode C - Deep execution continues
        - Day 9 (Wed week 2): Mode D - Early wrap-up
        - Day 10 (Thu week 2): Mode D - Wrap-up
        - Day 11+ (Fri-Sun week 2): Mode A - Prep for next sprint
        
        The key insight: near end of sprint, transition to prep mode.
        """
        sprint_info = self.get_current_sprint_info()
        day_of_sprint = sprint_info["day_of_sprint"]
        days_until_next = sprint_info["days_until_next_sprint"]
        
        # If 3-4 days until next sprint, we're in prep mode
        if days_until_next <= 4:
            return "A"
        
        # Check day_of_sprint for mode detection
        if day_of_sprint in [0, 1]:
            return "B"  # Mon, Tue of week 1
        elif day_of_sprint in [2, 3, 4, 7, 8]:
            return "C"  # Wed-Fri week 1, Mon-Tue week 2
        elif day_of_sprint in [9, 10]:
            return "D"  # Wed-Thu week 2 (wrap-up)
        else:
            # Weekend or late sprint
            return "C"  # Default to execution
    
    def get_current_mode(self) -> Optional[str]:
        """Get the currently set mode from settings."""
        repo = _get_settings_repo()
        if repo:
            return repo.get_setting("workflow_mode")
        return None
    
    def run(self) -> Dict[str, Any]:
        """
        Check sprint phase and create notification if mode change suggested.
        
        Returns:
            Dict with sprint info and suggested mode
        """
        logger.info("Running Sprint Mode Auto-Detect job")
        
        sprint_info = self.get_current_sprint_info()
        suggested_mode = self.detect_suggested_mode()
        current_mode = self.get_current_mode()
        
        mode_info = self.MODES.get(suggested_mode, {})
        
        result = {
            "sprint_info": sprint_info,
            "suggested_mode": suggested_mode,
            "suggested_mode_name": mode_info.get("name", "Unknown"),
            "current_mode": current_mode,
            "mode_change_needed": current_mode != suggested_mode,
        }
        
        # Create notification if mode change suggested
        if current_mode and current_mode != suggested_mode:
            notification = Notification(
                notification_type=NotificationType.COACH_RECOMMENDATION,
                title=f"🔄 Mode Change: {mode_info.get('name', suggested_mode)}",
                body=f"Based on sprint cadence, consider switching to Mode {suggested_mode}: {mode_info.get('description', '')}",
                data={
                    "type": "sprint_mode_suggestion",
                    "suggested_mode": suggested_mode,
                    "current_mode": current_mode,
                    "sprint_info": sprint_info,
                    "mode_description": mode_info.get("description", ""),
                },
                priority=NotificationPriority.NORMAL,
                expires_at=datetime.now() + timedelta(days=1),
            )
            
            notification_id = self.queue.create(notification)
            result["notification_id"] = notification_id
            logger.info(f"Created mode change notification: {notification_id}")
        
        return result
