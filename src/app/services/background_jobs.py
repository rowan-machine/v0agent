# src/app/services/background_jobs.py
"""
Background Jobs Service - Phase F4

Scheduled jobs that generate proactive notifications:
- F4a: 1:1 Prep Digest (biweekly Tuesday 7 AM)
- F4b: Stale Ticket/Blocker Alert (daily 9 AM weekdays)
- F4c: Grooming-to-Ticket Match (hourly)
- F4d: Sprint Mode Auto-Detect (daily)

Jobs create notifications via NotificationQueue service.
Can be triggered manually via CLI or scheduled via cron/APScheduler.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ..db import connect
from .notification_queue import (
    NotificationQueue,
    NotificationType,
    NotificationPriority,
    Notification,
)

logger = logging.getLogger(__name__)


# =============================================================================
# JOB CONFIGURATION
# =============================================================================

@dataclass
class JobConfig:
    """Configuration for a background job."""
    name: str
    description: str
    schedule: str  # cron expression or description
    enabled: bool = True


JOB_CONFIGS = {
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
}


# =============================================================================
# F4a: 1:1 PREP DIGEST
# =============================================================================

class OneOnOnePrepJob:
    """
    Generate 1:1 prep digest answering:
    1. What are my top 3 things I'm currently working on?
    2. Where do I need help? (blockers)
    3. What are my recent observations and feedback to discuss?
    
    Schedule: Biweekly Tuesday 7 AM
    Next run: Jan 27, 2026
    """
    
    # Biweekly schedule - runs on odd weeks (Jan 27 is week 5 of 2026)
    BIWEEKLY_START = datetime(2026, 1, 27)  # First 1:1 date
    
    def __init__(self, queue: Optional[NotificationQueue] = None):
        self.queue = queue or NotificationQueue()
    
    def should_run_today(self) -> bool:
        """Check if today is a biweekly Tuesday."""
        today = datetime.now()
        
        # Must be Tuesday
        if today.weekday() != 1:  # 0=Mon, 1=Tue
            return False
        
        # Check if this is a biweekly Tuesday (every 2 weeks from start date)
        days_since_start = (today.date() - self.BIWEEKLY_START.date()).days
        weeks_since_start = days_since_start // 7
        
        return weeks_since_start % 2 == 0
    
    def run(self) -> Dict[str, Any]:
        """
        Generate the 1:1 prep digest notification.
        
        Returns:
            Dict with notification_id and digest content
        """
        logger.info("Running 1:1 Prep Digest job")
        
        # Gather data for the digest
        top_work_items = self._get_top_work_items()
        blockers = self._get_blockers()
        observations = self._get_observations()
        overdue_actions = self._get_overdue_actions()
        
        # Build the digest body
        body = self._format_digest(
            top_work_items=top_work_items,
            blockers=blockers,
            observations=observations,
            overdue_actions=overdue_actions,
        )
        
        # Calculate next 1:1 date
        next_one_on_one = self._get_next_one_on_one_date()
        
        # Create notification
        notification = Notification(
            notification_type=NotificationType.COACH_RECOMMENDATION,
            title="📋 1:1 Prep Ready",
            body=body[:500],  # Truncate for notification preview
            data={
                "type": "one_on_one_prep",
                "next_meeting": next_one_on_one.isoformat(),
                "top_work_items": top_work_items,
                "blockers": blockers,
                "observations": observations,
                "overdue_actions": overdue_actions,
                "generated_at": datetime.now().isoformat(),
            },
            priority=NotificationPriority.HIGH,
            expires_at=next_one_on_one + timedelta(days=1),
        )
        
        notification_id = self.queue.create(notification)
        
        logger.info(f"Created 1:1 prep notification: {notification_id}")
        
        return {
            "notification_id": notification_id,
            "next_one_on_one": next_one_on_one.isoformat(),
            "top_work_items": top_work_items,
            "blockers": blockers,
            "observations": observations,
            "overdue_actions": overdue_actions,
        }
    
    def _get_top_work_items(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get top active tickets ordered by recent activity."""
        with connect() as conn:
            rows = conn.execute("""
                SELECT id, title, status, tags, updated_at, created_at
                FROM tickets
                WHERE status NOT IN ('done', 'closed', 'archived')
                ORDER BY 
                    COALESCE(updated_at, created_at) DESC
                LIMIT ?
            """, (limit,)).fetchall()
        
        items = []
        for row in rows:
            items.append({
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "tags": row["tags"],
                "last_activity": row["updated_at"] or row["created_at"],
            })
        
        return items
    
    def _get_blockers(self, days: int = 14) -> List[Dict[str, Any]]:
        """Get blockers from recent meetings and tickets."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        blockers = []
        
        with connect() as conn:
            # Get blockers from meeting signals
            meetings = conn.execute("""
                SELECT id, meeting_name, meeting_date, signals_json
                FROM meeting_summaries
                WHERE signals_json IS NOT NULL
                AND COALESCE(meeting_date, created_at) >= ?
                ORDER BY COALESCE(meeting_date, created_at) DESC
            """, (cutoff,)).fetchall()
            
            for meeting in meetings:
                signals = json.loads(meeting["signals_json"] or "{}")
                for blocker in signals.get("blockers", []):
                    if isinstance(blocker, str):
                        blockers.append({
                            "text": blocker,
                            "source": f"Meeting: {meeting['meeting_name']}",
                            "meeting_id": meeting["id"],
                            "date": meeting["meeting_date"],
                        })
                    elif isinstance(blocker, dict):
                        blockers.append({
                            "text": blocker.get("text", str(blocker)),
                            "source": f"Meeting: {meeting['meeting_name']}",
                            "meeting_id": meeting["id"],
                            "date": meeting["meeting_date"],
                        })
            
            # Get tickets with blocked status
            blocked_tickets = conn.execute("""
                SELECT id, title, status
                FROM tickets
                WHERE status = 'blocked'
                OR tags LIKE '%blocked%'
            """).fetchall()
            
            for ticket in blocked_tickets:
                blockers.append({
                    "text": ticket["title"],
                    "source": f"Ticket #{ticket['id']}",
                    "ticket_id": ticket["id"],
                })
        
        return blockers[:10]  # Limit to top 10
    
    def _get_observations(self, days: int = 14) -> List[Dict[str, Any]]:
        """Get decisions, risks, and ideas from recent meetings."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        observations = []
        
        with connect() as conn:
            meetings = conn.execute("""
                SELECT id, meeting_name, meeting_date, signals_json
                FROM meeting_summaries
                WHERE signals_json IS NOT NULL
                AND COALESCE(meeting_date, created_at) >= ?
                ORDER BY COALESCE(meeting_date, created_at) DESC
                LIMIT 10
            """, (cutoff,)).fetchall()
            
            for meeting in meetings:
                signals = json.loads(meeting["signals_json"] or "{}")
                
                # Collect decisions
                for decision in signals.get("decisions", [])[:2]:
                    text = decision if isinstance(decision, str) else decision.get("text", str(decision))
                    observations.append({
                        "type": "decision",
                        "text": text,
                        "source": meeting["meeting_name"],
                        "meeting_id": meeting["id"],
                    })
                
                # Collect risks
                for risk in signals.get("risks", [])[:2]:
                    text = risk if isinstance(risk, str) else risk.get("text", str(risk))
                    observations.append({
                        "type": "risk",
                        "text": text,
                        "source": meeting["meeting_name"],
                        "meeting_id": meeting["id"],
                    })
                
                # Collect ideas
                for idea in signals.get("ideas", [])[:1]:
                    text = idea if isinstance(idea, str) else idea.get("text", str(idea))
                    observations.append({
                        "type": "idea",
                        "text": text,
                        "source": meeting["meeting_name"],
                        "meeting_id": meeting["id"],
                    })
        
        return observations[:10]
    
    def _get_overdue_actions(self) -> List[Dict[str, Any]]:
        """Get action items that appear overdue based on date patterns."""
        overdue = []
        today = datetime.now()
        
        # Date patterns to look for
        date_patterns = [
            (r'by\s+(monday|tuesday|wednesday|thursday|friday)', 'weekday'),
            (r'by\s+eod', 'eod'),
            (r'by\s+end\s+of\s+(day|week)', 'eod_eow'),
            (r'due\s+(\d{1,2}/\d{1,2})', 'date'),
        ]
        
        with connect() as conn:
            meetings = conn.execute("""
                SELECT id, meeting_name, meeting_date, signals_json
                FROM meeting_summaries
                WHERE signals_json IS NOT NULL
                ORDER BY COALESCE(meeting_date, created_at) DESC
                LIMIT 20
            """).fetchall()
            
            for meeting in meetings:
                signals = json.loads(meeting["signals_json"] or "{}")
                meeting_date = meeting["meeting_date"]
                
                for action in signals.get("action_items", []):
                    text = action if isinstance(action, str) else action.get("text", str(action))
                    text_lower = text.lower()
                    
                    # Check for date patterns that suggest it might be overdue
                    is_overdue = False
                    for pattern, pattern_type in date_patterns:
                        if re.search(pattern, text_lower):
                            # If meeting was > 7 days ago, likely overdue
                            if meeting_date:
                                try:
                                    meeting_dt = datetime.fromisoformat(meeting_date)
                                    if (today - meeting_dt).days > 7:
                                        is_overdue = True
                                except:
                                    pass
                            break
                    
                    if is_overdue:
                        overdue.append({
                            "text": text,
                            "source": meeting["meeting_name"],
                            "meeting_id": meeting["id"],
                            "meeting_date": meeting_date,
                        })
        
        return overdue[:5]
    
    def _format_digest(
        self,
        top_work_items: List[Dict],
        blockers: List[Dict],
        observations: List[Dict],
        overdue_actions: List[Dict],
    ) -> str:
        """Format the digest as readable text."""
        lines = ["**1:1 Prep Digest**\n"]
        
        # Top 3 work items
        lines.append("**What am I working on?**")
        if top_work_items:
            for i, item in enumerate(top_work_items, 1):
                lines.append(f"{i}. {item['title']} ({item['status']})")
        else:
            lines.append("- No active tickets found")
        lines.append("")
        
        # Blockers
        lines.append("**Where do I need help?**")
        if blockers:
            for blocker in blockers[:3]:
                lines.append(f"- {blocker['text'][:100]}")
                lines.append(f"  _from {blocker['source']}_")
        else:
            lines.append("- No blockers identified ✅")
        lines.append("")
        
        # Observations
        lines.append("**Recent observations/feedback:**")
        if observations:
            for obs in observations[:5]:
                emoji = {"decision": "✅", "risk": "⚠️", "idea": "💡"}.get(obs["type"], "•")
                lines.append(f"{emoji} {obs['text'][:80]}")
        else:
            lines.append("- No notable observations")
        lines.append("")
        
        # Overdue actions
        if overdue_actions:
            lines.append("**⚠️ Potentially overdue:**")
            for action in overdue_actions[:3]:
                lines.append(f"- {action['text'][:80]}")
        
        return "\n".join(lines)
    
    def _get_next_one_on_one_date(self) -> datetime:
        """Calculate the next 1:1 meeting date."""
        today = datetime.now()
        
        # Find next Tuesday
        days_until_tuesday = (1 - today.weekday()) % 7
        if days_until_tuesday == 0 and today.hour >= 12:
            days_until_tuesday = 7
        
        next_tuesday = today + timedelta(days=days_until_tuesday)
        
        # Check if it's a biweekly Tuesday
        days_since_start = (next_tuesday.date() - self.BIWEEKLY_START.date()).days
        weeks_since_start = days_since_start // 7
        
        if weeks_since_start % 2 != 0:
            next_tuesday += timedelta(days=7)
        
        return next_tuesday.replace(hour=9, minute=0, second=0, microsecond=0)


# =============================================================================
# F4d: SPRINT MODE AUTO-DETECT
# =============================================================================

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
        with connect() as conn:
            row = conn.execute("""
                SELECT value FROM settings WHERE key = 'workflow_mode'
            """).fetchone()
        
        if row:
            return row["value"]
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


# =============================================================================
# JOB RUNNER
# =============================================================================

def run_job(job_name: str) -> Dict[str, Any]:
    """
    Run a specific background job by name.
    
    Args:
        job_name: One of 'one_on_one_prep', 'stale_ticket_alert', 
                  'grooming_match', 'sprint_mode_detect'
    
    Returns:
        Job result dict
    """
    jobs = {
        "one_on_one_prep": OneOnOnePrepJob,
        "sprint_mode_detect": SprintModeDetectJob,
        # F4b and F4c to be added
    }
    
    if job_name not in jobs:
        raise ValueError(f"Unknown job: {job_name}. Available: {list(jobs.keys())}")
    
    job_class = jobs[job_name]
    job = job_class()
    
    return job.run()


def run_all_due_jobs() -> List[Dict[str, Any]]:
    """
    Run all jobs that are due based on their schedules.
    
    Returns:
        List of job results
    """
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
    
    return results
