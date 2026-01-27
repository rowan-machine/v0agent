# src/app/domains/career/api/standups.py
"""
Standup Updates API Routes

Endpoints for managing daily standup entries.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from ....repositories import get_career_repository
from ..services.standup_service import analyze_standup

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/standups")
async def get_standups(
    request: Request,
    limit: int = Query(10),
    days_back: Optional[int] = Query(None),
):
    """Get standup updates."""
    repo = get_career_repository()
    standups = repo.get_standups(limit=limit, days_back=days_back)
    
    return JSONResponse({
        "standups": [
            {
                "id": s.id,
                "yesterday": s.yesterday,
                "today": s.today,
                "blockers": s.blockers,
                "mood": s.mood,
                "notes": s.notes,
                "ai_analysis": s.ai_analysis,
                "created_at": s.created_at,
            }
            for s in standups
        ],
        "count": len(standups),
    })


@router.get("/standups/{date}")
async def get_standup_by_date(date: str):
    """Get standup for a specific date (YYYY-MM-DD)."""
    repo = get_career_repository()
    standup = repo.get_standup_by_date(date)
    
    if standup:
        return JSONResponse({
            "id": standup.id,
            "yesterday": standup.yesterday,
            "today": standup.today,
            "blockers": standup.blockers,
            "mood": standup.mood,
            "notes": standup.notes,
            "ai_analysis": standup.ai_analysis,
            "created_at": standup.created_at,
        })
    return JSONResponse({"error": "Standup not found"}, status_code=404)


@router.post("/standups")
async def create_standup(request: Request):
    """Create a new standup update with optional AI analysis."""
    data = await request.json()
    
    repo = get_career_repository()
    
    # Optionally generate AI analysis
    if data.get("analyze", False):
        analysis = await analyze_standup(
            yesterday=data.get("yesterday", ""),
            today=data.get("today", ""),
            blockers=data.get("blockers", ""),
        )
        data["ai_analysis"] = analysis
    
    # Remove the analyze flag before saving
    data.pop("analyze", None)
    
    standup = repo.add_standup(data)
    
    if standup:
        return JSONResponse({
            "status": "ok",
            "id": standup.id,
            "ai_analysis": standup.ai_analysis,
        })
    return JSONResponse({"error": "Failed to create standup"}, status_code=500)


@router.delete("/standups/{standup_id}")
async def delete_standup(standup_id: int):
    """Delete a standup update by ID."""
    repo = get_career_repository()
    success = repo.delete_standup(standup_id)
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to delete standup"}, status_code=500)
