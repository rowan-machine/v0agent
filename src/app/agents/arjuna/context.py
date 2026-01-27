"""
Arjuna Agent Context - System context and focus recommendations.

These methods gather context for the agent:
- System state (sprint, tickets, signals)
- Focus recommendations
- Follow-up suggestions

Extracted from _arjuna_core.py for better maintainability.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, date, timedelta
import json
import logging

from .constants import AVAILABLE_MODELS, SYSTEM_PAGES

logger = logging.getLogger(__name__)


class ArjunaContextMixin:
    """Mixin class providing context-gathering methods for ArjunaAgent."""
    
    def _get_system_context(self) -> Dict[str, Any]:
        """Get current system state for context including sprint work items."""
        conn = self._get_db_connection()
        if not conn:
            return {}
        
        try:
            # Get sprint info
            sprint = conn.execute(
                "SELECT * FROM sprint_settings WHERE id = 1"
            ).fetchone()
            
            # Get current AI model
            model_row = conn.execute(
                "SELECT value FROM settings WHERE key = 'ai_model'"
            ).fetchone()
            current_model = model_row["value"] if model_row else "gpt-4o-mini"
            
            # Get ticket counts by status
            ticket_stats = conn.execute(
                """
                SELECT status, COUNT(*) as count 
                FROM tickets 
                GROUP BY status
                """
            ).fetchall()
            
            # Get recent tickets with checklist progress
            tickets = conn.execute(
                """
                SELECT ticket_id, title, status, priority, task_decomposition, in_sprint
                FROM tickets 
                WHERE in_sprint = 1
                ORDER BY 
                    CASE status
                        WHEN 'blocked' THEN 1
                        WHEN 'in_progress' THEN 2
                        WHEN 'in_review' THEN 3
                        WHEN 'todo' THEN 4
                        ELSE 5
                    END,
                    priority DESC
                LIMIT 15
                """
            ).fetchall()
            
            # Process ticket checklists
            tickets_with_progress = []
            for t in tickets:
                ticket_data = {
                    "ticket_id": t["ticket_id"],
                    "title": t["title"],
                    "status": t["status"],
                    "priority": t["priority"],
                }
                if t["task_decomposition"]:
                    try:
                        tasks = json.loads(t["task_decomposition"])
                        if isinstance(tasks, list):
                            total = len(tasks)
                            done = sum(1 for task in tasks if task.get("done", False))
                            ticket_data["checklist_progress"] = f"{done}/{total}"
                            ticket_data["checklist_items"] = [
                                {"text": task.get("text", task.get("title", str(task))), "done": task.get("done", False)}
                                for task in tasks[:5]
                            ]
                    except:
                        pass
                tickets_with_progress.append(ticket_data)
            
            # Get pending action items from signals
            action_items = conn.execute(
                """
                SELECT id, content, meeting_id, status, created_at
                FROM signals
                WHERE signal_type = 'action_item' AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 10
                """
            ).fetchall()
            
            # Get active test plans with task progress
            test_plans = conn.execute(
                """
                SELECT id, test_plan_id, title, status, priority, task_decomposition, linked_ticket_id
                FROM test_plans
                WHERE status IN ('planned', 'in_progress') AND in_sprint = 1
                ORDER BY priority DESC
                LIMIT 10
                """
            ).fetchall()
            
            test_plans_with_progress = []
            for tp in test_plans:
                plan_data = {
                    "test_plan_id": tp["test_plan_id"],
                    "title": tp["title"],
                    "status": tp["status"],
                    "priority": tp["priority"],
                    "linked_ticket_id": tp["linked_ticket_id"],
                }
                if tp["task_decomposition"]:
                    try:
                        tasks = json.loads(tp["task_decomposition"])
                        if isinstance(tasks, list):
                            total = len(tasks)
                            done = sum(1 for task in tasks if task.get("done", False))
                            plan_data["task_progress"] = f"{done}/{total}"
                            plan_data["tasks"] = [
                                {"text": task.get("text", task.get("title", str(task))), "done": task.get("done", False)}
                                for task in tasks[:5]
                            ]
                    except:
                        pass
                test_plans_with_progress.append(plan_data)
            
            # Get blockers
            blockers = conn.execute(
                """
                SELECT id, content, meeting_id, created_at
                FROM signals
                WHERE signal_type = 'blocker' AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 5
                """
            ).fetchall()
            
            # Get accountability items (waiting-for)
            waiting_for = conn.execute(
                """
                SELECT id, description, responsible_party, due_date, status
                FROM accountability_items
                WHERE status = 'waiting'
                ORDER BY due_date ASC NULLS LAST
                LIMIT 5
                """
            ).fetchall()
            
            return {
                "sprint": dict(sprint) if sprint else None,
                "current_ai_model": current_model,
                "available_models": AVAILABLE_MODELS,
                "ticket_stats": {row["status"]: row["count"] for row in ticket_stats},
                "sprint_tickets": tickets_with_progress,
                "action_items_pending": [
                    {"id": a["id"], "content": a["content"][:150], "created": a["created_at"][:10]}
                    for a in action_items
                ],
                "test_plans": test_plans_with_progress,
                "active_blockers": [
                    {"id": b["id"], "content": b["content"][:150], "from_meeting": b["meeting_id"]}
                    for b in blockers
                ],
                "waiting_for": [
                    {"description": w["description"][:100], "who": w["responsible_party"], "due": w["due_date"]}
                    for w in waiting_for
                ],
                "available_pages": SYSTEM_PAGES,
            }
        except Exception as e:
            logger.error(f"Failed to get system context: {e}")
            return {}
    
    def _get_focus_recommendations(self) -> Dict[str, Any]:
        """Get prioritized work recommendations."""
        conn = self._get_db_connection()
        if not conn:
            return {"recommendations": [], "total_count": 0}
        
        recommendations = []
        
        try:
            # 1. BLOCKERS (Highest priority)
            blockers = conn.execute(
                """SELECT ticket_id, title FROM tickets 
                   WHERE status = 'blocked' 
                   ORDER BY created_at ASC LIMIT 2"""
            ).fetchall()
            for b in blockers:
                recommendations.append({
                    "priority": 1,
                    "type": "blocker",
                    "title": f"🚫 Blocked: {b['ticket_id']}",
                    "text": b["title"],
                    "reason": "Blocked work stops everything downstream",
                    "action": "Identify who can unblock this and reach out",
                })
            
            # 2. IN-PROGRESS WORK
            in_progress = conn.execute(
                """SELECT ticket_id, title FROM tickets 
                   WHERE status = 'in_progress' 
                   ORDER BY updated_at DESC LIMIT 2"""
            ).fetchall()
            for t in in_progress:
                recommendations.append({
                    "priority": 2,
                    "type": "active",
                    "title": f"🔄 Continue: {t['ticket_id']}",
                    "text": t["title"],
                    "reason": "Finishing started work is more efficient than context-switching",
                    "action": "Continue where you left off",
                })
            
            # 3. SPRINT DEADLINE APPROACHING
            sprint = conn.execute(
                "SELECT * FROM sprint_settings WHERE id = 1"
            ).fetchone()
            if sprint and sprint["sprint_start_date"] and sprint["sprint_length_days"]:
                try:
                    start_date = datetime.strptime(sprint["sprint_start_date"], "%Y-%m-%d").date()
                    end_date = start_date + timedelta(days=sprint["sprint_length_days"])
                    days_left = (end_date - date.today()).days
                    
                    if 0 <= days_left <= 3:
                        todo_count = conn.execute(
                            "SELECT COUNT(*) as c FROM tickets WHERE status IN ('todo', 'in_progress')"
                        ).fetchone()["c"]
                        
                        if todo_count > 0:
                            recommendations.append({
                                "priority": 2,
                                "type": "deadline",
                                "title": f"⏰ Sprint ends in {days_left} days!",
                                "text": f"{todo_count} items still in todo",
                                "reason": "Time is running out - consider scope reduction",
                                "action": "Review remaining work and prioritize ruthlessly",
                            })
                except Exception:
                    pass
            
            # 4. STALE WORK
            stale = conn.execute(
                """SELECT ticket_id, title, updated_at FROM tickets 
                   WHERE status = 'in_progress' 
                   AND date(updated_at) < date('now', '-2 days')
                   ORDER BY updated_at ASC LIMIT 1"""
            ).fetchall()
            for t in stale:
                recommendations.append({
                    "priority": 3,
                    "type": "stale",
                    "title": f"⏳ Stale: {t['ticket_id']}",
                    "text": t["title"],
                    "reason": "This has been in progress for days - is it blocked?",
                    "action": "Either complete it or mark it blocked",
                })
            
            # 5. WAITING-FOR ITEMS
            waiting = conn.execute(
                """SELECT description, responsible_party FROM accountability_items
                   WHERE status = 'waiting'
                   ORDER BY created_at ASC LIMIT 2"""
            ).fetchall()
            for w in waiting:
                recommendations.append({
                    "priority": 4,
                    "type": "waiting",
                    "title": f"⏳ Follow up: {w['responsible_party']}",
                    "text": w["description"][:60],
                    "reason": "Dependencies on others can become blockers",
                    "action": f"Check in with {w['responsible_party']}",
                })
            
            # 6. HIGH PRIORITY TODO
            if len(recommendations) < 3:
                high_priority = conn.execute(
                    """SELECT ticket_id, title FROM tickets 
                       WHERE status = 'todo' AND priority = 'high'
                       ORDER BY created_at ASC LIMIT 2"""
                ).fetchall()
                for t in high_priority:
                    recommendations.append({
                        "priority": 6,
                        "type": "todo",
                        "title": f"⭐ High Priority: {t['ticket_id']}",
                        "text": t["title"],
                        "reason": "High priority work should be started soon",
                        "action": "Start working on this ticket",
                    })
        
        except Exception as e:
            logger.error(f"Failed to get focus recommendations: {e}")
        
        recommendations.sort(key=lambda r: r["priority"])
        
        return {
            "recommendations": recommendations[:5],
            "total_count": len(recommendations),
        }
    
    def _get_follow_up_suggestions(
        self,
        action: Optional[str],
        intent: Optional[str],
        result: Dict[str, Any],
    ) -> List[str]:
        """Generate contextual follow-up suggestions."""
        suggestions = []
        
        if action == "create_ticket":
            suggestions = [
                "What's the priority?",
                "Add a description",
                "Show my tickets",
            ]
        elif action == "update_ticket":
            suggestions = [
                "Show my tickets",
                "What should I work on next?",
                "Create another ticket",
            ]
        elif action == "create_accountability":
            suggestions = [
                "Show waiting-for items",
                "Create a ticket from this",
            ]
        elif action == "create_standup":
            suggestions = [
                "What should I focus on?",
                "Show my tickets",
            ]
        elif action == "navigate":
            suggestions = [
                "Help me understand this page",
                "What can I do here?",
            ]
        elif action == "change_model":
            suggestions = [
                "What models are available?",
                "Tell me about this model",
            ]
        elif action == "focus_recommendations":
            suggestions = [
                "Start working on the first one",
                "Show me more details",
            ]
        elif intent == "greeting":
            suggestions = [
                "What can you help me with?",
                "What should I focus on?",
                "Show me my tickets",
            ]
        else:
            suggestions = [
                "What should I focus on?",
                "Create a ticket",
                "Show my progress",
            ]
        
        return suggestions


__all__ = ["ArjunaContextMixin"]
