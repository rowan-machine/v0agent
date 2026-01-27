# src/app/agents/arjuna/tickets.py
"""
Arjuna Ticket Operations

Handles ticket-related CRUD operations for the Arjuna agent.
Extracted from _arjuna_core.py for better organization.
"""

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ArjunaTicketMixin:
    """
    Mixin class for ticket operations in Arjuna agent.
    
    Provides methods for:
    - Creating tickets
    - Updating ticket status/priority
    - Listing tickets with filters
    - Accountability item creation
    """
    
    def _create_ticket(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new ticket."""
        ticket_id = f"AJ-{datetime.now().strftime('%y%m%d-%H%M')}"
        conn.execute(
            """
            INSERT INTO tickets (ticket_id, title, description, status, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                entities.get("title", "Untitled Task"),
                entities.get("description", ""),
                entities.get("status", "backlog"),
                entities.get("priority", "medium"),
            ),
        )
        return {"success": True, "ticket_id": ticket_id, "action": "create_ticket"}
    
    def _update_ticket(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing ticket."""
        ticket_id = entities.get("ticket_id")
        if not ticket_id:
            return {"success": False, "error": "No ticket ID provided"}
        
        updates = []
        params = []
        
        if "status" in entities:
            updates.append("status = ?")
            params.append(entities["status"])
        if "priority" in entities:
            updates.append("priority = ?")
            params.append(entities["priority"])
        
        if updates:
            params.append(ticket_id)
            conn.execute(
                f"UPDATE tickets SET {', '.join(updates)} WHERE ticket_id = ?",
                params,
            )
        
        return {"success": True, "action": "update_ticket"}
    
    def _list_tickets(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """List tickets with optional status filter."""
        status_filter = entities.get("status")
        
        if status_filter:
            tickets = conn.execute(
                """SELECT ticket_id, title, status, priority FROM tickets 
                   WHERE status = ? ORDER BY created_at DESC LIMIT 10""",
                (status_filter,),
            ).fetchall()
        else:
            tickets = conn.execute(
                """SELECT ticket_id, title, status, priority FROM tickets 
                   ORDER BY created_at DESC LIMIT 10"""
            ).fetchall()
        
        return {
            "success": True,
            "tickets": [dict(t) for t in tickets],
            "action": "list_tickets",
        }
    
    def _create_accountability(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new accountability item."""
        conn.execute(
            """
            INSERT INTO accountability_items (description, responsible_party, context, source_type)
            VALUES (?, ?, ?, 'assistant')
            """,
            (
                entities.get("description", ""),
                entities.get("responsible_party", ""),
                entities.get("context", ""),
            ),
        )
        return {"success": True, "action": "create_accountability"}
    
    def _handle_navigation(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Handle navigation to a specific page."""
        from .constants import SYSTEM_PAGES
        
        target_page = entities.get("target_page", "")
        
        if target_page in SYSTEM_PAGES:
            page_info = SYSTEM_PAGES[target_page]
            return {
                "success": True,
                "navigate_to": page_info["path"],
                "action": "navigate",
            }
        
        return {"success": True, "action": "navigate"}
    
    def _change_model(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Change the current AI model."""
        from .constants import MODEL_ALIASES, AVAILABLE_MODELS
        
        new_model = entities.get("model_name", "")
        
        # Check aliases first
        if new_model.lower() in MODEL_ALIASES:
            new_model = MODEL_ALIASES[new_model.lower()]
        
        if new_model not in AVAILABLE_MODELS:
            return {
                "success": False,
                "error": f"Unknown model: {new_model}. Available: {', '.join(AVAILABLE_MODELS)}",
            }
        
        # Update settings
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'ai_model'",
            (new_model,),
        )
        
        return {
            "success": True,
            "action": "change_model",
            "new_model": new_model,
        }
    
    def _update_sprint(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Update sprint settings."""
        updates = []
        params = []
        
        if "sprint_name" in entities:
            updates.append("sprint_name = ?")
            params.append(entities["sprint_name"])
        if "start_date" in entities:
            updates.append("start_date = ?")
            params.append(entities["start_date"])
        if "end_date" in entities:
            updates.append("end_date = ?")
            params.append(entities["end_date"])
        if "sprint_length" in entities:
            updates.append("sprint_length = ?")
            params.append(entities["sprint_length"])
        
        if updates:
            params.append(1)  # Sprint ID is always 1
            conn.execute(
                f"UPDATE sprint_settings SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        
        return {
            "success": True,
            "action": "update_sprint",
            "navigate_to": "/settings#sprint",
        }
    
    def _reset_workflow(self, conn) -> Dict[str, Any]:
        """Reset the workflow to a clean state."""
        conn.execute("UPDATE workflow_sessions SET is_active = 0")
        return {
            "success": True,
            "action": "reset_workflow",
        }
    
    def _search_meetings(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Search meetings by keyword."""
        query = entities.get("query", "")
        
        if not query:
            return {"success": False, "error": "No search query provided"}
        
        meetings = conn.execute(
            """SELECT id, meeting_name, meeting_date FROM meetings 
               WHERE meeting_name LIKE ? OR raw_text LIKE ?
               ORDER BY meeting_date DESC LIMIT 5""",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        
        return {
            "success": True,
            "meetings": [dict(m) for m in meetings],
            "action": "search_meetings",
            "navigate_to": f"/search?q={query}",
        }


__all__ = ["ArjunaTicketMixin"]
