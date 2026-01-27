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
from ....services import ticket_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["career-projects"])


@router.get("/completed-projects")
async def get_completed_projects():
    """Get completed projects from tickets and career memories."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"tickets": [], "memories": []})
    
    # Get completed tickets
    tickets_result = supabase.table("tickets").select("*").in_(
        "status", ["done", "complete", "completed"]
    ).order("updated_at", desc=True).limit(50).execute()
    
    all_tickets = tickets_result.data or []
    
    # Get memories that are already synced
    synced_result = supabase.table("career_memories").select("source_id").eq(
        "source_type", "ticket"
    ).execute()
    synced_ids = {str(m.get("source_id")) for m in (synced_result.data or [])}
    
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
    
    # Get completed project memories
    memories_result = supabase.table("career_memories").select("*").eq(
        "memory_type", "completed_project"
    ).order("is_pinned", desc=True).order("created_at", desc=True).execute()
    
    return JSONResponse({
        "tickets": tickets,
        "memories": memories_result.data or []
    })


@router.post("/sync-completed-projects")
async def sync_completed_projects():
    """Sync completed tickets to career memories."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    all_tickets = ticket_service.get_all_tickets()
    completed_tickets = [t for t in all_tickets if t.get("status") in ('done', 'complete', 'completed')]
    
    existing_result = supabase.table("career_memories").select("source_id").eq(
        "source_type", "ticket"
    ).execute()
    existing_ids = {str(row.get("source_id")) for row in (existing_result.data or [])}
    
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
        
        supabase.table("career_memories").insert({
            "memory_type": "completed_project",
            "title": t.get("title") or "",
            "description": t.get("ai_summary") or t.get("description") or "",
            "source_type": "ticket",
            "source_id": str(t.get("id")),
            "skills": skills,
            "is_pinned": False,
            "metadata": metadata
        }).execute()
        added += 1
    
    return JSONResponse({"status": "ok", "added": added})


@router.get("/development-tracker")
async def get_development_tracker():
    """Get development tracker data - skill progress and learning activities."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"skills": [], "activities": [], "projects": [], "summary": {}})
    
    # Get recent skill changes
    skills_result = supabase.table("skill_tracker").select(
        "skill_name,category,proficiency_level,evidence,updated_at,projects_count"
    ).gt("proficiency_level", 0).order("updated_at", desc=True).order(
        "proficiency_level", desc=True
    ).limit(20).execute()
    skills = skills_result.data or []
    
    # Get recent career memories as learning activities
    memories_result = supabase.table("career_memories").select(
        "id,memory_type,title,description,skills,created_at"
    ).in_("memory_type", ["skill_milestone", "achievement"]).order(
        "created_at", desc=True
    ).limit(10).execute()
    memories = memories_result.data or []
    
    # Get completed projects from career_memories
    projects_result = supabase.table("career_memories").select(
        "id,title,skills,description,created_at"
    ).or_("memory_type.eq.completed_project,is_ai_work.eq.true").order(
        "created_at", desc=True
    ).limit(5).execute()
    
    projects = []
    for p in (projects_result.data or []):
        projects.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "technologies": p.get("skills"),
            "impact": p.get("description"),
            "completed_date": p.get("created_at")
        })
    
    # Calculate summary stats
    all_skills_result = supabase.table("skill_tracker").select("proficiency_level").gt(
        "proficiency_level", 0
    ).execute()
    all_skills = all_skills_result.data or []
    total_skills = len(all_skills)
    avg_proficiency = sum(s.get("proficiency_level", 0) for s in all_skills) / total_skills if total_skills else 0
    
    skill_levels = {
        "beginner": len([s for s in all_skills if 1 <= s.get("proficiency_level", 0) <= 30]),
        "intermediate": len([s for s in all_skills if 31 <= s.get("proficiency_level", 0) <= 60]),
        "advanced": len([s for s in all_skills if 61 <= s.get("proficiency_level", 0) <= 85]),
        "expert": len([s for s in all_skills if s.get("proficiency_level", 0) > 85]),
    }
    
    return JSONResponse({
        "skills": skills,
        "activities": memories,
        "projects": projects,
        "summary": {
            "total_skills": total_skills,
            "avg_proficiency": round(avg_proficiency, 1),
            "skill_levels": skill_levels
        }
    })


__all__ = ["router"]
