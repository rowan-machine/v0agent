# src/app/domains/career/api/profile.py
"""
Career Profile API Routes

Endpoints for managing career profile data.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_career_repository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/profile")
async def get_career_profile(request: Request):
    """Get the current career profile."""
    repo = get_career_repository()
    profile = repo.get_profile()
    
    if profile:
        return JSONResponse(profile.to_dict())
    return JSONResponse({}, status_code=404)


@router.post("/profile")
async def update_career_profile(request: Request):
    """Update the career profile."""
    data = await request.json()
    
    repo = get_career_repository()
    success = repo.update_profile(data)
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to update profile"}, status_code=500)


@router.get("/profile/insights")
async def get_profile_insights(request: Request):
    """Get the latest profile insights."""
    repo = get_career_repository()
    insights = repo.get_profile_insights()
    
    if insights:
        return JSONResponse(insights)
    return JSONResponse({"last_insights": None, "updated_at": None})
