# src/app/domains/meetings/api/crud.py
"""
Meeting CRUD API Routes

Basic create, read, update, delete operations for meetings.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

from ....repositories import get_meeting_repository
from ..constants import DEFAULT_MEETING_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items")


@router.get("")
async def list_meetings(
    limit: int = Query(DEFAULT_MEETING_LIMIT, le=200),
    offset: int = Query(0, ge=0),
    status: str = Query("active")
):
    """List meetings with pagination."""
    repo = get_meeting_repository()
    
    meetings = repo.list(limit=limit, offset=offset)
    
    return JSONResponse({
        "status": "ok",
        "meetings": [m if isinstance(m, dict) else m.__dict__ for m in meetings],
        "count": len(meetings),
        "limit": limit,
        "offset": offset
    })


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str):
    """Get a specific meeting by ID."""
    repo = get_meeting_repository()
    
    meeting = repo.get(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    meeting_dict = meeting if isinstance(meeting, dict) else meeting.__dict__
    return JSONResponse({"status": "ok", "meeting": meeting_dict})


@router.post("")
async def create_meeting(request: Request):
    """Create a new meeting."""
    data = await request.json()
    
    repo = get_meeting_repository()
    
    # Validate required fields
    if not data.get("meeting_name"):
        return JSONResponse({"error": "meeting_name is required"}, status_code=400)
    
    meeting = repo.create(data)
    if not meeting:
        return JSONResponse({"error": "Failed to create meeting"}, status_code=500)
    
    meeting_dict = meeting if isinstance(meeting, dict) else meeting.__dict__
    return JSONResponse({"status": "ok", "meeting": meeting_dict}, status_code=201)


@router.put("/{meeting_id}")
async def update_meeting(meeting_id: str, request: Request):
    """Update an existing meeting."""
    data = await request.json()
    
    repo = get_meeting_repository()
    
    # Check exists
    existing = repo.get(meeting_id)
    if not existing:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    updated = repo.update(meeting_id, data)
    if not updated:
        return JSONResponse({"error": "Failed to update meeting"}, status_code=500)
    
    updated_dict = updated if isinstance(updated, dict) else updated.__dict__
    return JSONResponse({"status": "ok", "meeting": updated_dict})


@router.delete("/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete a meeting (soft delete)."""
    repo = get_meeting_repository()
    
    # Check exists
    existing = repo.get(meeting_id)
    if not existing:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    success = repo.delete(meeting_id)
    if not success:
        return JSONResponse({"error": "Failed to delete meeting"}, status_code=500)
    
    return JSONResponse({"status": "ok", "message": "Meeting deleted"})


@router.get("/by-date/{date}")
async def get_meetings_by_date(date: str):
    """Get meetings for a specific date."""
    repo = get_meeting_repository()
    
    try:
        # Validate date format
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return JSONResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status_code=400)
    
    meetings = repo.get_by_date_range(date, date)
    
    return JSONResponse({
        "status": "ok",
        "date": date,
        "meetings": [m if isinstance(m, dict) else m.__dict__ for m in meetings],
        "count": len(meetings)
    })
