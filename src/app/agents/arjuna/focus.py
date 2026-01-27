# src/app/agents/arjuna/focus.py
"""
Arjuna Focus Mixin - Focus recommendations functionality.

This mixin provides focus-related methods for the Arjuna agent:
- Focus query detection
- Focus recommendations generation
- Focus response formatting
"""

from datetime import datetime, date, timedelta
from typing import Any, Dict, List
import json
import logging

from .constants import FOCUS_KEYWORDS

logger = logging.getLogger(__name__)


class ArjunaFocusMixin:
    """
    Mixin providing focus recommendation functionality for ArjunaAgent.
    
    Methods:
    - _is_focus_query(): Detect if a message is asking for focus recommendations
    - _handle_focus_query(): Get and format focus recommendations
    - _get_focus_recommendations(): Calculate what to focus on
    - _format_focus_response(): Format recommendations for display
    - _get_focus_step(): Chain command step for focus
    """
    
    def _is_focus_query(self, message: str) -> bool:
        """Check if the message is asking for focus recommendations."""
        msg_lower = message.lower()
        return any(kw in msg_lower for kw in FOCUS_KEYWORDS)
    
    async def _handle_focus_query(self) -> Dict[str, Any]:
        """
        Handle a focus query and return recommendations.
        
        Returns dict with:
        - success: bool
        - message: Formatted recommendations
        - recommendations: Raw recommendation data
        - focus_data: Additional focus context
        """
        try:
            recs = self._get_focus_recommendations()
            focus_data = recs.get("focus_data", {})
            recommendations = recs.get("recommendations", [])
            
            message = self._format_focus_response(recommendations, focus_data)
            
            return {
                "success": True,
                "message": message,
                "recommendations": recommendations,
                "focus_data": focus_data,
            }
        except Exception as e:
            logger.error(f"Error handling focus query: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "I couldn't get your focus recommendations right now."
            }
    
    async def _get_focus_step(self) -> Dict[str, Any]:
        """Chain command step for focus recommendations."""
        return await self._handle_focus_query()
    
    def _get_focus_recommendations(self) -> Dict[str, Any]:
        """
        Get prioritized focus recommendations based on current state.
        
        Considers:
        - Blocked tickets (high priority)
        - In-progress tickets (medium priority)
        - Overdue items (high priority)
        - Pending action items
        - Unprocessed meeting signals
        
        Returns:
            Dict with:
            - recommendations: List of prioritized items
            - focus_data: Context about current state
        """
        conn = self._get_db_connection()
        if not conn:
            return {"error": "No database connection", "recommendations": [], "focus_data": {}}
        
        recommendations = []
        focus_data = {
            "total_open_tickets": 0,
            "blocked_count": 0,
            "in_progress_count": 0,
            "overdue_count": 0,
            "pending_actions": 0,
            "unprocessed_signals": 0,
        }
        
        today = date.today().isoformat()
        
        try:
            # Count open tickets
            total = conn.execute(
                """SELECT COUNT(*) FROM tickets WHERE status NOT IN ('done', 'cancelled', 'closed')"""
            ).fetchone()[0]
            focus_data["total_open_tickets"] = total
            
            # Blocked tickets - highest priority
            blocked = conn.execute(
                """SELECT ticket_id, title, status FROM tickets 
                   WHERE status = 'blocked' 
                   ORDER BY updated_at DESC LIMIT 5"""
            ).fetchall()
            focus_data["blocked_count"] = len(blocked)
            
            for t in blocked:
                recommendations.append({
                    "priority": "high",
                    "type": "blocked_ticket",
                    "message": f"🚫 Unblock {t['ticket_id']}: {t['title'][:40]}",
                    "ticket_id": t["ticket_id"],
                    "reason": "Blocked tickets block progress"
                })
            
            # In-progress tickets
            in_progress = conn.execute(
                """SELECT ticket_id, title, status, updated_at FROM tickets 
                   WHERE status = 'in_progress' 
                   ORDER BY updated_at ASC LIMIT 5"""
            ).fetchall()
            focus_data["in_progress_count"] = len(in_progress)
            
            for t in in_progress[:3]:  # Top 3 in progress
                recommendations.append({
                    "priority": "medium",
                    "type": "in_progress_ticket",
                    "message": f"🔄 Continue {t['ticket_id']}: {t['title'][:40]}",
                    "ticket_id": t["ticket_id"],
                    "reason": "Already started - maintain momentum"
                })
            
            # Overdue items
            overdue = conn.execute(
                """SELECT description, due_date FROM accountability_items 
                   WHERE status != 'complete' AND due_date < ?
                   ORDER BY due_date ASC LIMIT 5""",
                (today,)
            ).fetchall()
            focus_data["overdue_count"] = len(overdue)
            
            for item in overdue[:2]:  # Top 2 overdue
                recommendations.append({
                    "priority": "high",
                    "type": "overdue_item",
                    "message": f"⚠️ Overdue: {item['description'][:40]}",
                    "due_date": item["due_date"],
                    "reason": f"Was due {item['due_date']}"
                })
            
            # Pending action items
            pending = conn.execute(
                """SELECT COUNT(*) FROM accountability_items 
                   WHERE status = 'pending'"""
            ).fetchone()[0]
            focus_data["pending_actions"] = pending
            
            if pending > 0:
                recommendations.append({
                    "priority": "low",
                    "type": "pending_actions",
                    "message": f"📋 {pending} pending action item(s) to address",
                    "count": pending,
                    "reason": "Keep action items moving"
                })
            
            # Sort by priority
            priority_order = {"high": 0, "medium": 1, "low": 2}
            recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))
            
        except Exception as e:
            logger.error(f"Error getting focus recommendations: {e}")
            return {"error": str(e), "recommendations": [], "focus_data": focus_data}
        
        return {"recommendations": recommendations, "focus_data": focus_data}
    
    def _format_focus_response(self, recs: List[Dict], focus_data: Dict) -> str:
        """
        Format focus recommendations as a readable response.
        
        Args:
            recs: List of recommendation dicts
            focus_data: Context about current state
        
        Returns:
            Formatted markdown string
        """
        if not recs:
            return "✨ **You're all caught up!** No urgent items need your attention."
        
        lines = ["🎯 **Focus Recommendations**\n"]
        
        # Summary
        if focus_data.get("blocked_count"):
            lines.append(f"⚠️ {focus_data['blocked_count']} blocked ticket(s) need attention\n")
        
        # Grouped by priority
        high_priority = [r for r in recs if r.get("priority") == "high"]
        medium_priority = [r for r in recs if r.get("priority") == "medium"]
        low_priority = [r for r in recs if r.get("priority") == "low"]
        
        if high_priority:
            lines.append("**🔴 High Priority:**")
            for r in high_priority[:3]:
                lines.append(f"- {r['message']}")
            lines.append("")
        
        if medium_priority:
            lines.append("**🟡 Medium Priority:**")
            for r in medium_priority[:3]:
                lines.append(f"- {r['message']}")
            lines.append("")
        
        if low_priority:
            lines.append("**🟢 When you have time:**")
            for r in low_priority[:2]:
                lines.append(f"- {r['message']}")
        
        return "\n".join(lines)
