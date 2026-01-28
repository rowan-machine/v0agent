# src/app/services/jobs/grooming_match.py
"""
F4c: Grooming Meeting to Ticket Match Alert Job

When a new grooming/planning meeting is imported:
- Find matching tickets based on content similarity
- Identify gaps: items discussed but not in ticket
- Create HIGH priority notification for matches

Schedule: Hourly (checks for new grooming meetings)
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ...repositories import get_notifications_repository
from .. import ticket_service, meeting_service
from ..notification_queue import (
    NotificationQueue,
    NotificationType,
    NotificationPriority,
    Notification,
)

logger = logging.getLogger(__name__)


def _get_notifications_repo():
    """Get notifications repository (lazy load)."""
    try:
        return get_notifications_repository()
    except Exception:
        return None


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
        
        all_meetings = meeting_service.get_all_meetings()
        
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
        all_tickets = ticket_service.get_active_tickets()
        
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
