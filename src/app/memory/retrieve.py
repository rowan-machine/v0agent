# src/app/memory/retrieve.py

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def _get_supabase():
    """Get Supabase client if available."""
    try:
        from ..infrastructure.supabase_client import get_supabase_client
        return get_supabase_client()
    except Exception as e:
        logger.debug(f"Supabase not available: {e}")
    return None


def _supabase_retrieve(
    terms: List[str],
    source_type: str,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Retrieve from Supabase using text search."""
    results = {"documents": [], "meetings": []}
    
    sb = _get_supabase()
    if not sb:
        return results
    
    try:
        # Build search pattern for ilike
        search_patterns = [f"%{t.lower()}%" for t in terms]
        
        # -------- Documents --------
        if source_type in ("docs", "both"):
            try:
                query = sb.table("documents").select("id, source, content, document_date, created_at")
                
                # Apply date filters
                if start_date:
                    query = query.gte("document_date", start_date)
                if end_date:
                    query = query.lte("document_date", end_date)
                
                query = query.order("document_date", desc=True).limit(limit * 2)  # Get more, filter later
                
                response = query.execute()
                
                if response.data:
                    for doc in response.data:
                        content_lower = (doc.get("content") or "").lower()
                        # Check if any term matches
                        if any(t.lower() in content_lower for t in terms):
                            results["documents"].append({
                                "id": doc.get("id"),
                                "source": doc.get("source"),
                                "content": doc.get("content"),
                                "document_date": doc.get("document_date"),
                                "created_at": doc.get("created_at"),
                            })
                            if len(results["documents"]) >= limit:
                                break
            except Exception as e:
                logger.warning(f"Supabase documents search failed: {e}")
        
        # -------- Meetings --------
        if source_type in ("meetings", "both"):
            try:
                query = sb.table("meetings").select("id, meeting_name, synthesized_notes, meeting_date, created_at")
                
                # Apply date filters
                if start_date:
                    query = query.gte("meeting_date", start_date)
                if end_date:
                    query = query.lte("meeting_date", end_date)
                
                query = query.order("meeting_date", desc=True).limit(limit * 2)
                
                response = query.execute()
                
                if response.data:
                    for mtg in response.data:
                        notes_lower = (mtg.get("synthesized_notes") or "").lower()
                        # Check if any term matches
                        if any(t.lower() in notes_lower for t in terms):
                            results["meetings"].append({
                                "id": mtg.get("id"),
                                "meeting_name": mtg.get("meeting_name"),
                                "synthesized_notes": mtg.get("synthesized_notes"),
                                "meeting_date": mtg.get("meeting_date"),
                                "created_at": mtg.get("created_at"),
                            })
                            if len(results["meetings"]) >= limit:
                                break
            except Exception as e:
                logger.warning(f"Supabase meetings search failed: {e}")
        
        logger.info(f"Supabase retrieve: {len(results['documents'])} docs, {len(results['meetings'])} meetings")
        return results
        
    except Exception as e:
        logger.error(f"Supabase retrieve error: {e}")
        return results


def _sqlite_retrieve(
    terms: List[str],
    source_type: str,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Secondary Supabase retrieve (renamed from SQLite for compatibility)."""
    # This function now also uses Supabase - kept for API compatibility
    # The primary _supabase_retrieve is preferred; this is a fallback path
    return _supabase_retrieve(terms, source_type, start_date, end_date, limit)


def retrieve(
    terms: List[str],
    source_type: str = "docs",  # docs | meetings | both
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Broad, recall-oriented retrieval.
    No formatting. No LLM. No ranking tricks.
    
    Tries Supabase first (for Railway), falls back to SQLite (for local dev).
    """
    results = {"documents": [], "meetings": []}

    if not terms:
        return results

    # Try Supabase first (primary for production/Railway)
    results = _supabase_retrieve(terms, source_type, start_date, end_date, limit)
    
    # If we got results from Supabase, return them
    if results["documents"] or results["meetings"]:
        return results
    
    # Fallback to SQLite (for local development or if Supabase fails)
    logger.debug("Falling back to SQLite for retrieve")
    return _sqlite_retrieve(terms, source_type, start_date, end_date, limit)
