# src/app/domains/documents/api/search.py
"""
Document Search API Routes

Full-text and semantic search over documents.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_document_repository
from ..constants import DEFAULT_SEARCH_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search")


@router.get("")
async def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    doc_type: str = Query(None, description="Filter by document type"),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, le=100)
):
    """Search documents by text content."""
    repo = get_document_repository()
    
    # Use repository search if available
    if hasattr(repo, 'search'):
        results = repo.search(q, limit=limit)
    else:
        # Fallback to list + filter
        all_docs = repo.list(limit=200)
        results = [
            d for d in all_docs
            if q.lower() in (d.get("title", "") if isinstance(d, dict) else getattr(d, "title", "")).lower()
            or q.lower() in (d.get("content", "") if isinstance(d, dict) else getattr(d, "content", "")).lower()
        ][:limit]
    
    # Apply type filter
    if doc_type:
        results = [d for d in results if (d.get("doc_type") if isinstance(d, dict) else getattr(d, "doc_type", None)) == doc_type]
    
    return JSONResponse({
        "status": "ok",
        "query": q,
        "results": [r if isinstance(r, dict) else r.__dict__ for r in results],
        "count": len(results)
    })


@router.get("/recent")
async def get_recent_documents(
    days: int = Query(7, le=90, description="Number of days to look back"),
    limit: int = Query(20, le=100)
):
    """Get recently updated documents."""
    from datetime import datetime, timedelta
    
    repo = get_document_repository()
    
    # Get all documents and filter by date
    all_docs = repo.list(limit=500)
    cutoff = datetime.now() - timedelta(days=days)
    
    recent = []
    for doc in all_docs:
        doc_dict = doc if isinstance(doc, dict) else doc.__dict__
        updated = doc_dict.get("updated_at") or doc_dict.get("created_at")
        if updated:
            try:
                doc_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if doc_date.replace(tzinfo=None) > cutoff:
                    recent.append(doc_dict)
            except Exception:
                pass
    
    # Sort by date descending and limit
    recent.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    recent = recent[:limit]
    
    return JSONResponse({
        "status": "ok",
        "days": days,
        "documents": recent,
        "count": len(recent)
    })


@router.get("/by-type/{doc_type}")
async def get_documents_by_type(
    doc_type: str,
    limit: int = Query(50, le=200)
):
    """Get documents filtered by type."""
    repo = get_document_repository()
    
    all_docs = repo.list(limit=500)
    filtered = [
        d if isinstance(d, dict) else d.__dict__
        for d in all_docs
        if (d.get("doc_type") if isinstance(d, dict) else getattr(d, "doc_type", None)) == doc_type
    ][:limit]
    
    return JSONResponse({
        "status": "ok",
        "doc_type": doc_type,
        "documents": filtered,
        "count": len(filtered)
    })
