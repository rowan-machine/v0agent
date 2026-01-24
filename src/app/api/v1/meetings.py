# src/app/api/v1/meetings.py
"""
API v1 - Meetings endpoints.

RESTful endpoints for meeting CRUD operations with proper pagination,
HTTP status codes, and Pydantic validation.

Supabase-first with SQLite fallback for Railway ephemeral storage.
"""

import logging
import os
from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, List, Dict, Any

from ..v1.models import (
    MeetingCreate, MeetingUpdate, MeetingResponse,
    PaginatedResponse, APIResponse
)
from ...db import connect

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_meetings_from_supabase(skip: int = 0, limit: int = 50) -> tuple[List[Dict[str, Any]], int]:
    """
    Fetch meetings from Supabase.
    Returns (meetings_list, total_count) or raises exception.
    """
    try:
        from ...infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        # Get total count
        count_result = supabase.table("meetings").select("id", count="exact").execute()
        total = count_result.count if count_result.count is not None else 0
        
        # Get paginated meetings
        result = supabase.table("meetings").select("*").order(
            "created_at", desc=True
        ).range(skip, skip + limit - 1).execute()
        
        meetings = []
        for row in result.data or []:
            meetings.append({
                "id": row.get("id"),
                "name": row.get("meeting_name", ""),
                "notes": row.get("synthesized_notes", ""),
                "date": row.get("meeting_date", ""),
                "created_at": row.get("created_at"),
                "raw_text": row.get("raw_text"),
                "signals_json": row.get("signals"),
            })
        
        logger.info(f"✅ Fetched {len(meetings)} meetings from Supabase")
        return meetings, total
    except Exception as e:
        logger.error(f"❌ Failed to fetch from Supabase: {e}")
        raise


def _get_meetings_from_sqlite(skip: int = 0, limit: int = 50) -> tuple[List[Dict[str, Any]], int]:
    """
    Fetch meetings from SQLite meeting_summaries table.
    Returns (meetings_list, total_count).
    """
    with connect() as conn:
        # Get total count
        total = conn.execute("SELECT COUNT(*) as count FROM meeting_summaries").fetchone()["count"]
        
        # Get paginated meetings
        rows = conn.execute(
            """SELECT id, meeting_name, synthesized_notes, meeting_date, 
                      created_at, raw_text, signals_json
               FROM meeting_summaries
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, skip)
        ).fetchall()
        
        meetings = []
        for row in rows:
            meetings.append({
                "id": row["id"],
                "name": row["meeting_name"] or "",
                "notes": row["synthesized_notes"] or "",
                "date": row["meeting_date"] or "",
                "created_at": row["created_at"],
                "raw_text": row["raw_text"],
                "signals_json": row["signals_json"],
            })
        
        return meetings, total


@router.get("", response_model=PaginatedResponse)
async def list_meetings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    device_id: Optional[str] = Query(None, description="Filter by device ID (ignored for now)"),
):
    """
    List all meetings with pagination.
    
    Returns meetings ordered by most recently created first.
    Uses Supabase as primary source with SQLite fallback.
    """
    # Try Supabase first
    try:
        meetings, total = _get_meetings_from_supabase(skip, limit)
        return PaginatedResponse(items=meetings, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.warning(f"⚠️ Supabase unavailable, falling back to SQLite: {e}")
    
    # Fall back to SQLite
    try:
        meetings, total = _get_meetings_from_sqlite(skip, limit)
        return PaginatedResponse(items=meetings, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.error(f"❌ SQLite also failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch meetings")


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: str):
    """
    Get a single meeting by ID.
    
    Returns 404 if meeting not found.
    Accepts either UUID (Supabase) or integer (SQLite) ID.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        result = supabase.table("meetings").select("*").eq("id", meeting_id).execute()
        if result.data:
            meeting = result.data[0]
            return MeetingResponse(
                id=meeting.get("id"),
                name=meeting.get("meeting_name", ""),
                notes=meeting.get("synthesized_notes"),
                date=meeting.get("meeting_date", ""),
                created_at=meeting.get("created_at"),
                last_modified_at=meeting.get("updated_at")
            )
    except Exception as e:
        logger.warning(f"⚠️ Supabase lookup failed: {e}")
    
    # Fall back to SQLite
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM meeting_summaries WHERE id = ?",
                (int(meeting_id) if meeting_id.isdigit() else -1,)
            ).fetchone()
        
        if row:
            return MeetingResponse(
                id=str(row["id"]),
                name=row["meeting_name"] or "",
                notes=row["synthesized_notes"],
                date=row["meeting_date"] or "",
                created_at=row["created_at"],
                last_modified_at=row["created_at"]
            )
    except Exception as e:
        logger.error(f"❌ SQLite lookup failed: {e}")
    
    raise HTTPException(status_code=404, detail="Meeting not found")


@router.post("", response_model=APIResponse, status_code=201)
async def create_meeting(meeting: MeetingCreate):
    """
    Create a new meeting.
    
    Creates in Supabase first, then syncs to SQLite.
    Returns the created meeting ID.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        result = supabase.table("meetings").insert({
            "meeting_name": meeting.name,
            "synthesized_notes": meeting.notes or "",
            "meeting_date": meeting.date,
        }).execute()
        
        if result.data:
            meeting_id = result.data[0]["id"]
            logger.info(f"✅ Created meeting {meeting_id} in Supabase")
            return APIResponse(success=True, message="Meeting created", data={"id": meeting_id})
    except Exception as e:
        logger.warning(f"⚠️ Supabase create failed, trying SQLite: {e}")
    
    # Fall back to SQLite
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO meeting_summaries (meeting_name, synthesized_notes, meeting_date)
               VALUES (?, ?, ?)""",
            (meeting.name, meeting.notes or "", meeting.date)
        )
        meeting_id = cursor.lastrowid
        conn.commit()
    
    return APIResponse(success=True, message="Meeting created", data={"id": meeting_id})


@router.put("/{meeting_id}", response_model=APIResponse)
async def update_meeting(meeting_id: str, meeting: MeetingUpdate):
    """
    Update an existing meeting.
    
    Only updates fields that are provided.
    Returns 404 if meeting not found.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        # Check if meeting exists
        existing = supabase.table("meetings").select("id").eq("id", meeting_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Build update dict
        updates = {}
        if meeting.name is not None:
            updates["meeting_name"] = meeting.name
        if meeting.notes is not None:
            updates["synthesized_notes"] = meeting.notes
        if meeting.date is not None:
            updates["meeting_date"] = meeting.date
        
        if updates:
            supabase.table("meetings").update(updates).eq("id", meeting_id).execute()
        
        return APIResponse(success=True, message="Meeting updated", data={"id": meeting_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"⚠️ Supabase update failed: {e}")
    
    # Fall back to SQLite
    with connect() as conn:
        sqlite_id = int(meeting_id) if meeting_id.isdigit() else -1
        existing = conn.execute("SELECT id FROM meeting_summaries WHERE id = ?", (sqlite_id,)).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        updates = []
        params = []
        if meeting.name is not None:
            updates.append("meeting_name = ?")
            params.append(meeting.name)
        if meeting.notes is not None:
            updates.append("synthesized_notes = ?")
            params.append(meeting.notes)
        if meeting.date is not None:
            updates.append("meeting_date = ?")
            params.append(meeting.date)
        
        if updates:
            query = f"UPDATE meeting_summaries SET {', '.join(updates)} WHERE id = ?"
            params.append(sqlite_id)
            conn.execute(query, tuple(params))
            conn.commit()
    
    return APIResponse(success=True, message="Meeting updated", data={"id": meeting_id})


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: str):
    """
    Delete a meeting.
    
    Returns 204 No Content on success, 404 if meeting not found.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        # Check if meeting exists
        existing = supabase.table("meetings").select("id").eq("id", meeting_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        supabase.table("meetings").delete().eq("id", meeting_id).execute()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"⚠️ Supabase delete failed: {e}")
    
    # Fall back to SQLite
    with connect() as conn:
        sqlite_id = int(meeting_id) if meeting_id.isdigit() else -1
        existing = conn.execute("SELECT id FROM meeting_summaries WHERE id = ?", (sqlite_id,)).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        conn.execute("DELETE FROM meeting_summaries WHERE id = ?", (sqlite_id,))
        conn.commit()
    
    return Response(status_code=204)
