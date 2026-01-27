# src/app/domains/career/api/code_locker.py
"""
Code Locker API Routes

Endpoints for storing and retrieving code snippets linked to tickets.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from ....repositories import get_career_repository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/code-locker")
async def get_code_entries(
    request: Request,
    ticket_id: Optional[int] = Query(None),
    filename: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Get code locker entries with optional filtering."""
    repo = get_career_repository()
    entries = repo.get_code_entries(
        ticket_id=ticket_id,
        filename=filename,
        limit=limit,
    )
    
    return JSONResponse({
        "entries": [
            {
                "id": e.id,
                "filename": e.filename,
                "content": e.content,
                "ticket_id": e.ticket_id,
                "version": e.version,
                "description": e.description,
                "created_at": e.created_at,
            }
            for e in entries
        ],
        "count": len(entries),
    })


@router.get("/code-locker/latest")
async def get_latest_code(
    ticket_id: int = Query(...),
    filename: str = Query(...),
):
    """Get the latest version of code for a file/ticket."""
    repo = get_career_repository()
    entry = repo.get_latest_code(ticket_id=ticket_id, filename=filename)
    
    if entry:
        return JSONResponse({
            "id": entry.id,
            "filename": entry.filename,
            "content": entry.content,
            "ticket_id": entry.ticket_id,
            "version": entry.version,
            "description": entry.description,
            "created_at": entry.created_at,
        })
    return JSONResponse({"error": "Code entry not found"}, status_code=404)


@router.post("/code-locker")
async def add_code_entry(request: Request):
    """Add a new code locker entry."""
    data = await request.json()
    
    if not data.get("filename"):
        return JSONResponse({"error": "filename is required"}, status_code=400)
    if not data.get("content"):
        return JSONResponse({"error": "content is required"}, status_code=400)
    if not data.get("ticket_id"):
        return JSONResponse({"error": "ticket_id is required"}, status_code=400)
    
    repo = get_career_repository()
    
    # Auto-increment version
    if "version" not in data:
        data["version"] = repo.get_next_version(
            ticket_id=data["ticket_id"],
            filename=data["filename"],
        )
    
    entry = repo.add_code_entry(data)
    
    if entry:
        return JSONResponse({
            "status": "ok",
            "id": entry.id,
            "version": entry.version,
        })
    return JSONResponse({"error": "Failed to add code entry"}, status_code=500)
