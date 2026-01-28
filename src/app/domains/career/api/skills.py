# src/app/domains/career/api/skills.py
"""
Skills Tracking API Routes

Endpoints for managing skill tracker data.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from ....repositories import get_career_repository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/skills")
async def get_skills(
    request: Request,
    category: Optional[str] = Query(None),
    limit: int = Query(100),
):
    """Get skills with optional filtering by category.
    
    Returns skills both as flat list and grouped by_category for the skills graph.
    """
    repo = get_career_repository()
    skills = repo.get_skills(category=category, limit=limit)
    
    # Build flat list
    skills_list = [
        {
            "id": s.id,
            "skill_name": s.skill_name,
            "category": s.category,
            "proficiency": s.proficiency,
            "proficiency_level": s.proficiency_level if hasattr(s, 'proficiency_level') else s.proficiency,
            "last_used": s.last_used,
            "context": s.context,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in skills
    ]
    
    # Group by category for skills graph
    by_category = {}
    for skill in skills_list:
        cat = skill.get("category") or "other"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(skill)
    
    return JSONResponse({
        "skills": skills_list,
        "by_category": by_category,
        "count": len(skills_list),
    })


@router.get("/skills/categories")
async def get_skill_categories(request: Request):
    """Get distinct skill categories."""
    repo = get_career_repository()
    categories = repo.get_skill_categories()
    
    return JSONResponse({"categories": categories})


@router.post("/skills")
async def upsert_skill(request: Request):
    """Create or update a skill."""
    data = await request.json()
    
    if not data.get("skill_name"):
        return JSONResponse({"error": "skill_name is required"}, status_code=400)
    
    repo = get_career_repository()
    skill = repo.upsert_skill(data)
    
    if skill:
        return JSONResponse({
            "status": "ok",
            "skill": {
                "id": skill.id,
                "skill_name": skill.skill_name,
                "category": skill.category,
                "proficiency": skill.proficiency,
            }
        })
    return JSONResponse({"error": "Failed to save skill"}, status_code=500)


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: int):
    """Delete a skill by ID."""
    repo = get_career_repository()
    success = repo.delete_skill(skill_id)
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to delete skill"}, status_code=500)
