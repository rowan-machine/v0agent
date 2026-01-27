"""
Arjuna Agent Tools - Intent execution methods.

These methods handle the actual execution of user intents:
- Ticket CRUD operations
- Accountability item creation
- Standup logging
- Navigation handling
- Model/sprint settings changes

Extracted from _arjuna_core.py for better maintainability.
"""

from typing import Any, Dict, List, Optional
from datetime import date
import json
import logging

from .constants import AVAILABLE_MODELS, MODEL_ALIASES, SYSTEM_PAGES

logger = logging.getLogger(__name__)


class ArjunaToolsMixin:
    """Mixin class providing intent execution tools for ArjunaAgent."""
    
    def _create_ticket(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new ticket."""
        title = entities.get("title") or entities.get("ticket_title", "New Ticket")
        
        # Get next ticket number
        cur = conn.execute("SELECT MAX(ticket_id) FROM tickets")
        max_id = cur.fetchone()[0] or 0
        new_id = max_id + 1
        
        conn.execute(
            """
            INSERT INTO tickets (ticket_id, title, status, priority, created_at, updated_at)
            VALUES (?, ?, 'todo', 'medium', datetime('now'), datetime('now'))
            """,
            (new_id, title),
        )
        
        return {
            "success": True,
            "action": "create_ticket",
            "ticket_id": new_id,
            "title": title,
        }
    
    def _update_ticket(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing ticket."""
        ticket_id = entities.get("ticket_id")
        if not ticket_id:
            return {"success": False, "error": "No ticket ID provided"}
        
        # Build update parts
        updates = []
        params = []
        
        if entities.get("status"):
            updates.append("status = ?")
            params.append(entities["status"])
        if entities.get("priority"):
            updates.append("priority = ?")
            params.append(entities["priority"])
        if entities.get("title"):
            updates.append("title = ?")
            params.append(entities["title"])
        
        if not updates:
            return {"success": False, "error": "No updates provided"}
        
        updates.append("updated_at = datetime('now')")
        params.append(ticket_id)
        
        conn.execute(
            f"UPDATE tickets SET {', '.join(updates)} WHERE ticket_id = ?",
            params,
        )
        
        return {
            "success": True,
            "action": "update_ticket",
            "ticket_id": ticket_id,
        }
    
    def _list_tickets(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """List tickets with optional filters."""
        status = entities.get("status")
        limit = entities.get("limit", 10)
        
        query = "SELECT ticket_id, title, status, priority FROM tickets"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        
        tickets = conn.execute(query, params).fetchall()
        
        return {
            "success": True,
            "action": "list_tickets",
            "tickets": [dict(t) for t in tickets],
        }
    
    def _create_accountability(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create an accountability/waiting-for item."""
        description = entities.get("description", "")
        responsible = entities.get("responsible_party", "Someone")
        due_date = entities.get("due_date")
        
        conn.execute(
            """
            INSERT INTO accountability_items (description, responsible_party, due_date, status, created_at)
            VALUES (?, ?, ?, 'waiting', datetime('now'))
            """,
            (description, responsible, due_date),
        )
        
        return {
            "success": True,
            "action": "create_accountability",
            "description": description,
        }
    
    def _create_standup(
        self,
        conn,
        entities: Dict[str, Any],
        intent_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a standup entry."""
        standup_date = date.today().isoformat()
        
        content_parts = []
        if entities.get("yesterday"):
            content_parts.append(f"Yesterday: {entities['yesterday']}")
        if entities.get("today_plan"):
            content_parts.append(f"Today: {entities['today_plan']}")
        if entities.get("blockers"):
            content_parts.append(f"Blockers: {entities['blockers']}")
        
        content = "\n".join(content_parts) or intent_data.get("response_text") or "Standup update"
        
        cur = conn.execute(
            """
            INSERT INTO standup_updates (standup_date, content, feedback, sentiment, key_themes)
            VALUES (?, ?, NULL, 'neutral', '')
            """,
            (standup_date, content),
        )
        
        return {
            "success": True,
            "action": "create_standup",
            "standup_id": cur.lastrowid,
        }
    
    def _handle_navigation(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Handle navigation requests."""
        target = entities.get("target_page")
        if target and target in SYSTEM_PAGES:
            return {
                "success": True,
                "action": "navigate",
                "navigate_to": SYSTEM_PAGES[target]["path"],
            }
        return {"success": True, "action": "navigate"}
    
    def _change_model(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Change the AI model setting."""
        model = entities.get("model", "").lower().strip()
        normalized = MODEL_ALIASES.get(model.replace(" ", "").replace("-", ""), model)
        
        if normalized not in AVAILABLE_MODELS:
            return {
                "success": False,
                "error": f"Unknown model: {model}. Available: {', '.join(AVAILABLE_MODELS)}",
            }
        
        conn.execute(
            """
            INSERT INTO settings (key, value) 
            VALUES ('ai_model', ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')
            """,
            (normalized, normalized),
        )
        
        return {"success": True, "action": "change_model", "model": normalized}
    
    def _update_sprint(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Update sprint settings."""
        sprint_name = entities.get("sprint_name")
        sprint_goal = entities.get("sprint_goal")
        
        if not sprint_name and not sprint_goal:
            return {"success": False, "error": "No sprint name or goal provided"}
        
        updates = []
        params = []
        
        if sprint_name:
            updates.append("sprint_name = ?")
            params.append(sprint_name)
        if sprint_goal:
            updates.append("sprint_goal = ?")
            params.append(sprint_goal)
        
        if updates:
            params.append(1)  # id = 1
            conn.execute(
                f"UPDATE sprint_settings SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        
        return {
            "success": True,
            "action": "update_sprint",
            "sprint_name": sprint_name,
            "sprint_goal": sprint_goal,
        }
    
    def _reset_workflow(self, conn) -> Dict[str, Any]:
        """Reset all workflow progress."""
        modes = ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g']
        for mode in modes:
            conn.execute(
                "DELETE FROM settings WHERE key = ?",
                (f"workflow_progress_{mode}",),
            )
        return {"success": True, "action": "reset_workflow"}
    
    def _search_meetings(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Search meeting summaries."""
        query = entities.get("query", "")
        meetings = conn.execute(
            """
            SELECT meeting_name, meeting_date, signals_json
            FROM meeting_summaries
            WHERE meeting_name LIKE ? OR raw_text LIKE ? OR signals_json LIKE ?
            ORDER BY meeting_date DESC
            LIMIT 5
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
        
        return {
            "success": True,
            "action": "search_meetings",
            "meetings": [dict(m) for m in meetings],
        }


__all__ = ["ArjunaToolsMixin"]
