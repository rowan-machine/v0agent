# src/app/domains/tickets/api/deployment.py
"""
Ticket Deployment API Routes

Deployment tracking and status management for tickets.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import json
import logging

from ....services import ticket_service
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deployment")


@router.get("/deployable")
async def get_deployable_tickets():
    """Get all tickets in the current sprint that require deployment (for Mode F)."""
    try:
        all_sprint_tickets = ticket_service.get_sprint_tickets()
        tickets = [t for t in all_sprint_tickets if t.get("in_sprint")]
        
        result = []
        for t in tickets:
            # Parse deployment checklist from task_decomposition or create default
            deployment_status = {
                "pushed": False,
                "pr_created": False,
                "pr_reviewed": False,
                "merged": False,
                "deployed": False
            }
            
            # Check if there's a deployment_status stored in task_decomposition
            if t.get('task_decomposition'):
                try:
                    decomp = json.loads(t['task_decomposition']) if isinstance(t['task_decomposition'], str) else t['task_decomposition']
                    if isinstance(decomp, dict) and 'deployment_status' in decomp:
                        deployment_status = decomp['deployment_status']
                except (json.JSONDecodeError, TypeError):
                    pass
            
            result.append({
                "id": t['id'],
                "ticket_id": t.get('ticket_id'),
                "title": t.get('title'),
                "status": t.get('status'),
                "priority": t.get('priority'),
                "sprint_points": t.get('sprint_points'),
                "deployment_status": deployment_status
            })
        
        return JSONResponse({"tickets": result})
    except Exception as e:
        logger.exception("Error getting deployable tickets")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/{ticket_id}/status")
async def update_deployment_status(ticket_id: str, request: Request):
    """Update deployment checklist status for a ticket."""
    try:
        data = await request.json()
        step = data.get("step")  # pushed, pr_created, pr_reviewed, merged, deployed
        status = data.get("status", False)
        
        ticket = ticket_service.get_ticket_by_id(ticket_id)
        
        if not ticket:
            return JSONResponse({"error": "Ticket not found"}, status_code=404)
        
        # Parse or create deployment status structure
        decomp = {}
        if ticket.get('task_decomposition'):
            try:
                decomp = json.loads(ticket['task_decomposition']) if isinstance(ticket['task_decomposition'], str) else ticket['task_decomposition']
                if not isinstance(decomp, dict):
                    decomp = {"tasks": decomp}  # Preserve existing tasks array
            except (json.JSONDecodeError, TypeError):
                decomp = {}
        
        # Ensure deployment_status exists
        if 'deployment_status' not in decomp:
            decomp['deployment_status'] = {
                "pushed": False,
                "pr_created": False,
                "pr_reviewed": False,
                "merged": False,
                "deployed": False
            }
        
        # Update the specific step
        decomp['deployment_status'][step] = status
        
        # Save to Supabase
        ticket_service.update_ticket(ticket_id, {
            "task_decomposition": json.dumps(decomp),
            "updated_at": datetime.now().isoformat()
        })
        
        return JSONResponse({"status": "ok", "step": step, "new_status": status})
    except Exception as e:
        logger.exception(f"Error updating deployment status for ticket {ticket_id}")
        return JSONResponse({"error": str(e)}, status_code=500)
