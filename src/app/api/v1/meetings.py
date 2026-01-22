# src/app/api/v1/meetings.py
"""
API v1 - Meetings endpoints.

RESTful endpoints for meeting CRUD operations with proper pagination,
HTTP status codes, and Pydantic validation.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional

from ..v1.models import (
    MeetingCreate, MeetingUpdate, MeetingResponse,
    PaginatedResponse, APIResponse
)
from ...db import connect

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_meetings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
):
    """
    List all meetings with pagination.
    
    Returns meetings ordered by most recently modified first.
    """
    with connect() as conn:
        # Build query with optional device filter
        query = "SELECT * FROM meeting"
        params = []
        
        if device_id:
            query += " WHERE synced_from_device = ?"
            params.append(device_id)
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
        total = conn.execute(count_query, tuple(params)).fetchone()["count"]
        
        # Add pagination
        query += " ORDER BY pk DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])
        
        rows = conn.execute(query, tuple(params)).fetchall()
        meetings = [dict(row) for row in rows]
    
    return PaginatedResponse(
        items=meetings,
        skip=skip,
        limit=limit,
        total=total
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: int):
    """
    Get a single meeting by ID.
    
    Returns 404 if meeting not found.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM meeting WHERE pk = ?",
            (meeting_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting = dict(row)
    return MeetingResponse(
        id=meeting.get("pk"),
        name=meeting.get("name", ""),
        notes=meeting.get("notes"),
        date=meeting.get("date", ""),
        created_at=meeting.get("created_at"),
        last_modified_at=meeting.get("last_modified_at")
    )


@router.post("", response_model=APIResponse, status_code=201)
async def create_meeting(meeting: MeetingCreate):
    """
    Create a new meeting.
    
    Returns the created meeting ID.
    """
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO meeting (name, notes, date, synced_from_device)
               VALUES (?, ?, ?, ?)""",
            (meeting.name, meeting.notes, meeting.date, meeting.device_id)
        )
        meeting_id = cursor.lastrowid
        conn.commit()
    
    return APIResponse(
        success=True,
        message="Meeting created",
        data={"id": meeting_id}
    )


@router.put("/{meeting_id}", response_model=APIResponse)
async def update_meeting(meeting_id: int, meeting: MeetingUpdate):
    """
    Update an existing meeting.
    
    Only updates fields that are provided.
    Returns 404 if meeting not found.
    """
    with connect() as conn:
        # Check if meeting exists
        existing = conn.execute(
            "SELECT pk FROM meeting WHERE pk = ?",
            (meeting_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Build dynamic update query
        updates = []
        params = []
        
        if meeting.name is not None:
            updates.append("name = ?")
            params.append(meeting.name)
        if meeting.notes is not None:
            updates.append("notes = ?")
            params.append(meeting.notes)
        if meeting.date is not None:
            updates.append("date = ?")
            params.append(meeting.date)
        
        if updates:
            query = f"UPDATE meeting SET {', '.join(updates)} WHERE pk = ?"
            params.append(meeting_id)
            conn.execute(query, tuple(params))
            conn.commit()
    
    return APIResponse(
        success=True,
        message="Meeting updated",
        data={"id": meeting_id}
    )


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: int):
    """
    Delete a meeting.
    
    Returns 204 No Content on success, 404 if meeting not found.
    """
    with connect() as conn:
        # Check if meeting exists
        existing = conn.execute(
            "SELECT pk FROM meeting WHERE pk = ?",
            (meeting_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        conn.execute("DELETE FROM meeting WHERE pk = ?", (meeting_id,))
        conn.commit()
    
    return Response(status_code=204)
