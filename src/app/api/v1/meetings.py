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
from ...infrastructure.supabase_client import get_supabase_client

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
            "meeting_date", desc=True
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


@router.get("", response_model=PaginatedResponse)
async def list_meetings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    device_id: Optional[str] = Query(None, description="Filter by device ID (ignored for now)"),
):
    """
    List all meetings with pagination.
    
    Returns meetings ordered by most recently created first.
    Uses Supabase as primary source.
    """
    try:
        meetings, total = _get_meetings_from_supabase(skip, limit)
        return PaginatedResponse(items=meetings, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.error(f"❌ Failed to fetch meetings: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch meetings")


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: str):
    """
    Get a single meeting by ID.
    
    Returns 404 if meeting not found.
    Accepts UUID (Supabase) ID.
    """
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
        logger.error(f"❌ Supabase lookup failed: {e}")
    
    raise HTTPException(status_code=404, detail="Meeting not found")


@router.post("", response_model=APIResponse, status_code=201)
async def create_meeting(meeting: MeetingCreate):
    """
    Create a new meeting.
    
    Creates in Supabase.
    Returns the created meeting ID.
    """
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
        logger.error(f"❌ Supabase create failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create meeting")


@router.put("/{meeting_id}", response_model=APIResponse)
async def update_meeting(meeting_id: str, meeting: MeetingUpdate):
    """
    Update an existing meeting.
    
    Only updates fields that are provided.
    Returns 404 if meeting not found.
    """
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
        logger.error(f"❌ Supabase update failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update meeting")


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: str):
    """
    Delete a meeting.
    
    Returns 204 No Content on success, 404 if meeting not found.
    """
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
        logger.error(f"❌ Supabase delete failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete meeting")
