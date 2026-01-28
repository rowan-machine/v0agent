# src/app/domains/search/api/fulltext.py
"""
Full-text Search API Routes (Legacy HTML Template)

Provides the /search endpoint for HTML template-based search.
This is the legacy search interface using Jinja2 templates.
"""

from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from typing import Optional

from ..services import (
    highlight_match,
    search_documents,
    search_meetings,
    search_meeting_documents,
)

router = APIRouter(tags=["search-fulltext"])
templates = Jinja2Templates(directory="src/app/templates")


@router.get("/search")
def fulltext_search(
    request: Request,
    q: Optional[str] = Query(default=None),
    source_type: str = Query(default="docs"),  # docs | meetings | both | transcripts
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    include_transcripts: bool = Query(default=False),  # F2: Search raw transcripts
    limit: int = 10,
):
    """
    Full-text search with HTML template response.
    
    Searches across documents, meetings, and optionally transcripts.
    Returns rendered HTML template with results.
    """
    results = []

    if q and len(q) >= 2:
        # -------- Documents (from Supabase) --------
        if source_type in ("docs", "both"):
            doc_results = search_documents(q, start_date, end_date, limit)
            results.extend(doc_results)

        # -------- Meetings (from Supabase) --------
        if source_type in ("meetings", "both", "transcripts"):
            search_transcripts = include_transcripts or source_type == "transcripts"
            meeting_results = search_meetings(q, search_transcripts, start_date, end_date, limit)
            results.extend(meeting_results)
        
        # -------- F2: Meeting Documents (linked transcripts/summaries) --------
        if include_transcripts or source_type == "transcripts":
            transcript_results = search_meeting_documents(q, limit)
            results.extend(transcript_results)

    results.sort(key=lambda r: r.get("date") or "", reverse=True)

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q or "",
            "results": results,
            "source_type": source_type,
            "start_date": start_date or "",
            "end_date": end_date or "",
            "include_transcripts": include_transcripts,
        },
    )
