# src/app/services/jobs/one_on_one_prep.py
"""
F4a: 1:1 Prep Digest Job

Generates 1:1 prep digest answering:
1. What are my top 3 things I'm currently working on?
2. Where do I need help? (blockers)
3. What are my recent observations and feedback to discuss?

Schedule: Biweekly Tuesday 7 AM
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .. import ticket_service, meeting_service
from ..notification_queue import (
    NotificationQueue,
    NotificationType,
    NotificationPriority,
    Notification,
)

logger = logging.getLogger(__name__)


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
        all_tickets = ticket_service.get_active_tickets()
        
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
        all_meetings = meeting_service.get_all_meetings()
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
        blocked_tickets = ticket_service.get_blocked_tickets()
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
        
        all_meetings = meeting_service.get_all_meetings()
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
        
        all_meetings = meeting_service.get_all_meetings()
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
