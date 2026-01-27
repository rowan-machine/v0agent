# src/app/domains/career/api/suggestions.py
"""
Career Suggestions API Routes

Endpoints for managing AI-generated career suggestions.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging

from ....repositories import get_career_repository
from ..services.suggestion_service import generate_career_suggestions

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/suggestions")
async def get_suggestions(
    request: Request,
    status: Optional[str] = Query(None),
    suggestion_type: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Get career suggestions with optional filtering."""
    repo = get_career_repository()
    
    statuses = [status] if status else None
    suggestions = repo.get_suggestions(
        statuses=statuses,
        suggestion_type=suggestion_type,
        limit=limit,
    )
    
    return JSONResponse({
        "suggestions": [
            {
                "id": s.id,
                "suggestion_type": s.suggestion_type,
                "content": s.content,
                "status": s.status,
                "priority": s.priority,
                "created_at": s.created_at,
            }
            for s in suggestions
        ],
        "count": len(suggestions),
    })


@router.post("/suggestions/generate")
async def generate_suggestions(request: Request):
    """Generate new AI suggestions based on profile and context."""
    data = await request.json()
    
    suggestions = await generate_career_suggestions(
        context=data.get("context", {}),
        count=data.get("count", 3),
    )
    
    return JSONResponse({
        "status": "ok",
        "generated": len(suggestions),
        "suggestions": suggestions,
    })


@router.put("/suggestions/{suggestion_id}")
async def update_suggestion(suggestion_id: int, request: Request):
    """Update a suggestion (e.g., accept, dismiss)."""
    data = await request.json()
    
    repo = get_career_repository()
    success = repo.update_suggestion(suggestion_id, data)
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to update suggestion"}, status_code=500)


@router.post("/suggestions/dismiss")
async def dismiss_suggestions(request: Request):
    """Dismiss multiple suggestions at once."""
    data = await request.json()
    suggestion_ids = data.get("ids", [])
    
    if not suggestion_ids:
        return JSONResponse({"error": "No suggestion IDs provided"}, status_code=400)
    
    repo = get_career_repository()
    dismissed = repo.dismiss_suggestions(suggestion_ids)
    
    return JSONResponse({
        "status": "ok",
        "dismissed": dismissed,
    })
