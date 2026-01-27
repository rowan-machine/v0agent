# src/app/domains/career/api/docs.py
"""
Documentation & Codebase Analysis API Routes

Endpoints for extracting information from repository documentation
and performing codebase assessment.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/docs/adrs")
async def get_documentation_adrs():
    """
    Get Architecture Decision Records from repository documentation.
    
    Returns ADRs with parsed metadata including technologies and status.
    """
    from ....services.documentation_reader import get_adrs
    
    try:
        adrs = get_adrs()
        return JSONResponse({
            "status": "ok",
            "count": len(adrs),
            "adrs": adrs
        })
    except Exception as e:
        logger.error(f"Error reading ADRs: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/docs/ai-implementations")
async def get_documentation_ai_implementations():
    """
    Get AI implementation records extracted from repository documentation.
    
    Scans docs for AI/ML-related content and returns structured implementation records.
    """
    from ....services.documentation_reader import get_ai_implementations
    
    try:
        implementations = get_ai_implementations()
        return JSONResponse({
            "status": "ok",
            "count": len(implementations),
            "implementations": implementations
        })
    except Exception as e:
        logger.error(f"Error extracting AI implementations: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/docs/skill-evidence")
async def get_documentation_skill_evidence():
    """
    Get skill evidence extracted from repository documentation.
    
    Returns technologies/skills mentioned in docs with their source locations.
    """
    from ....services.documentation_reader import get_skill_evidence
    
    try:
        evidence = get_skill_evidence()
        return JSONResponse({
            "status": "ok",
            "skills_count": len(evidence),
            "evidence": evidence
        })
    except Exception as e:
        logger.error(f"Error extracting skill evidence: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/docs/assess-codebase")
async def get_codebase_assessment():
    """
    Get comprehensive codebase assessment.
    
    Analyzes project structure, languages, frameworks, and metrics.
    """
    from ....services.documentation_reader import assess_codebase
    
    try:
        assessment = assess_codebase()
        return JSONResponse({
            "status": "ok",
            "assessment": assessment
        })
    except Exception as e:
        logger.error(f"Error assessing codebase: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/docs/sync-to-memories")
async def sync_docs_to_memories():
    """
    Sync documentation-based AI implementations to career memories.
    
    Imports AI implementation records from docs into the career_memories table.
    """
    from ....services.documentation_reader import get_ai_implementations
    from ....infrastructure.supabase_client import get_supabase_client
    
    try:
        implementations = get_ai_implementations()
        added = []
        updated = []
        
        supabase = get_supabase_client()
        if not supabase:
            return JSONResponse({"error": "Database not configured"}, status_code=500)
        
        for impl in implementations:
            title = impl.get("title", "Unknown Implementation")
            description = impl.get("summary", "")
            technologies = ", ".join(impl.get("technologies", []))
            source = impl.get("source", "docs")
            
            # Check if already exists
            existing = supabase.table("career_memories").select("id").eq(
                "title", title
            ).eq("source_type", "documentation").execute()
            
            if existing.data:
                # Update existing
                supabase.table("career_memories").update({
                    "description": description,
                    "skills": technologies
                }).eq("id", existing.data[0].get("id")).execute()
                updated.append(title)
            else:
                # Insert new
                supabase.table("career_memories").insert({
                    "memory_type": "ai_implementation",
                    "title": title,
                    "description": description,
                    "source_type": "documentation",
                    "skills": technologies,
                    "is_pinned": False,
                    "is_ai_work": True,
                    "metadata": json.dumps({"source": source})
                }).execute()
                added.append(title)
        
        return JSONResponse({
            "status": "ok",
            "added": added,
            "updated": updated,
            "added_count": len(added),
            "updated_count": len(updated)
        })
    except Exception as e:
        logger.error(f"Error syncing docs to memories: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/backends/status")
async def get_backend_status():
    """
    Get status of all configured Supabase backends.
    
    Shows which backends (default, career, analytics) are configured.
    """
    from ....infrastructure.supabase_multi import list_backends
    
    try:
        backends = list_backends()
        return JSONResponse({
            "status": "ok",
            "backends": backends
        })
    except Exception as e:
        logger.error(f"Error checking backends: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
