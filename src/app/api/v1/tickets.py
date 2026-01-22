# src/app/api/v1/tickets.py
"""
API v1 - Tickets endpoints.

RESTful endpoints for ticket CRUD operations with sprint management
integration and AI-powered features via TicketAgent adapters.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional

from ..v1.models import (
    TicketCreate, TicketUpdate, TicketResponse,
    PaginatedResponse, APIResponse
)
from ...db import connect

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_tickets(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """
    List all tickets with pagination and filtering.
    
    Status: backlog, active, in_progress, done, archived
    """
    with connect() as conn:
        query = "SELECT * FROM ticket WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
        total = conn.execute(count_query, tuple(params)).fetchone()["count"]
        
        # Add pagination
        query += " ORDER BY priority DESC, pk DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])
        
        rows = conn.execute(query, tuple(params)).fetchall()
        tickets = [dict(row) for row in rows]
    
    return PaginatedResponse(
        items=tickets,
        skip=skip,
        limit=limit,
        total=total
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int):
    """
    Get a single ticket by ID.
    
    Returns 404 if ticket not found.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ticket WHERE pk = ?",
            (ticket_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    tkt = dict(row)
    return TicketResponse(
        id=tkt.get("pk"),
        title=tkt.get("title", ""),
        description=tkt.get("description"),
        status=tkt.get("status", "backlog"),
        priority=tkt.get("priority", 0),
        points=tkt.get("points"),
        tags=tkt.get("tags"),
        created_at=tkt.get("created_at")
    )


@router.post("", response_model=APIResponse, status_code=201)
async def create_ticket(ticket: TicketCreate):
    """
    Create a new ticket.
    
    Returns the created ticket ID.
    """
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO ticket (title, description, status, priority, points, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticket.title, ticket.description, ticket.status,
             ticket.priority, ticket.points, ticket.tags)
        )
        ticket_id = cursor.lastrowid
        conn.commit()
    
    return APIResponse(
        success=True,
        message="Ticket created",
        data={"id": ticket_id}
    )


@router.put("/{ticket_id}", response_model=APIResponse)
async def update_ticket(ticket_id: int, ticket: TicketUpdate):
    """
    Update an existing ticket.
    
    Only updates fields that are provided.
    Returns 404 if ticket not found.
    """
    with connect() as conn:
        # Check if ticket exists
        existing = conn.execute(
            "SELECT pk FROM ticket WHERE pk = ?",
            (ticket_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        # Build dynamic update query
        updates = []
        params = []
        
        if ticket.title is not None:
            updates.append("title = ?")
            params.append(ticket.title)
        if ticket.description is not None:
            updates.append("description = ?")
            params.append(ticket.description)
        if ticket.status is not None:
            updates.append("status = ?")
            params.append(ticket.status)
        if ticket.priority is not None:
            updates.append("priority = ?")
            params.append(ticket.priority)
        if ticket.points is not None:
            updates.append("points = ?")
            params.append(ticket.points)
        if ticket.tags is not None:
            updates.append("tags = ?")
            params.append(ticket.tags)
        
        if updates:
            query = f"UPDATE ticket SET {', '.join(updates)} WHERE pk = ?"
            params.append(ticket_id)
            conn.execute(query, tuple(params))
            conn.commit()
    
    return APIResponse(
        success=True,
        message="Ticket updated",
        data={"id": ticket_id}
    )


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: int):
    """
    Delete a ticket.
    
    Returns 204 No Content on success, 404 if ticket not found.
    """
    with connect() as conn:
        # Check if ticket exists
        existing = conn.execute(
            "SELECT pk FROM ticket WHERE pk = ?",
            (ticket_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        conn.execute("DELETE FROM ticket WHERE pk = ?", (ticket_id,))
        conn.commit()
    
    return Response(status_code=204)


# -------------------------
# AI-Powered Endpoints (via TicketAgent adapters)
# -------------------------

@router.post("/{ticket_id}/generate-summary", response_model=APIResponse)
async def generate_ticket_summary(ticket_id: int):
    """
    Generate AI-powered ticket summary.
    
    Uses TicketAgent.summarize() for tag-aware summaries.
    """
    # Lazy import for backward compatibility
    from ...agents.ticket_agent import summarize_ticket_adapter
    
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ticket WHERE pk = ?",
            (ticket_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = dict(row)
    summary = await summarize_ticket_adapter(ticket)
    
    return APIResponse(
        success=True,
        message="Summary generated",
        data={"summary": summary}
    )


@router.post("/{ticket_id}/generate-plan", response_model=APIResponse)
async def generate_ticket_plan(ticket_id: int):
    """
    Generate AI-powered implementation plan.
    
    Uses TicketAgent.generate_plan() with Claude Opus for detailed planning.
    """
    # Lazy import for backward compatibility
    from ...agents.ticket_agent import generate_plan_adapter
    
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ticket WHERE pk = ?",
            (ticket_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = dict(row)
    plan = await generate_plan_adapter(ticket)
    
    return APIResponse(
        success=True,
        message="Plan generated",
        data={"plan": plan}
    )


@router.post("/{ticket_id}/decompose", response_model=APIResponse)
async def decompose_ticket(ticket_id: int):
    """
    Decompose ticket into atomic subtasks.
    
    Uses TicketAgent.decompose() for task breakdown with estimates.
    """
    # Lazy import for backward compatibility
    from ...agents.ticket_agent import decompose_ticket_adapter
    
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ticket WHERE pk = ?",
            (ticket_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = dict(row)
    subtasks = await decompose_ticket_adapter(ticket)
    
    return APIResponse(
        success=True,
        message="Ticket decomposed",
        data={"subtasks": subtasks}
    )
