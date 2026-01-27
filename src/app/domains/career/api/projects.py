# src/app/domains/career/api/projects.py
"""
Career Projects API Routes

Handles completed projects, development tracker, and project sync.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json
import logging

from ....infrastructure.supabase_client import get_supabase_client
from ....repositories import get_career_repository
from ....services import ticket_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["career-projects"])


@router.get("/completed-projects")
async def get_completed_projects():
    """Get completed projects from tickets and career memories."""
    career_repo = get_career_repository()
    supabase = get_supabase_client()
    
    if not supabase:
        return JSONResponse({"tickets": [], "memories": []})
    
    # Get completed tickets
    tickets_result = supabase.table("tickets").select("*").in_(
        "status", ["done", "complete", "completed"]
    ).order("updated_at", desc=True).limit(50).execute()
    
    all_tickets = tickets_result.data or []
    
    # Get memories that are already synced using repository
    synced_ids = set(career_repo.get_synced_source_ids("ticket"))
    
    # Filter tickets to only those not yet synced
    tickets = []
    for t in all_tickets:
        if str(t.get("id")) not in synced_ids:
            files_result = supabase.table("ticket_files").select("filename").eq(
                "ticket_id", t.get("id")
            ).execute()
            file_names = [f.get("filename") for f in (files_result.data or [])]
            t["files"] = ",".join(file_names) if file_names else None
            tickets.append(t)
    
    # Get completed project memories using repository
    memories = career_repo.get_memories_by_type("completed_project", limit=100, order_by_pinned=True)
    
    return JSONResponse({
        "tickets": tickets,
        "memories": memories
    })


@router.post("/sync-completed-projects")
async def sync_completed_projects():
    """Sync completed tickets to career memories."""
    career_repo = get_career_repository()
    
    all_tickets = ticket_service.get_all_tickets()
    completed_tickets = [t for t in all_tickets if t.get("status") in ('done', 'complete', 'completed')]
    
    # Get existing synced IDs using repository
    existing_ids = set(career_repo.get_synced_source_ids("ticket"))
    
    added = 0
    for t in completed_tickets:
        if str(t.get("id")) in existing_ids:
            continue
            
        skills = t.get("tags") or ""
        metadata = json.dumps({
            "ticket_id": t.get("ticket_id"),
            "status": t.get("status"),
            "completed_at": t.get("updated_at")
        })
        
        career_repo.add_memory({
            "memory_type": "completed_project",
            "title": t.get("title") or "",
            "description": t.get("ai_summary") or t.get("description") or "",
            "source_type": "ticket",
            "source_id": str(t.get("id")),
            "skills": skills,
            "is_pinned": False,
            "metadata": metadata
        })
        added += 1
    
    return JSONResponse({"status": "ok", "added": added})


@router.get("/development-tracker")
async def get_development_tracker():
    """Get development tracker data - skill progress and learning activities."""
    career_repo = get_career_repository()
    
    # Get recent skills with proficiency > 0
    skills_entries = career_repo.get_skills(min_proficiency=1, limit=20, order_by="updated_at")
    skills = [
        {
            "skill_name": s.skill_name,
            "category": s.category,
            "proficiency_level": s.proficiency_level,
            "evidence": s.evidence,
            "updated_at": s.updated_at,
            "projects_count": s.projects_count
        }
        for s in skills_entries
    ]
    
    # Get recent career memories as learning activities
    memories = career_repo.get_memories_by_types(
        memory_types=["skill_milestone", "achievement"],
        limit=10
    )
    
    # Get completed projects from career_memories
    project_data = career_repo.get_project_memories(limit=5)
    projects = [
        {
            "id": p.get("id"),
            "title": p.get("title"),
            "technologies": p.get("skills"),
            "impact": p.get("description"),
            "completed_date": p.get("created_at")
        }
        for p in project_data
    ]
    
    # Calculate summary stats using repository
    summary = career_repo.get_skill_summary()
    
    return JSONResponse({
        "skills": skills,
        "activities": memories,
        "projects": projects,
        "summary": summary
    })


__all__ = ["router"]
