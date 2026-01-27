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

from ..infrastructure.supabase_client import get_supabase_client
from ..repositories import get_settings_repository, get_notifications_repository
from . import tickets_supabase, meetings_supabase
from .notification_queue import (
    NotificationQueue,
    NotificationType,
    NotificationPriority,
    Notification,
)

logger = logging.getLogger(__name__)

def get_supabase():
    """Get Supabase client."""
    return get_supabase_client()

def _get_settings_repo():
    """Get settings repository (lazy load)."""
    try:
        return get_settings_repository()
    except Exception:
        return None

def _get_notifications_repo():
    """Get notifications repository (lazy load)."""
    try:
        return get_notifications_repository()
    except Exception:
        return None

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
    "overdue_encouragement": JobConfig(
        name="Overdue Task Encouragement",
        description="Send encouraging gut-check when overdue on tasks",
        schedule="0 14,17 * * 1-5",  # Weekdays at 2 PM and 5 PM
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
        """Get top active tickets ordered by recent activity (from Supabase)."""
        all_tickets = tickets_supabase.get_active_tickets()
        
        # Sort by most recent activity
        def get_activity_time(t):
            return t.get("updated_at") or t.get("created_at") or ""
        
        sorted_tickets = sorted(all_tickets, key=get_activity_time, reverse=True)
        
        items = []
        for ticket in sorted_tickets[:limit]:
            items.append({
                "id": ticket["id"],
                "title": ticket.get("title") or "",
                "status": ticket.get("status") or "",
                "tags": ticket.get("tags") or "",
                "last_activity": ticket.get("updated_at") or ticket.get("created_at"),
            })
        
        return items
    
    def _get_blockers(self, days: int = 14) -> List[Dict[str, Any]]:
        """Get blockers from recent meetings and tickets (from Supabase)."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        blockers = []
        
        # Get blockers from meeting signals (Supabase)
        all_meetings = meetings_supabase.get_all_meetings()
        for meeting in all_meetings:
            meeting_date = meeting.get("meeting_date") or meeting.get("created_at") or ""
            if meeting_date < cutoff:
                continue
            
            signals_json = meeting.get("signals_json")
            if not signals_json:
                continue
                
            try:
                signals = json.loads(signals_json) if isinstance(signals_json, str) else signals_json
            except:
                continue
                
            for blocker in signals.get("blockers", []):
                if isinstance(blocker, str):
                    blockers.append({
                        "text": blocker,
                        "source": f"Meeting: {meeting.get('meeting_name', 'Unknown')}",
                        "meeting_id": meeting["id"],
                        "date": meeting.get("meeting_date"),
                    })
                elif isinstance(blocker, dict):
                    blockers.append({
                        "text": blocker.get("text", str(blocker)),
                        "source": f"Meeting: {meeting.get('meeting_name', 'Unknown')}",
                        "meeting_id": meeting["id"],
                        "date": meeting.get("meeting_date"),
                    })
        
        # Get tickets with blocked status (Supabase)
        blocked_tickets = tickets_supabase.get_blocked_tickets()
        for ticket in blocked_tickets:
            blockers.append({
                "text": ticket.get("title") or "",
                "source": f"Ticket #{ticket['id']}",
                "ticket_id": ticket["id"],
            })
        
        return blockers[:10]  # Limit to top 10
    
    def _get_observations(self, days: int = 14) -> List[Dict[str, Any]]:
        """Get decisions, risks, and ideas from recent meetings (from Supabase)."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        observations = []
        
        all_meetings = meetings_supabase.get_all_meetings()
        count = 0
        for meeting in all_meetings:
            if count >= 10:
                break
            meeting_date = meeting.get("meeting_date") or meeting.get("created_at") or ""
            if meeting_date < cutoff:
                continue
            
            signals_json = meeting.get("signals_json")
            if not signals_json:
                continue
            
            try:
                signals = json.loads(signals_json) if isinstance(signals_json, str) else signals_json
            except:
                continue
            
            count += 1
            
            # Collect decisions
            for decision in signals.get("decisions", [])[:2]:
                text = decision if isinstance(decision, str) else decision.get("text", str(decision))
                observations.append({
                    "type": "decision",
                    "text": text,
                    "source": meeting.get("meeting_name") or "Unknown",
                    "meeting_id": meeting["id"],
                })
            
            # Collect risks
            for risk in signals.get("risks", [])[:2]:
                text = risk if isinstance(risk, str) else risk.get("text", str(risk))
                observations.append({
                    "type": "risk",
                    "text": text,
                    "source": meeting.get("meeting_name") or "Unknown",
                    "meeting_id": meeting["id"],
                })
            
            # Collect ideas
            for idea in signals.get("ideas", [])[:1]:
                text = idea if isinstance(idea, str) else idea.get("text", str(idea))
                observations.append({
                    "type": "idea",
                    "text": text,
                    "source": meeting.get("meeting_name") or "Unknown",
                    "meeting_id": meeting["id"],
                })
        
        return observations[:10]
    
    def _get_overdue_actions(self) -> List[Dict[str, Any]]:
        """Get action items that appear overdue based on date patterns (from Supabase)."""
        overdue = []
        today = datetime.now()
        
        # Date patterns to look for
        date_patterns = [
            (r'by\s+(monday|tuesday|wednesday|thursday|friday)', 'weekday'),
            (r'by\s+eod', 'eod'),
            (r'by\s+end\s+of\s+(day|week)', 'eod_eow'),
            (r'due\s+(\d{1,2}/\d{1,2})', 'date'),
        ]
        
        all_meetings = meetings_supabase.get_all_meetings()
        count = 0
        for meeting in all_meetings:
            if count >= 20:
                break
            
            signals_json = meeting.get("signals_json")
            if not signals_json:
                continue
            
            count += 1
            
            try:
                signals = json.loads(signals_json) if isinstance(signals_json, str) else signals_json
            except:
                continue
            
            meeting_date = meeting.get("meeting_date")
            
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
                                meeting_dt = datetime.fromisoformat(meeting_date.replace('Z', '+00:00').replace('+00:00', ''))
                                if (today - meeting_dt).days > 7:
                                    is_overdue = True
                            except:
                                pass
                        break
                
                if is_overdue:
                    overdue.append({
                        "text": text,
                        "source": meeting.get("meeting_name") or "Unknown",
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


# =============================================================================
# JOB RUNNER
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


# =============================================================================
# F4b: STALE TICKET / BLOCKER ALERT
# =============================================================================

class StaleTicketAlertJob:
    """
    F4b: Stale Ticket and Blocker Alert
    
    Triggers when:
    - Ticket has no activity for 5+ days
    - Blocker mentioned but unresolved after 3 days
    - Action item with date pattern is overdue
    
    Schedule: Daily 9:00 AM (weekdays)
    """
    
    STALE_TICKET_DAYS = 5
    STALE_BLOCKER_DAYS = 3
    
    def __init__(self, queue: Optional[NotificationQueue] = None):
        self.queue = queue or NotificationQueue()
    
    def run(self) -> Dict[str, Any]:
        """Check for stale tickets and unresolved blockers."""
        logger.info("Running Stale Ticket Alert job")
        
        stale_tickets = self._get_stale_tickets()
        stale_blockers = self._get_stale_blockers()
        
        alerts = []
        
        # Create notifications for stale tickets
        for ticket in stale_tickets[:5]:  # Max 5 alerts
            notification = Notification(
                notification_type=NotificationType.AI_SUGGESTION,
                priority=NotificationPriority.NORMAL,
                title=f"Stale ticket: {ticket['title'][:40]}",
                body=f"No activity for {ticket['days_stale']} days.\nStatus: {ticket['status']}\nLast update: {ticket['last_activity']}",
                data={
                    "type": "stale_ticket",
                    "ticket_id": ticket["id"],
                    "days_stale": ticket["days_stale"],
                },
                expires_at=datetime.now() + timedelta(days=1),
            )
            notif_id = self.queue.create(notification)
            alerts.append({"type": "stale_ticket", "ticket_id": ticket["id"], "notification_id": notif_id})
        
        # Create notifications for stale blockers
        for blocker in stale_blockers[:3]:  # Max 3 alerts
            notification = Notification(
                notification_type=NotificationType.AI_SUGGESTION,
                priority=NotificationPriority.HIGH,
                title=f"Unresolved blocker ({blocker['days_old']}d)",
                body=f"{blocker['text'][:100]}\n\n_From: {blocker['source']}_",
                data={
                    "type": "stale_blocker",
                    "blocker_text": blocker["text"],
                    "meeting_id": blocker.get("meeting_id"),
                },
                expires_at=datetime.now() + timedelta(days=1),
            )
            notif_id = self.queue.create(notification)
            alerts.append({"type": "stale_blocker", "notification_id": notif_id})
        
        return {
            "stale_tickets_found": len(stale_tickets),
            "stale_blockers_found": len(stale_blockers),
            "alerts_created": len(alerts),
            "alerts": alerts,
        }
    
    def _get_stale_tickets(self) -> List[Dict[str, Any]]:
        """Find tickets with no activity for STALE_TICKET_DAYS (from Supabase)."""
        cutoff = (datetime.now() - timedelta(days=self.STALE_TICKET_DAYS)).isoformat()
        
        stale_tickets = tickets_supabase.get_stale_in_progress_tickets(days=self.STALE_TICKET_DAYS)
        
        stale = []
        for ticket in stale_tickets[:10]:
            last_activity = ticket.get("updated_at") or ticket.get("created_at")
            if last_activity:
                try:
                    days_stale = (datetime.now() - datetime.fromisoformat(last_activity.replace('Z', '+00:00').replace('+00:00', ''))).days
                except:
                    days_stale = self.STALE_TICKET_DAYS
            else:
                days_stale = self.STALE_TICKET_DAYS
            
            stale.append({
                "id": ticket["id"],
                "title": ticket.get("title") or "",
                "status": ticket.get("status") or "",
                "last_activity": last_activity,
                "days_stale": days_stale,
            })
        
        return stale
    
    def _get_stale_blockers(self) -> List[Dict[str, Any]]:
        """Find blockers mentioned in meetings that haven't been resolved (from Supabase)."""
        cutoff_recent = (datetime.now() - timedelta(days=self.STALE_BLOCKER_DAYS)).isoformat()
        cutoff_old = (datetime.now() - timedelta(days=30)).isoformat()  # Don't look more than 30 days back
        
        blockers = []
        
        all_meetings = meetings_supabase.get_all_meetings()
        for meeting in all_meetings:
            meeting_date = meeting.get("meeting_date") or ""
            if not meeting_date or meeting_date < cutoff_old or meeting_date > cutoff_recent:
                continue
            
            signals_json = meeting.get("signals_json")
            if not signals_json:
                continue
                
            try:
                signals = json.loads(signals_json) if isinstance(signals_json, str) else signals_json
                for signal in signals.get("blockers", []):
                    text = signal.get("text", "") if isinstance(signal, dict) else str(signal)
                    if text:
                        if meeting_date:
                            try:
                                days_old = (datetime.now() - datetime.fromisoformat(meeting_date.replace('Z', ''))).days
                            except:
                                days_old = self.STALE_BLOCKER_DAYS
                        else:
                            days_old = self.STALE_BLOCKER_DAYS
                        
                        blockers.append({
                            "text": text,
                            "source": meeting.get("meeting_name") or "Unknown",
                            "meeting_id": meeting["id"],
                            "meeting_date": meeting_date,
                            "days_old": days_old,
                        })
            except json.JSONDecodeError:
                continue
        
        return blockers


# =============================================================================
# F4c: GROOMING-TO-TICKET MATCH ALERT
# =============================================================================

class GroomingMatchJob:
    """
    F4c: Grooming Meeting to Ticket Match Alert
    
    When a new grooming/planning meeting is imported:
    - Find matching tickets based on content similarity
    - Identify gaps: items discussed but not in ticket
    - Create HIGH priority notification for matches
    
    Schedule: Hourly (checks for new grooming meetings)
    """
    
    GROOMING_KEYWORDS = ['grooming', 'planning', 'refinement', 'backlog', 'sprint planning', 'estimation']
    
    def __init__(self, queue: Optional[NotificationQueue] = None):
        self.queue = queue or NotificationQueue()
    
    def run(self) -> Dict[str, Any]:
        """Check for new grooming meetings and match to tickets."""
        logger.info("Running Grooming Match job")
        
        # Find recent grooming meetings (last 2 hours)
        grooming_meetings = self._get_recent_grooming_meetings()
        
        if not grooming_meetings:
            return {"matches": [], "message": "No recent grooming meetings found"}
        
        matches = []
        
        for meeting in grooming_meetings:
            # Find potential ticket matches
            ticket_matches = self._find_matching_tickets(meeting)
            
            if ticket_matches:
                # Create notification
                best_match = ticket_matches[0]
                gaps = self._analyze_gaps(meeting, best_match)
                
                notification = Notification(
                    notification_type=NotificationType.AI_SUGGESTION,
                    priority=NotificationPriority.HIGH,
                    title=f"🎯 Grooming match: {best_match['title'][:35]}",
                    body=self._format_match_body(meeting, best_match, gaps),
                    data={
                        "type": "grooming_match",
                        "meeting_id": meeting["id"],
                        "ticket_id": best_match["id"],
                        "match_score": best_match.get("score", 0),
                        "gaps": gaps,
                    },
                    expires_at=datetime.now() + timedelta(days=3),
                )
                notif_id = self.queue.create(notification)
                
                matches.append({
                    "meeting_id": meeting["id"],
                    "meeting_name": meeting["meeting_name"],
                    "ticket_id": best_match["id"],
                    "ticket_title": best_match["title"],
                    "score": best_match.get("score", 0),
                    "notification_id": notif_id,
                })
                
                # Mark meeting as processed
                self._mark_meeting_processed(meeting["id"])
        
        return {
            "grooming_meetings_checked": len(grooming_meetings),
            "matches": matches,
        }
    
    def _get_recent_grooming_meetings(self) -> List[Dict[str, Any]]:
        """Find grooming meetings from the last 24 hours that haven't been matched yet (from Supabase)."""
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        
        all_meetings = meetings_supabase.get_all_meetings()
        
        # Get processed meeting IDs from notifications table using repository
        processed_ids = set()
        notifications_repo = _get_notifications_repo()
        if notifications_repo:
            notifications = notifications_repo.get_by_type("transcript_match", limit=500)
            for notification in notifications:
                metadata = notification.data or {}
                if metadata.get("meeting_id"):
                    processed_ids.add(metadata["meeting_id"])
        
        results = []
        for meeting in all_meetings:
            created_at = meeting.get("created_at") or ""
            if created_at < cutoff:
                continue
            if meeting["id"] in processed_ids:
                continue
            
            meeting_name = (meeting.get("meeting_name") or "").lower()
            if any(kw in meeting_name for kw in self.GROOMING_KEYWORDS):
                results.append({
                    "id": meeting["id"],
                    "meeting_name": meeting.get("meeting_name") or "",
                    "meeting_date": meeting.get("meeting_date"),
                    "raw_text": meeting.get("raw_text") or "",
                    "signals_json": meeting.get("signals_json"),
                })
                if len(results) >= 5:
                    break
        
        return results
    
    def _find_matching_tickets(self, meeting: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find tickets that match the grooming meeting content (from Supabase)."""
        meeting_text = (meeting.get("raw_text") or "")[:2000].lower()
        meeting_name = (meeting.get("meeting_name") or "").lower()
        
        # Extract key terms from meeting
        # Simple keyword extraction - look for capitalized words, ticket IDs, etc.
        ticket_id_pattern = re.compile(r'\b([A-Z]+-\d+)\b')
        potential_ids = ticket_id_pattern.findall(meeting.get("raw_text") or "")
        
        matches = []
        
        # Get all active tickets from Supabase
        all_tickets = tickets_supabase.get_active_tickets()
        
        # First, check for exact ticket ID matches
        if potential_ids:
            potential_ids_lower = [pid.lower() for pid in potential_ids]
            for ticket in all_tickets:
                ticket_id = (ticket.get("ticket_id") or "").lower()
                if ticket_id in potential_ids_lower:
                    matches.append({
                        "id": ticket["id"],
                        "title": ticket.get("title") or "",
                        "status": ticket.get("status") or "",
                        "description": ticket.get("description") or "",
                        "tags": ticket.get("tags") or "",
                        "score": 100,  # Exact ID match
                        "match_type": "id_match",
                    })
        
        # Then, do fuzzy title matching
        if not matches:
            # Sort by updated_at for recent tickets
            def get_updated(t):
                return t.get("updated_at") or ""
            sorted_tickets = sorted(all_tickets, key=get_updated, reverse=True)[:50]
            
            for ticket in sorted_tickets:
                title = (ticket.get("title") or "").lower()
                desc = (ticket.get("description") or "").lower()
                
                # Simple scoring: count word overlaps
                title_words = set(title.split())
                meeting_words = set(meeting_text.split())
                
                # Remove common words
                common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                               'to', 'of', 'and', 'in', 'that', 'for', 'on', 'with', 'as'}
                title_words -= common_words
                meeting_words -= common_words
                
                overlap = len(title_words & meeting_words)
                
                if overlap >= 2:  # At least 2 significant words overlap
                    score = min(overlap * 15, 80)  # Cap at 80 for fuzzy match
                    matches.append({
                        "id": ticket["id"],
                        "title": ticket.get("title") or "",
                        "status": ticket.get("status") or "",
                        "description": ticket.get("description") or "",
                        "tags": ticket.get("tags") or "",
                        "score": score,
                        "match_type": "keyword_match",
                    })
        
        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        return matches[:3]  # Top 3 matches
    
    def _analyze_gaps(self, meeting: Dict[str, Any], ticket: Dict[str, Any]) -> List[str]:
        """Identify items discussed in meeting but not reflected in ticket."""
        gaps = []
        
        try:
            signals = json.loads(meeting.get("signals_json") or "{}") if meeting.get("signals_json") else {}
        except:
            signals = {}
        
        ticket_text = f"{ticket.get('title', '')} {ticket.get('description', '')}".lower()
        
        # Check if action items from meeting are in ticket
        for action in signals.get("actions", [])[:5]:
            action_text = action.get("text", "") if isinstance(action, dict) else str(action)
            if action_text:
                # Simple check: are key words from action in ticket?
                action_words = set(action_text.lower().split()) - {'the', 'a', 'to', 'and', 'for'}
                if len(action_words) > 2:
                    overlap = sum(1 for w in action_words if w in ticket_text)
                    if overlap < len(action_words) * 0.3:  # Less than 30% overlap
                        gaps.append(f"Action not in ticket: {action_text[:60]}")
        
        # Check for decisions not reflected
        for decision in signals.get("decisions", [])[:3]:
            dec_text = decision.get("text", "") if isinstance(decision, dict) else str(decision)
            if dec_text and dec_text.lower() not in ticket_text:
                gaps.append(f"Decision: {dec_text[:60]}")
        
        return gaps[:5]  # Max 5 gaps
    
    def _format_match_body(self, meeting: Dict, ticket: Dict, gaps: List[str]) -> str:
        """Format the notification body for a grooming match."""
        lines = [
            f"**Meeting:** {meeting['meeting_name']}",
            f"**Matched Ticket:** {ticket['title']}",
            f"**Match Score:** {ticket.get('score', 0)}%",
            f"**Status:** {ticket.get('status', 'unknown')}",
            "",
        ]
        
        if gaps:
            lines.append("**⚠️ Gaps Found:**")
            for gap in gaps[:3]:
                lines.append(f"- {gap}")
        else:
            lines.append("✅ No obvious gaps detected")
        
        return "\n".join(lines)
    
    def _mark_meeting_processed(self, meeting_id: int):
        """Mark meeting as processed to avoid duplicate notifications."""
        # The notification itself serves as the marker via metadata.meeting_id
        pass


# =============================================================================
# F4f: OVERDUE TASK ENCOURAGEMENT
# =============================================================================

class OverdueEncouragementJob:
    """
    Send encouraging gut-check messages when overdue on workflow tasks.
    
    Reviews:
    - Workflow checklist progress vs expected time
    - Ticket implementation plans and task decomposition
    - Generates contextual time-based questions
    
    Schedule: Weekdays at 2 PM and 5 PM
    """
    
    # Expected durations per mode (in minutes) - same as F4e
    MODE_DEFAULTS = {
        "mode-a": 60,   # Context Distillation
        "mode-b": 45,   # Implementation Planning
        "mode-c": 90,   # Assisted Draft Intake
        "mode-d": 60,   # Deep Review
        "mode-e": 30,   # Promotion Readiness
        "mode-f": 20,   # Controlled Sync
        "mode-g": 120,  # Execution
    }
    
    MODE_NAMES = {
        "mode-a": "Context Distillation",
        "mode-b": "Implementation Planning",
        "mode-c": "Assisted Draft Intake",
        "mode-d": "Deep Review & Validation",
        "mode-e": "Promotion Readiness",
        "mode-f": "Controlled Sync",
        "mode-g": "Execution",
    }
    
    # Gut-check question templates per mode
    GUT_CHECK_TEMPLATES = {
        "mode-a": [
            "How's the context gathering going? Found all the files you need?",
            "Are you feeling clear about the scope of what you're working on?",
            "Any dependencies or blockers surfacing that need attention?",
        ],
        "mode-b": [
            "How are you feeling about the implementation approach?",
            "Is the plan coming together, or are there unknowns blocking you?",
            "Any technical decisions you're wrestling with?",
        ],
        "mode-c": [
            "How's the drafting going? Making progress on the structure?",
            "Are you getting good output from the AI assistance?",
            "Any parts feeling stuck or unclear?",
        ],
        "mode-d": [
            "How's the review going? Finding issues or looking clean?",
            "Are you comfortable with the test coverage?",
            "Any edge cases you're worried about?",
        ],
        "mode-e": [
            "Feeling ready for promotion? Anything missing from the checklist?",
            "Is the documentation complete?",
            "Any last-minute concerns before delivery?",
        ],
        "mode-f": [
            "Sync going smoothly? Any merge conflicts or issues?",
            "PR ready for review?",
            "Any dependencies to coordinate?",
        ],
        "mode-g": [
            "How are you feeling about the {task_focus}?",
            "Making progress on the implementation?",
            "Any blockers or questions coming up?",
        ],
    }
    
    def __init__(self, queue: Optional[NotificationQueue] = None):
        self.queue = queue or NotificationQueue()
    
    def run(self) -> Dict[str, Any]:
        """Run the overdue encouragement check."""
        logger.info("Running OverdueEncouragementJob")
        
        result = {
            "notifications_created": 0,
            "mode_checked": None,
            "is_overdue": False,
            "message": "",
        }
        
        try:
            # Get current mode and tracking info
            mode_info = self._get_current_mode_info()
            result["mode_checked"] = mode_info.get("mode")
            
            if not mode_info.get("mode"):
                result["message"] = "No active mode found"
                return result
            
            # Check if overdue
            overdue_info = self._check_if_overdue(mode_info)
            result["is_overdue"] = overdue_info["is_overdue"]
            
            if not overdue_info["is_overdue"]:
                result["message"] = f"Not overdue in {mode_info['mode']}"
                return result
            
            # Get context for encouragement message
            context = self._get_task_context(mode_info)
            
            # Generate encouraging message
            notification = self._create_encouragement_notification(
                mode_info, overdue_info, context
            )
            
            notification_id = self.queue.create(notification)
            result["notifications_created"] = 1
            result["notification_id"] = notification_id
            result["message"] = f"Sent encouragement for {mode_info['mode']}"
            
        except Exception as e:
            logger.error(f"OverdueEncouragementJob error: {e}")
            result["error"] = str(e)
        
        return result
    
    def _get_current_mode_info(self) -> Dict[str, Any]:
        """Get current mode and tracking session info."""
        info = {
            "mode": None,
            "elapsed_seconds": 0,
            "started_at": None,
            "progress": [],
        }
        
        settings_repo = _get_settings_repo()
        if not settings_repo:
            return info
        
        # Get current mode from settings
        mode = settings_repo.get_setting("current_mode")
        if mode:
            info["mode"] = mode
        
        # Get active tracking session
        if info["mode"]:
            active_sessions = settings_repo.get_active_sessions()
            # Find active session for current mode
            mode_session = next(
                (s for s in active_sessions if s.get("mode") == info["mode"]),
                None
            )
            
            if mode_session:
                info["started_at"] = mode_session.get("started_at")
                # Calculate current elapsed time from started_at
                if mode_session.get("started_at"):
                    try:
                        started = datetime.fromisoformat(mode_session["started_at"])
                        info["elapsed_seconds"] = int((datetime.now() - started).total_seconds())
                    except:
                        info["elapsed_seconds"] = 0
            
            # Get workflow progress
            progress_value = settings_repo.get_setting(f"workflow_progress_{info['mode']}")
            if progress_value:
                try:
                    info["progress"] = json.loads(progress_value)
                except:
                    pass
        
        return info
    
    def _check_if_overdue(self, mode_info: Dict) -> Dict[str, Any]:
        """Check if current mode session is overdue."""
        mode = mode_info.get("mode", "mode-a")
        elapsed_seconds = mode_info.get("elapsed_seconds", 0)
        progress = mode_info.get("progress", [])
        
        expected_minutes = self.MODE_DEFAULTS.get(mode, 60)
        expected_seconds = expected_minutes * 60
        
        # Calculate completion percentage
        total_tasks = len(progress) if progress else 0
        completed_tasks = sum(1 for p in progress if p) if progress else 0
        completion_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Overdue conditions:
        # 1. Elapsed time > expected time
        # 2. AND at least some tasks remain incomplete
        is_overdue = (
            elapsed_seconds > expected_seconds and
            completion_pct < 100 and
            total_tasks > 0
        )
        
        # Calculate how much over
        overdue_seconds = max(0, elapsed_seconds - expected_seconds)
        overdue_minutes = int(overdue_seconds / 60)
        
        return {
            "is_overdue": is_overdue,
            "expected_minutes": expected_minutes,
            "elapsed_minutes": int(elapsed_seconds / 60),
            "overdue_minutes": overdue_minutes,
            "completion_pct": completion_pct,
            "tasks_remaining": total_tasks - completed_tasks,
        }
    
    def _get_task_context(self, mode_info: Dict) -> Dict[str, Any]:
        """Get context from tickets and implementation plans."""
        context = {
            "ticket_title": None,
            "task_focus": None,
            "implementation_hints": [],
            "pending_tasks": [],
        }
        
        # Get active tickets from Supabase
        all_tickets = tickets_supabase.get_active_tickets()
        
        # Sort: in_progress first, then todo
        def sort_priority(t):
            status = t.get("status", "")
            if status == "in_progress":
                return 0
            elif status == "todo":
                return 1
            return 2
        
        sorted_tickets = sorted(all_tickets, key=sort_priority)
        
        if sorted_tickets:
            ticket = sorted_tickets[0]
            context["ticket_title"] = ticket.get("title") or ""
            
            # Parse task decomposition for pending tasks
            task_decomp = ticket.get("task_decomposition")
            if task_decomp:
                try:
                    tasks = json.loads(task_decomp) if isinstance(task_decomp, str) else task_decomp
                    for task in tasks if isinstance(tasks, list) else []:
                        if isinstance(task, dict):
                            status = task.get("status", "pending")
                            if status not in ("done", "complete", "completed"):
                                title = task.get("title") or task.get("text") or str(task)
                                context["pending_tasks"].append(title[:50])
                        elif isinstance(task, str):
                            context["pending_tasks"].append(task[:50])
                except:
                    pass
            
            # Extract key topics from implementation plan
            impl_plan = ticket.get("implementation_plan")
            if impl_plan:
                plan = impl_plan
                # Find technical keywords
                keywords = re.findall(
                    r'\b(api|function|class|method|transform|logic|data|model|service|component|handler|endpoint)\b',
                    plan.lower()
                )
                if keywords:
                    # Use most common keyword as focus
                    from collections import Counter
                    focus = Counter(keywords).most_common(1)[0][0]
                    context["task_focus"] = f"the {focus}"
                
                # Extract hints (first sentences of paragraphs)
                paragraphs = plan.split('\n\n')[:3]
                for para in paragraphs:
                    first_sentence = para.split('.')[0].strip()[:80]
                    if first_sentence and len(first_sentence) > 10:
                        context["implementation_hints"].append(first_sentence)
        
        # Set default task focus if none found
        if not context["task_focus"]:
            if context["pending_tasks"]:
                context["task_focus"] = context["pending_tasks"][0]
            else:
                context["task_focus"] = "current work"
        
        return context
    
    def _create_encouragement_notification(
        self,
        mode_info: Dict,
        overdue_info: Dict,
        context: Dict,
    ) -> Notification:
        """Create the encouraging notification."""
        import random
        
        mode = mode_info.get("mode", "mode-a")
        mode_name = self.MODE_NAMES.get(mode, mode)
        
        # Pick a gut-check question
        templates = self.GUT_CHECK_TEMPLATES.get(mode, self.GUT_CHECK_TEMPLATES["mode-g"])
        question_template = random.choice(templates)
        
        # Format the question with context
        gut_check = question_template.format(
            task_focus=context.get("task_focus", "the current task")
        )
        
        # Build the message
        title = f"⏰ Check-in: {mode_name}"
        
        body_lines = [
            f"You've been in **{mode_name}** for {overdue_info['elapsed_minutes']} minutes.",
            f"(Expected ~{overdue_info['expected_minutes']} min)",
            "",
            f"💭 **{gut_check}**",
            "",
        ]
        
        # Add task context if available
        if context["pending_tasks"]:
            body_lines.append(f"**Remaining tasks:**")
            for task in context["pending_tasks"][:3]:
                body_lines.append(f"• {task}")
            body_lines.append("")
        
        # Add encouraging close
        encouragements = [
            "Take a moment to assess — you've got this! 💪",
            "No rush, just a friendly nudge. You're doing great!",
            "Sometimes stepping back helps. How can I help?",
            "Progress over perfection! Keep going! 🚀",
        ]
        body_lines.append(random.choice(encouragements))
        
        body = "\n".join(body_lines)
        
        return Notification(
            notification_type=NotificationType.COACH_RECOMMENDATION,
            title=title,
            body=body,
            data={
                "type": "overdue_encouragement",
                "mode": mode,
                "elapsed_minutes": overdue_info["elapsed_minutes"],
                "expected_minutes": overdue_info["expected_minutes"],
                "tasks_remaining": overdue_info["tasks_remaining"],
                "task_focus": context.get("task_focus"),
                "ticket_title": context.get("ticket_title"),
            },
            priority=NotificationPriority.NORMAL,
            expires_at=datetime.now() + timedelta(hours=4),
        )
