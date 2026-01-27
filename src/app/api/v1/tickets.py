# src/app/api/v1/tickets.py
"""
API v1 - Tickets endpoints.

RESTful endpoints for ticket CRUD operations with sprint management
integration and AI-powered features via TicketAgent adapters.

Supabase-first with SQLite fallback.
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, List, Dict, Any

from ..v1.models import (
    TicketCreate, TicketUpdate, TicketResponse,
    PaginatedResponse, APIResponse
)
from ...db import connect
from ...repositories import get_ticket_repository

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_tickets_from_supabase(skip: int = 0, limit: int = 50, status: Optional[str] = None, tag: Optional[str] = None) -> tuple[List[Dict[str, Any]], int]:
    """
    Fetch tickets from Supabase.
    Returns (tickets_list, total_count) or raises exception.
    """
    try:
        from ...infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        if not supabase:
            raise Exception("Supabase client not available")
        
        # Build query with filters
        query = supabase.table("tickets").select("*", count="exact")
        
        if status:
            query = query.eq("status", status)
        if tag:
            query = query.ilike("tags", f"%{tag}%")
        
        # Get total count first
        count_result = query.execute()
        total = count_result.count if count_result.count is not None else len(count_result.data or [])
        
        # Get paginated tickets
        query = supabase.table("tickets").select("*")
        if status:
            query = query.eq("status", status)
        if tag:
            query = query.ilike("tags", f"%{tag}%")
        
        result = query.order("created_at", desc=True).range(skip, skip + limit - 1).execute()
        
        tickets = result.data or []
        logger.info(f"✅ Fetched {len(tickets)} tickets from Supabase")
        return tickets, total
    except Exception as e:
        logger.error(f"❌ Failed to fetch tickets from Supabase: {e}")
        raise


def _get_tickets_from_sqlite(skip: int = 0, limit: int = 50, status: Optional[str] = None, tag: Optional[str] = None) -> tuple[List[Dict[str, Any]], int]:
    """
    Fetch tickets from SQLite.
    Returns (tickets_list, total_count).
    """
    with connect() as conn:
        query = "SELECT * FROM tickets WHERE 1=1"
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
        query += " ORDER BY priority DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])
        
        rows = conn.execute(query, tuple(params)).fetchall()
        tickets = [dict(row) for row in rows]
    
    return tickets, total


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
    Uses Supabase as primary source with SQLite fallback.
    """
    # Try Supabase first
    try:
        tickets, total = _get_tickets_from_supabase(skip, limit, status, tag)
        return PaginatedResponse(items=tickets, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.warning(f"⚠️ Supabase unavailable for tickets, falling back to SQLite: {e}")
    
    # Fall back to SQLite
    try:
        tickets, total = _get_tickets_from_sqlite(skip, limit, status, tag)
        return PaginatedResponse(items=tickets, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.error(f"❌ SQLite also failed for tickets: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch tickets")


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int):
    """
    Get a single ticket by ID.
    
    Returns 404 if ticket not found.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM tickets WHERE id = ?",
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
            """INSERT INTO tickets (title, description, status, priority, points, tags)
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
            "SELECT id FROM tickets WHERE id = ?",
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
            query = f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?"
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
            "SELECT id FROM tickets WHERE id = ?",
            (ticket_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
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
            "SELECT * FROM tickets WHERE id = ?",
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
            "SELECT * FROM tickets WHERE id = ?",
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
            "SELECT * FROM tickets WHERE id = ?",
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
