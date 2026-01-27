# src/app/domains/career/api/memories.py
"""
Career Memories API Routes

Endpoints for managing career memories and reflections,
including AI implementation memories.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional
import json
import logging

from ....repositories import get_career_repository
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/memories")
async def get_memories(
    request: Request,
    category: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Get career memories with optional filtering."""
    repo = get_career_repository()
    memories = repo.get_memories(category=category, limit=limit)
    
    return JSONResponse({
        "memories": [
            {
                "id": m.id,
                "memory_text": m.memory_text,
                "category": m.category,
                "importance": m.importance,
                "created_at": m.created_at,
            }
            for m in memories
        ],
        "count": len(memories),
    })


@router.post("/memories")
async def add_memory(request: Request):
    """Add a new career memory."""
    data = await request.json()
    
    if not data.get("memory_text"):
        return JSONResponse({"error": "memory_text is required"}, status_code=400)
    
    repo = get_career_repository()
    memory = repo.add_memory(data)
    
    if memory:
        return JSONResponse({
            "status": "ok",
            "id": memory.id,
        })
    return JSONResponse({"error": "Failed to add memory"}, status_code=500)


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int):
    """Delete a career memory by ID."""
    repo = get_career_repository()
    success = repo.delete_memory(memory_id)
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to delete memory"}, status_code=500)


# =============================================================================
# AI Implementation Memories
# =============================================================================

@router.post("/ai-memories")
async def add_ai_implementation_memory(request: Request):
    """Add a memory specifically for AI implementation work in this app."""
    data = await request.json()
    title = data.get("title")
    description = data.get("description")
    skills = data.get("skills", "AI/ML Integration, LLM APIs, Prompt Engineering")
    
    if not title:
        return JSONResponse({"error": "Title is required"}, status_code=400)
    
    metadata = json.dumps({
        "app": "v0agent",
        "type": "ai_implementation",
        "features": data.get("features", [])
    })
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("career_memories").insert({
        "memory_type": "ai_implementation",
        "title": title,
        "description": description,
        "source_type": "codebase",
        "skills": skills,
        "is_pinned": False,
        "is_ai_work": True,
        "metadata": metadata
    }).execute()
    
    memory_id = result.data[0].get("id") if result.data else None
    
    return JSONResponse({"status": "ok", "id": memory_id})


@router.get("/ai-memories")
async def get_ai_memories():
    """Get all AI implementation memories."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    result = supabase.table("career_memories").select("*").eq(
        "is_ai_work", True
    ).order("is_pinned", desc=True).order("created_at", desc=True).execute()
    
    return JSONResponse(result.data or [])


@router.delete("/ai-memories/{memory_id}")
async def delete_ai_memory(memory_id: int):
    """Delete an AI implementation memory."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("career_memories").delete().eq("id", memory_id).eq("is_ai_work", True).execute()
    return JSONResponse({"status": "ok", "deleted": memory_id})


@router.post("/ai-memories/compress")
async def compress_ai_memories(request: Request):
    """Compress AI memories by removing duplicates and merging similar entries."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Get all AI memories
    result = supabase.table("career_memories").select(
        "id,title,description,technologies,skills"
    ).eq("is_ai_work", True).order("created_at", desc=True).execute()
    
    memories = result.data or []
    
    if len(memories) <= 1:
        return JSONResponse({
            "status": "ok",
            "removed": 0,
            "merged": 0,
            "message": "Not enough memories to compress"
        })
    
    removed = 0
    merged = 0
    
    # Find and remove exact duplicates (same title)
    seen_titles = {}
    for mem in memories:
        title_lower = (mem.get('title') or '').lower().strip()
        if title_lower in seen_titles:
            # Delete duplicate
            supabase.table("career_memories").delete().eq("id", mem.get('id')).execute()
            removed += 1
        else:
            seen_titles[title_lower] = mem.get('id')
    
    # Find similar entries (same technologies) and merge their skills
    if len(memories) > 3:
        tech_groups = {}
        for mem in memories:
            tech = (mem.get('technologies') or '').lower().strip()
            if tech:
                if tech not in tech_groups:
                    tech_groups[tech] = []
                tech_groups[tech].append(mem)
        
        # Merge groups with same technology
        for tech, group in tech_groups.items():
            if len(group) > 1:
                # Keep the first one, merge skills from others
                keeper = group[0]
                all_skills = set((keeper.get('skills') or '').split(','))
                all_skills = {s.strip() for s in all_skills if s.strip()}
                
                for other in group[1:]:
                    other_skills = (other.get('skills') or '').split(',')
                    for s in other_skills:
                        if s.strip():
                            all_skills.add(s.strip())
                    # Delete the duplicate
                    supabase.table("career_memories").delete().eq("id", other.get('id')).execute()
                    removed += 1
                
                # Update the keeper with merged skills
                if all_skills:
                    supabase.table("career_memories").update({
                        "skills": ','.join(sorted(all_skills))
                    }).eq("id", keeper.get('id')).execute()
                    merged += 1
    
    return JSONResponse({
        "status": "ok",
        "removed": removed,
        "merged": merged,
        "message": f"Removed {removed} duplicates, merged {merged} entries"
    })
