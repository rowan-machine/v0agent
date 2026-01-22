from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from .db import connect
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
        like = f"%{q.lower()}%"

        with connect() as conn:

            # -------- Documents --------
            if source_type in ("docs", "both"):
                date_clauses, date_params = date_clause(start_date, end_date, "document_date")
                where = ["(LOWER(content) LIKE ? OR LOWER(source) LIKE ?)"] + date_clauses

                docs = conn.execute(
                    f"""
                    SELECT id, source AS title, content, document_date, created_at
                    FROM docs
                    WHERE {' AND '.join(where)}
                    ORDER BY document_date DESC
                    LIMIT ?
                    """,
                    (like, like, *date_params, limit),
                ).fetchall()

                for d in docs:
                    results.append({
                        "type": "document",
                        "id": d["id"],
                        "title": d["title"],
                        "snippet": highlight_match(d["content"], q),
                        "date": d["document_date"] or d["created_at"],
                    })

            # -------- Meetings (notes + optional raw_text) --------
            if source_type in ("meetings", "both", "transcripts"):
                date_clauses, date_params = date_clause(start_date, end_date, "meeting_date")
                
                # F2: Include raw_text in search when include_transcripts is True
                if include_transcripts or source_type == "transcripts":
                    where_clause = "(LOWER(synthesized_notes) LIKE ? OR LOWER(meeting_name) LIKE ? OR LOWER(raw_text) LIKE ?)"
                    search_params = (like, like, like, *date_params, limit)
                else:
                    where_clause = "(LOWER(synthesized_notes) LIKE ? OR LOWER(meeting_name) LIKE ?)"
                    search_params = (like, like, *date_params, limit)
                
                where = [where_clause] + date_clauses

                meetings = conn.execute(
                    f"""
                    SELECT id, meeting_name AS title, synthesized_notes, raw_text, meeting_date, created_at
                    FROM meeting_summaries
                    WHERE {' AND '.join(where)}
                    ORDER BY meeting_date DESC
                    LIMIT ?
                    """,
                    search_params,
                ).fetchall()

                for m in meetings:
                    # Check where the match was found for better snippet
                    notes = m["synthesized_notes"] or ""
                    raw = m["raw_text"] or ""
                    
                    if q.lower() in notes.lower():
                        snippet = highlight_match(notes, q)
                        match_source = "notes"
                    elif q.lower() in raw.lower():
                        snippet = highlight_match(raw, q)
                        match_source = "transcript"
                    else:
                        snippet = notes[:300]
                        match_source = "title"
                    
                    results.append({
                        "type": "meeting",
                        "id": m["id"],
                        "title": m["title"],
                        "snippet": snippet,
                        "date": m["meeting_date"] or m["created_at"],
                        "match_source": match_source,
                    })
            
            # -------- F2: Meeting Documents (linked transcripts/summaries) --------
            if include_transcripts or source_type == "transcripts":
                # Search in meeting_documents table (Teams/Pocket transcripts)
                doc_results = conn.execute(
                    """
                    SELECT md.id, md.meeting_id, md.doc_type, md.source, md.content,
                           md.created_at, ms.meeting_name, ms.meeting_date
                    FROM meeting_documents md
                    JOIN meeting_summaries ms ON md.meeting_id = ms.id
                    WHERE LOWER(md.content) LIKE ?
                    ORDER BY md.created_at DESC
                    LIMIT ?
                    """,
                    (like, limit),
                ).fetchall()
                
                for d in doc_results:
                    results.append({
                        "type": "transcript",
                        "id": d["meeting_id"],  # Link to meeting
                        "doc_id": d["id"],  # Document ID
                        "title": f"{d['meeting_name']} ({d['source']} {d['doc_type']})",
                        "snippet": highlight_match(d["content"], q),
                        "date": d["meeting_date"] or d["created_at"],
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

