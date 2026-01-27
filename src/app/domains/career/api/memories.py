# src/app/domains/career/api/memories.py
"""
Career Memories API Routes

Endpoints for managing career memories and reflections.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from ....repositories import get_career_repository

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
