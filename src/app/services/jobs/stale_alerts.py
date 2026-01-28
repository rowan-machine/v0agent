# src/app/services/jobs/stale_alerts.py
"""
F4b: Stale Ticket and Blocker Alert Job

Triggers when:
- Ticket has no activity for 5+ days
- Blocker mentioned but unresolved after 3 days
- Action item with date pattern is overdue

Schedule: Daily 9:00 AM (weekdays)
"""

import json
import logging
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
        
        stale_tickets = ticket_service.get_stale_in_progress_tickets(days=self.STALE_TICKET_DAYS)
        
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
        
        all_meetings = meeting_service.get_all_meetings()
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
