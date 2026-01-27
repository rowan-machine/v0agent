# src/app/domains/meetings/api/search.py
"""
Meeting Search API Routes

Full-text and semantic search over meetings.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_meeting_repository
from ..constants import DEFAULT_SEARCH_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search")


@router.get("")
async def search_meetings(
    q: str = Query(..., min_length=1, description="Search query"),
    include_transcripts: bool = Query(False, description="Include transcript text in search"),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, le=50)
):
    """Search meetings by text content."""
    repo = get_meeting_repository()
    
    results = repo.search(q, include_transcripts=include_transcripts, limit=limit)
    
    return JSONResponse({
        "status": "ok",
        "query": q,
        "results": [r if isinstance(r, dict) else r.__dict__ for r in results],
        "count": len(results)
    })


@router.get("/date-range")
async def search_by_date_range(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, le=200)
):
    """Get meetings within a date range."""
    repo = get_meeting_repository()
    
    meetings = repo.get_by_date_range(start_date, end_date, limit=limit)
    
    return JSONResponse({
        "status": "ok",
        "start_date": start_date,
        "end_date": end_date,
        "meetings": [m if isinstance(m, dict) else m.__dict__ for m in meetings],
        "count": len(meetings)
    })


@router.get("/recent")
async def get_recent_meetings(
    days: int = Query(7, le=90, description="Number of days to look back"),
    limit: int = Query(20, le=100)
):
    """Get recent meetings from the last N days."""
    from datetime import datetime, timedelta
    
    repo = get_meeting_repository()
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    meetings = repo.get_by_date_range(start_date, end_date, limit=limit)
    
    return JSONResponse({
        "status": "ok",
        "days": days,
        "meetings": [m if isinstance(m, dict) else m.__dict__ for m in meetings],
        "count": len(meetings)
    })
