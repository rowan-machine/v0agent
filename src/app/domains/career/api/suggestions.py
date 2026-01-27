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


@router.post("/suggestions/{suggestion_id}/status")
async def update_suggestion_status(suggestion_id: int, request: Request):
    """Update the status of a career suggestion."""
    data = await request.json()
    status = data.get("status")
    
    repo = get_career_repository()
    success = repo.update_suggestion(suggestion_id, {"status": status})
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to update suggestion status"}, status_code=500)


@router.post("/suggestions/{suggestion_id}/to-ticket")
async def convert_suggestion_to_ticket(suggestion_id: int, request: Request):
    """Convert a career suggestion to a ticket."""
    try:
        repo = get_career_repository()
        suggestion = repo.get_suggestion_by_id(suggestion_id)
        
        if not suggestion:
            return JSONResponse({"error": "Suggestion not found"}, status_code=404)
        
        # Create ticket from suggestion
        from ....infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        if not supabase:
            return JSONResponse({"error": "Database not configured"}, status_code=500)
        
        ticket_id = f"CAREER-{suggestion_id}"
        description = suggestion.content or ""
        
        # Build description from suggestion attributes if available
        if hasattr(suggestion, 'description'):
            description = suggestion.description or description
        if hasattr(suggestion, 'rationale') and suggestion.rationale:
            description += f"\n\n**Rationale:** {suggestion.rationale}"
        
        ticket_result = supabase.table("tickets").insert({
            "ticket_id": ticket_id,
            "title": getattr(suggestion, 'title', None) or suggestion.content[:100],
            "description": description,
            "status": "backlog",
            "priority": "medium",
            "tags": "career,growth"
        }).execute()
        
        ticket_db_id = ticket_result.data[0].get("id") if ticket_result.data else None
        
        # Update suggestion status
        repo.update_suggestion(suggestion_id, {
            "status": "accepted",
            "converted_to_ticket": ticket_db_id
        })
        
        return JSONResponse({
            "status": "ok",
            "ticket_id": ticket_id,
            "ticket_db_id": ticket_db_id
        })
    
    except Exception as e:
        logger.exception("Error converting suggestion to ticket")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/suggestions/compress")
async def compress_suggestions(request: Request):
    """Compress/deduplicate AI suggestions using LLM analysis."""
    try:
        from ....infrastructure.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        if not supabase:
            return JSONResponse({"error": "Database not configured"}, status_code=500)
        
        # Get all active suggestions
        result = supabase.table("career_suggestions").select(
            "id, title, description, suggestion_type, rationale"
        ).eq("status", "suggested").order("created_at", desc=True).execute()
        rows = result.data or []
        
        if len(rows) < 2:
            return JSONResponse({
                "status": "ok",
                "merged": 0,
                "removed": 0,
                "message": "Not enough suggestions to compress"
            })
        
        # Prepare for LLM analysis
        suggestions_text = "\n".join([
            f"[ID:{r.get('id')}] {r.get('title')}: {(r.get('description') or '')[:200]}"
            for r in rows
        ])
        
        prompt = f"""Analyze these career suggestions and identify duplicates or very similar items.
Return a JSON object with:
- "groups": array of arrays, each containing IDs that should be merged (keep first, remove rest)
- "remove": array of IDs to remove entirely (low quality or superseded)

Suggestions:
{suggestions_text}

Rules:
1. Group suggestions that have the same core advice or recommendation
2. Mark as remove any that are vague, unhelpful, or completely duplicated
3. Only group items that are truly about the same thing
4. Return valid JSON only, no markdown"""

        from ....llm import ask as ask_llm
        response = ask_llm(prompt, model="gpt-4o-mini")
        
        # Parse response
        try:
            import json as json_module
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            llm_result = json_module.loads(response)
        except Exception:
            return JSONResponse({
                "status": "ok",
                "merged": 0,
                "removed": 0,
                "message": "Could not parse LLM response"
            })
        
        merged = 0
        removed = 0
        
        # Process groups - keep first, remove rest
        for group in llm_result.get("groups", []):
            if len(group) > 1:
                to_remove = group[1:]
                for rid in to_remove:
                    supabase.table("career_suggestions").update(
                        {"status": "dismissed"}
                    ).eq("id", rid).execute()
                    merged += 1
        
        # Process removals
        for rid in llm_result.get("remove", []):
            supabase.table("career_suggestions").update(
                {"status": "dismissed"}
            ).eq("id", rid).execute()
            removed += 1
        
        return JSONResponse({
            "status": "ok",
            "merged": merged,
            "removed": removed
        })
    
    except Exception as e:
        logger.exception("Error compressing suggestions")
        return JSONResponse({"error": str(e)}, status_code=500)
