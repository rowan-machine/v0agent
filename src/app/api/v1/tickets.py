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
from ...infrastructure.supabase_client import get_supabase_client
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
    Uses Supabase as primary source.
    """
    try:
        tickets, total = _get_tickets_from_supabase(skip, limit, status, tag)
        return PaginatedResponse(items=tickets, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.error(f"❌ Failed to fetch tickets: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch tickets")


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int):
    """
    Get a single ticket by ID.
    
    Returns 404 if ticket not found.
    """
    supabase = get_supabase_client()
    result = supabase.table("tickets").select("*").eq("id", ticket_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    tkt = result.data[0]
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
    supabase = get_supabase_client()
    result = supabase.table("tickets").insert({
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "points": ticket.points,
        "tags": ticket.tags
    }).execute()
    
    ticket_id = result.data[0]["id"] if result.data else None
    
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
    supabase = get_supabase_client()
    
    # Check if ticket exists
    existing = supabase.table("tickets").select("id").eq("id", ticket_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Build update dict
    updates = {}
    if ticket.title is not None:
        updates["title"] = ticket.title
    if ticket.description is not None:
        updates["description"] = ticket.description
    if ticket.status is not None:
        updates["status"] = ticket.status
    if ticket.priority is not None:
        updates["priority"] = ticket.priority
    if ticket.points is not None:
        updates["points"] = ticket.points
    if ticket.tags is not None:
        updates["tags"] = ticket.tags
    
    if updates:
        supabase.table("tickets").update(updates).eq("id", ticket_id).execute()
    
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
    supabase = get_supabase_client()
    
    # Check if ticket exists
    existing = supabase.table("tickets").select("id").eq("id", ticket_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    supabase.table("tickets").delete().eq("id", ticket_id).execute()
    
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
    
    supabase = get_supabase_client()
    result = supabase.table("tickets").select("*").eq("id", ticket_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = result.data[0]
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
    
    supabase = get_supabase_client()
    result = supabase.table("tickets").select("*").eq("id", ticket_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = result.data[0]
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
    
    supabase = get_supabase_client()
    result = supabase.table("tickets").select("*").eq("id", ticket_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = result.data[0]
    subtasks = await decompose_ticket_adapter(ticket)
    
    return APIResponse(
        success=True,
        message="Ticket decomposed",
        data={"subtasks": subtasks}
    )
