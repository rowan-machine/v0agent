# src/app/domains/search/services/text_search.py
"""
Text Search Service

Provides text-based search functionality for documents and meetings.
Includes snippet extraction and query highlighting.
"""

import re
import logging
from typing import Optional, List, Dict, Any

from ....infrastructure.supabase_client import get_supabase_client
from ....services import document_service, meeting_service

logger = logging.getLogger(__name__)


def highlight_match(text: str, query: str, context_chars: int = 100) -> str:
    """
    Extract snippet with query highlighted and surrounding context.
    
    Returns text with the match and context, with <mark> tags around matches.
    
    Args:
        text: The text to search within
        query: The search query to highlight
        context_chars: Number of characters to include on each side of match
        
    Returns:
        Snippet with <mark> tags around matched text
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


def search_documents(
    query: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search documents using Supabase.
    
    Args:
        query: Search query string
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        limit: Maximum number of results
        
    Returns:
        List of search result dictionaries
    """
    all_docs = document_service.get_all_documents()
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


def search_meetings(
    query: str,
    include_transcripts: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search meetings using Supabase.
    
    Args:
        query: Search query string
        include_transcripts: Whether to search raw transcript text
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        limit: Maximum number of results
        
    Returns:
        List of search result dictionaries with match_source indicator
    """
    all_meetings = meeting_service.get_all_meetings()
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


def search_meeting_documents(
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search meeting documents (Teams/Pocket transcripts) using Supabase.
    
    Args:
        query: Search query string
        limit: Maximum number of results
        
    Returns:
        List of transcript search result dictionaries
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.warning("Supabase not configured for meeting document search")
        return []
    
    results = []
    like = query.lower()
    
    try:
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
                "snippet": highlight_match(d["content"], query),
                "date": meeting.get("meeting_date") or d["created_at"],
                "source": d["source"],
                "doc_type": d["doc_type"],
            })
    except Exception as e:
        logger.error(f"Error searching meeting documents: {e}")
    
    return results
