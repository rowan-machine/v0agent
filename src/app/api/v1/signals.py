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
from ...db import connect

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
    with connect() as conn:
        query = "SELECT * FROM signal WHERE 1=1"
        params = []
        
        if signal_type:
            query += " AND signal_type = ?"
            params.append(signal_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        if meeting_id:
            query += " AND source_meeting_id = ?"
            params.append(meeting_id)
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
        total = conn.execute(count_query, tuple(params)).fetchone()["count"]
        
        # Add pagination
        query += " ORDER BY priority DESC, pk DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])
        
        rows = conn.execute(query, tuple(params)).fetchall()
        signals = [dict(row) for row in rows]
    
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
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM signal WHERE pk = ?",
            (signal_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    sig = dict(row)
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
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO signal (signal_type, content, source_meeting_id, priority, status)
               VALUES (?, ?, ?, ?, ?)""",
            (signal.signal_type, signal.content, signal.source_meeting_id,
             signal.priority, signal.status)
        )
        signal_id = cursor.lastrowid
        conn.commit()
    
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
    with connect() as conn:
        # Check if signal exists
        existing = conn.execute(
            "SELECT pk FROM signal WHERE pk = ?",
            (signal_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Build dynamic update query
        updates = []
        params = []
        
        if signal.content is not None:
            updates.append("content = ?")
            params.append(signal.content)
        if signal.priority is not None:
            updates.append("priority = ?")
            params.append(signal.priority)
        if signal.status is not None:
            updates.append("status = ?")
            params.append(signal.status)
        
        if updates:
            query = f"UPDATE signal SET {', '.join(updates)} WHERE pk = ?"
            params.append(signal_id)
            conn.execute(query, tuple(params))
            conn.commit()
    
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
    with connect() as conn:
        # Check if signal exists
        existing = conn.execute(
            "SELECT pk FROM signal WHERE pk = ?",
            (signal_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        conn.execute("DELETE FROM signal WHERE pk = ?", (signal_id,))
        conn.commit()
    
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
