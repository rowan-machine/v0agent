# src/app/domains/tickets/api/crud.py
"""
Ticket CRUD API Routes

Basic create, read, update, delete operations for tickets.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_ticket_repository
from ..constants import DEFAULT_TICKET_LIMIT, TICKET_STATUSES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items")


@router.get("")
async def list_tickets(
    limit: int = Query(DEFAULT_TICKET_LIMIT, le=200),
    offset: int = Query(0, ge=0),
    status: str = Query(None),
    sprint_id: str = Query(None)
):
    """List tickets with pagination and optional filters."""
    repo = get_ticket_repository()
    
    tickets = repo.list(limit=limit, offset=offset)
    
    # Apply filters if provided
    if status:
        tickets = [t for t in tickets if (t.get("status") if isinstance(t, dict) else getattr(t, "status", None)) == status]
    if sprint_id:
        tickets = [t for t in tickets if (t.get("sprint_id") if isinstance(t, dict) else getattr(t, "sprint_id", None)) == sprint_id]
    
    return JSONResponse({
        "status": "ok",
        "tickets": [t if isinstance(t, dict) else t.__dict__ for t in tickets],
        "count": len(tickets),
        "limit": limit,
        "offset": offset
    })


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str):
    """Get a specific ticket by ID."""
    repo = get_ticket_repository()
    
    ticket = repo.get(ticket_id)
    if not ticket:
        return JSONResponse({"error": "Ticket not found"}, status_code=404)
    
    ticket_dict = ticket if isinstance(ticket, dict) else ticket.__dict__
    return JSONResponse({"status": "ok", "ticket": ticket_dict})


@router.post("")
async def create_ticket(request: Request):
    """Create a new ticket."""
    data = await request.json()
    
    repo = get_ticket_repository()
    
    # Validate required fields
    if not data.get("title"):
        return JSONResponse({"error": "title is required"}, status_code=400)
    
    # Set defaults
    data.setdefault("status", "backlog")
    data.setdefault("type", "task")
    
    ticket = repo.create(data)
    if not ticket:
        return JSONResponse({"error": "Failed to create ticket"}, status_code=500)
    
    ticket_dict = ticket if isinstance(ticket, dict) else ticket.__dict__
    return JSONResponse({"status": "ok", "ticket": ticket_dict}, status_code=201)


@router.put("/{ticket_id}")
async def update_ticket(ticket_id: str, request: Request):
    """Update an existing ticket."""
    data = await request.json()
    
    repo = get_ticket_repository()
    
    existing = repo.get(ticket_id)
    if not existing:
        return JSONResponse({"error": "Ticket not found"}, status_code=404)
    
    updated = repo.update(ticket_id, data)
    if not updated:
        return JSONResponse({"error": "Failed to update ticket"}, status_code=500)
    
    updated_dict = updated if isinstance(updated, dict) else updated.__dict__
    return JSONResponse({"status": "ok", "ticket": updated_dict})


@router.delete("/{ticket_id}")
async def delete_ticket(ticket_id: str):
    """Delete a ticket (soft delete)."""
    repo = get_ticket_repository()
    
    existing = repo.get(ticket_id)
    if not existing:
        return JSONResponse({"error": "Ticket not found"}, status_code=404)
    
    success = repo.delete(ticket_id)
    if not success:
        return JSONResponse({"error": "Failed to delete ticket"}, status_code=500)
    
    return JSONResponse({"status": "ok", "message": "Ticket deleted"})


@router.put("/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, request: Request):
    """Update ticket status."""
    data = await request.json()
    new_status = data.get("status")
    
    if not new_status:
        return JSONResponse({"error": "status is required"}, status_code=400)
    
    if new_status not in TICKET_STATUSES:
        return JSONResponse({"error": f"Invalid status. Must be one of: {TICKET_STATUSES}"}, status_code=400)
    
    repo = get_ticket_repository()
    
    updated = repo.update(ticket_id, {"status": new_status})
    if not updated:
        return JSONResponse({"error": "Failed to update status"}, status_code=500)
    
    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "new_status": new_status})
