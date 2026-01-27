# src/app/domains/search/api/keyword.py
"""
Keyword Search API Routes

Traditional text-based search using PostgreSQL ILIKE.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search-keyword"])


@router.get("/keyword")
async def keyword_search(
    q: str = Query(None, min_length=2, max_length=1000, description="Search query"),
    source_type: str = Query("both", pattern="^(docs|meetings|both)$"),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(10, ge=1, le=100),
):
    """
    Keyword-based search across documents and meetings.
    """
    if not q:
        return {"results": [], "query": "", "total_results": 0, "search_type": "keyword"}
    
    results = []
    supabase = get_supabase_client()
    
    if not supabase:
        logger.warning("Supabase not configured for keyword search")
        return {"results": [], "query": q, "total_results": 0, "search_type": "keyword"}
    
    # Search documents
    if source_type in ("docs", "both"):
        query = supabase.table("documents").select("id, source, content, document_date, created_at")
        query = query.or_(f"content.ilike.%{q}%,source.ilike.%{q}%")
        
        if start_date:
            query = query.gte("document_date", start_date)
        if end_date:
            query = query.lte("document_date", end_date)
        
        query = query.order("document_date", desc=True).limit(limit)
        result = query.execute()
        
        for doc in (result.data or []):
            content = doc.get("content") or ""
            q_lower = q.lower()
            idx = content.lower().find(q_lower)
            
            if idx >= 0:
                start = max(0, idx - 100)
                end = min(len(content), idx + len(q) + 100)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
            else:
                snippet = content[:200] + "..." if len(content) > 200 else content
            
            results.append({
                "id": str(doc["id"]),
                "source_type": "document",
                "title": doc.get("source") or "Untitled Document",
                "snippet": snippet,
                "date": doc.get("document_date"),
                "score": 1.0,
            })
    
    # Search meetings
    if source_type in ("meetings", "both"):
        query = supabase.table("meetings").select("id, meeting_name, raw_text, meeting_date, signals_json")
        query = query.or_(f"meeting_name.ilike.%{q}%,raw_text.ilike.%{q}%")
        
        if start_date:
            query = query.gte("meeting_date", start_date)
        if end_date:
            query = query.lte("meeting_date", end_date)
        
        query = query.order("meeting_date", desc=True).limit(limit)
        result = query.execute()
        
        for mtg in (result.data or []):
            raw_text = mtg.get("raw_text") or ""
            q_lower = q.lower()
            idx = raw_text.lower().find(q_lower)
            
            if idx >= 0:
                start = max(0, idx - 100)
                end = min(len(raw_text), idx + len(q) + 100)
                snippet = raw_text[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(raw_text):
                    snippet = snippet + "..."
            else:
                snippet = raw_text[:200] + "..." if len(raw_text) > 200 else raw_text
            
            results.append({
                "id": str(mtg["id"]),
                "source_type": "meeting",
                "title": mtg.get("meeting_name") or "Untitled Meeting",
                "snippet": snippet,
                "date": mtg.get("meeting_date"),
                "score": 1.0,
            })
    
    return {
        "results": results[:limit],
        "query": q,
        "total_results": len(results),
        "search_type": "keyword"
    }


@router.get("/health")
async def search_health():
    """Check search service health."""
    supabase = get_supabase_client()
    
    return {
        "status": "ok",
        "supabase_connected": supabase is not None,
    }


__all__ = ["router"]
