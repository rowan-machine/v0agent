# src/app/api/v1/signals.py
"""
API v1 - Signals endpoints.

RESTful endpoints for signal CRUD operations (decisions, action items,
blockers, risks, ideas) with proper pagination and filtering.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional

from ..v1.models import (
    SignalCreate, SignalUpdate, SignalResponse,
    PaginatedResponse, APIResponse
)
from ...infrastructure.supabase_client import get_supabase_client

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_signals(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    meeting_id: Optional[int] = Query(None, description="Filter by source meeting"),
):
    """
    List all signals with pagination and filtering.
    
    Signal types: decision, action_item, blocker, risk, idea
    Status: active, resolved, archived
    """
    supabase = get_supabase_client()
    
    # Build query with filters
    query = supabase.table("signal").select("*", count="exact")
    
    if signal_type:
        query = query.eq("signal_type", signal_type)
    if status:
        query = query.eq("status", status)
    if meeting_id:
        query = query.eq("source_meeting_id", meeting_id)
    
    # Get total count
    count_result = query.execute()
    total = count_result.count if count_result.count is not None else len(count_result.data or [])
    
    # Get paginated results
    query = supabase.table("signal").select("*")
    if signal_type:
        query = query.eq("signal_type", signal_type)
    if status:
        query = query.eq("status", status)
    if meeting_id:
        query = query.eq("source_meeting_id", meeting_id)
    
    result = query.order("priority", desc=True).order("pk", desc=True).range(skip, skip + limit - 1).execute()
    signals = result.data or []
    
    return PaginatedResponse(
        items=signals,
        skip=skip,
        limit=limit,
        total=total
    )


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: int):
    """
    Get a single signal by ID.
    
    Returns 404 if signal not found.
    """
    supabase = get_supabase_client()
    result = supabase.table("signal").select("*").eq("pk", signal_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    sig = result.data[0]
    return SignalResponse(
        id=sig.get("pk"),
        signal_type=sig.get("signal_type", ""),
        content=sig.get("content", ""),
        source_meeting_id=sig.get("source_meeting_id"),
        priority=sig.get("priority", 0),
        status=sig.get("status", "active"),
        created_at=sig.get("created_at")
    )


@router.post("", response_model=APIResponse, status_code=201)
async def create_signal(signal: SignalCreate):
    """
    Create a new signal.
    
    Returns the created signal ID.
    """
    supabase = get_supabase_client()
    result = supabase.table("signal").insert({
        "signal_type": signal.signal_type,
        "content": signal.content,
        "source_meeting_id": signal.source_meeting_id,
        "priority": signal.priority,
        "status": signal.status
    }).execute()
    
    signal_id = result.data[0]["pk"] if result.data else None
    
    return APIResponse(
        success=True,
        message="Signal created",
        data={"id": signal_id}
    )


@router.put("/{signal_id}", response_model=APIResponse)
async def update_signal(signal_id: int, signal: SignalUpdate):
    """
    Update an existing signal.
    
    Only updates fields that are provided.
    Returns 404 if signal not found.
    """
    supabase = get_supabase_client()
    
    # Check if signal exists
    existing = supabase.table("signal").select("pk").eq("pk", signal_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    # Build update dict
    updates = {}
    if signal.content is not None:
        updates["content"] = signal.content
    if signal.priority is not None:
        updates["priority"] = signal.priority
    if signal.status is not None:
        updates["status"] = signal.status
    
    if updates:
        supabase.table("signal").update(updates).eq("pk", signal_id).execute()
    
    return APIResponse(
        success=True,
        message="Signal updated",
        data={"id": signal_id}
    )


@router.delete("/{signal_id}", status_code=204)
async def delete_signal(signal_id: int):
    """
    Delete a signal.
    
    Returns 204 No Content on success, 404 if signal not found.
    """
    supabase = get_supabase_client()
    
    # Check if signal exists
    existing = supabase.table("signal").select("pk").eq("pk", signal_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    supabase.table("signal").delete().eq("pk", signal_id).execute()
    
    return Response(status_code=204)


@router.get("/by-type/{signal_type}", response_model=PaginatedResponse)
async def list_signals_by_type(
    signal_type: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
):
    """
    List signals filtered by type.
    
    Convenience endpoint for getting all action items, blockers, etc.
    """
    return await list_signals(
        skip=skip,
        limit=limit,
        signal_type=signal_type,
        status=status,
        meeting_id=None
    )
