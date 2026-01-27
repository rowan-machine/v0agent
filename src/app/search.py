from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from .infrastructure.supabase_client import get_supabase_client
from .services import documents_supabase, meetings_supabase
from typing import Optional
import re

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


def date_clause(start_date, end_date, date_field="created_at"):
    clauses = []
    params = []

    if start_date:
        clauses.append(f"{date_field} >= ?")
        params.append(start_date)

    if end_date:
        clauses.append(f"{date_field} <= ?")
        params.append(end_date)

    return clauses, params


def highlight_match(text: str, query: str, context_chars: int = 100) -> str:
    """
    Extract snippet with query highlighted and surrounding context.
    
    Returns text with the match and context, with <mark> tags around matches.
    """
    if not text or not query:
        return text[:300] if text else ""
    
    # Find first occurrence (case-insensitive)
    lower_text = text.lower()
    lower_query = query.lower()
    
    match_pos = lower_text.find(lower_query)
    if match_pos == -1:
        return text[:300]
    
    # Get context around match
    start = max(0, match_pos - context_chars)
    end = min(len(text), match_pos + len(query) + context_chars)
    
    snippet = text[start:end]
    
    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    # Highlight all occurrences of query in snippet (case-insensitive)
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    snippet = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)
    
    return snippet


def _search_documents_supabase(query: str, start_date: str = None, end_date: str = None, limit: int = 10) -> list:
    """Search documents using Supabase."""
    all_docs = documents_supabase.get_all_documents()
    results = []
    
    like = query.lower()
    for d in all_docs:
        content = (d.get("content") or "").lower()
        source = (d.get("source") or "").lower()
        doc_date = d.get("document_date") or d.get("created_at") or ""
        
        # Date filtering
        if start_date and doc_date < start_date:
            continue
        if end_date and doc_date > end_date:
            continue
        
        # Content/source matching
        if like in content or like in source:
            results.append({
                "type": "document",
                "id": d["id"],
                "title": d.get("source") or "Untitled",
                "snippet": highlight_match(d.get("content") or "", query),
                "date": doc_date,
            })
            if len(results) >= limit:
                break
    
    return results


def _search_meetings_supabase(query: str, include_transcripts: bool, start_date: str = None, end_date: str = None, limit: int = 10) -> list:
    """Search meetings using Supabase."""
    all_meetings = meetings_supabase.get_all_meetings()
    results = []
    
    like = query.lower()
    for m in all_meetings:
        notes = (m.get("synthesized_notes") or "").lower()
        name = (m.get("meeting_name") or "").lower()
        raw = (m.get("raw_text") or "").lower() if include_transcripts else ""
        meeting_date = m.get("meeting_date") or m.get("created_at") or ""
        
        # Date filtering
        if start_date and meeting_date < start_date:
            continue
        if end_date and meeting_date > end_date:
            continue
        
        # Content matching
        if like in notes or like in name or (include_transcripts and like in raw):
            # Determine match source for snippet
            if like in (m.get("synthesized_notes") or "").lower():
                snippet = highlight_match(m.get("synthesized_notes") or "", query)
                match_source = "notes"
            elif include_transcripts and like in (m.get("raw_text") or "").lower():
                snippet = highlight_match(m.get("raw_text") or "", query)
                match_source = "transcript"
            else:
                snippet = (m.get("synthesized_notes") or "")[:300]
                match_source = "title"
            
            results.append({
                "type": "meeting",
                "id": m["id"],
                "title": m.get("meeting_name") or "Untitled Meeting",
                "snippet": snippet,
                "date": meeting_date,
                "match_source": match_source,
            })
            if len(results) >= limit:
                break
    
    return results


@router.get("/search")
def search(
    request: Request,
    q: str | None = Query(default=None),
    source_type: str = Query(default="docs"),  # docs | meetings | both | transcripts
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    include_transcripts: bool = Query(default=False),  # F2: Search raw transcripts
    limit: int = 10,
):
    results = []

    if q and len(q) >= 2:
        # -------- Documents (from Supabase) --------
        if source_type in ("docs", "both"):
            doc_results = _search_documents_supabase(q, start_date, end_date, limit)
            results.extend(doc_results)

        # -------- Meetings (from Supabase) --------
        if source_type in ("meetings", "both", "transcripts"):
            search_transcripts = include_transcripts or source_type == "transcripts"
            meeting_results = _search_meetings_supabase(q, search_transcripts, start_date, end_date, limit)
            results.extend(meeting_results)
        
        # -------- F2: Meeting Documents (linked transcripts/summaries) --------
        if include_transcripts or source_type == "transcripts":
            like = q.lower()
            supabase = get_supabase_client()
            if supabase:
                # Get meeting documents that match the query
                doc_results = supabase.table("meeting_documents")\
                    .select("id, meeting_id, doc_type, source, content, created_at")\
                    .ilike("content", f"%{like}%")\
                    .order("created_at", desc=True)\
                    .limit(limit)\
                    .execute()
                
                for d in (doc_results.data or []):
                    # Get meeting info
                    meeting_result = supabase.table("meetings")\
                        .select("meeting_name, meeting_date")\
                        .eq("id", d["meeting_id"])\
                        .execute()
                    meeting = meeting_result.data[0] if meeting_result.data else {}
                    
                    results.append({
                        "type": "transcript",
                        "id": d["meeting_id"],  # Link to meeting
                        "doc_id": d["id"],  # Document ID
                        "title": f"{meeting.get('meeting_name', 'Meeting')} ({d['source']} {d['doc_type']})",
                        "snippet": highlight_match(d["content"], q),
                        "date": meeting.get("meeting_date") or d["created_at"],
                        "source": d["source"],
                        "doc_type": d["doc_type"],
                    })

    results.sort(key=lambda r: r["date"] or "", reverse=True)

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

