# src/app/domains/career/api/chat.py
"""
Career Chat API Routes

Endpoints for career coaching chat and tweaks.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_career_repository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/chat/updates")
async def get_chat_updates(
    request: Request,
    limit: int = Query(20),
):
    """Get career chat updates."""
    repo = get_career_repository()
    updates = repo.get_chat_updates(limit=limit)
    
    return JSONResponse({
        "updates": updates,
        "count": len(updates),
    })


@router.post("/chat/updates")
async def add_chat_update(request: Request):
    """Add a career chat update."""
    data = await request.json()
    
    repo = get_career_repository()
    update = repo.add_chat_update(data)
    
    if update:
        return JSONResponse({"status": "ok", "id": update.get("id")})
    return JSONResponse({"error": "Failed to add chat update"}, status_code=500)


@router.get("/chat/summary")
async def get_latest_summary(request: Request):
    """Get the latest career summary."""
    repo = get_career_repository()
    summary = repo.get_latest_summary()
    
    return JSONResponse({"summary": summary})


@router.get("/tweaks")
async def get_tweaks(
    request: Request,
    limit: int = Query(50),
):
    """Get career tweaks."""
    repo = get_career_repository()
    tweaks = repo.get_tweaks(limit=limit)
    
    return JSONResponse({
        "tweaks": tweaks,
        "count": len(tweaks),
    })


@router.post("/tweaks")
async def add_tweak(request: Request):
    """Add a career tweak."""
    data = await request.json()
    content = data.get("content", "").strip()
    
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)
    
    repo = get_career_repository()
    tweak = repo.add_tweak(content)
    
    if tweak:
        return JSONResponse({"status": "ok", "id": tweak.get("id")})
    return JSONResponse({"error": "Failed to add tweak"}, status_code=500)


@router.delete("/tweaks/{tweak_id}")
async def delete_tweak(tweak_id: int):
    """Delete a career tweak by ID."""
    repo = get_career_repository()
    success = repo.delete_tweak(tweak_id)
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to delete tweak"}, status_code=500)
