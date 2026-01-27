# src/app/memory/semantic.py
import os
import logging
from .embed import embed_text, EMBED_MODEL
from .vector_store import fetch_all_embeddings, cosine
from ..infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

USE_EMBEDDINGS = os.getenv("USE_EMBEDDINGS", "1") == "1"


def _fetch_from_supabase(ref_type: str, ids: list) -> list:
    """Fetch documents/meetings from Supabase by IDs."""
    supabase = get_supabase_client()
    if not supabase or not ids:
        return []
    
    try:
        if ref_type == "doc":
            result = supabase.table("documents").select("id, source, content, document_date, created_at").in_("id", ids).execute()
        else:
            result = supabase.table("meetings").select("id, meeting_name, synthesized_notes, meeting_date, created_at").in_("id", ids).execute()
        
        if result.data:
            return result.data
    except Exception as e:
        logger.warning(f"Supabase fetch failed for {ref_type}: {e}")
    
    return []


def _supabase_semantic_search(question: str, ref_type: str, k: int = 8) -> list:
    """
    Semantic search using Supabase pgvector.
    Returns list of matching documents/meetings.
    """
    supabase = get_supabase_client()
    if not supabase:
        return []
    
    # Get query embedding
    qvec = embed_text(question)
    if not qvec:
        return []
    
    try:
        # Use Supabase's match_embeddings RPC function if available
        result = supabase.rpc(
            "match_embeddings",
            {
                "query_embedding": qvec,
                "match_threshold": 0.7,
                "match_count": k,
                "filter_ref_type": ref_type
            }
        ).execute()
        
        if result.data:
            ref_ids = [r["ref_id"] for r in result.data]
            return _fetch_from_supabase(ref_type, ref_ids)
    except Exception as e:
        logger.warning(f"Supabase vector search failed: {e}")
        # Fall back to fetching all and computing locally
        pass
    
    # Fallback: fetch recent items if vector search isn't set up
    try:
        if ref_type == "doc":
            result = supabase.table("documents").select("id, source, content, document_date, created_at").order("created_at", desc=True).limit(k * 2).execute()
        else:
            result = supabase.table("meetings").select("id, meeting_name, synthesized_notes, meeting_date, created_at").order("created_at", desc=True).limit(k * 2).execute()
        
        if result.data:
            logger.info(f"Supabase fallback: got {len(result.data)} {ref_type} items")
            return result.data[:k]
    except Exception as e:
        logger.warning(f"Supabase fallback fetch failed: {e}")
    
    return []


def semantic_search(question: str, ref_type: str, k: int = 8):
    """
    Semantic search across documents or meetings.
    
    Tries Supabase first (for production/Railway), falls back to SQLite.
    """
    if not USE_EMBEDDINGS:
        return []
    
    # Try Supabase first
    results = _supabase_semantic_search(question, ref_type, k)
    if results:
        logger.info(f"Semantic search via Supabase: {len(results)} {ref_type} results")
        return results
    
    # Local embedding fallback (still uses Supabase for data)
    qvec = embed_text(question)
    if not qvec:
        return []

    candidates = fetch_all_embeddings(ref_type, EMBED_MODEL)
    if not candidates:
        # No embeddings found, try direct fetch from Supabase
        logger.warning(f"No embeddings found for {ref_type}, trying direct fetch")
        supabase = get_supabase_client()
        if not supabase:
            return []
        
        try:
            if ref_type == "doc":
                result = supabase.table("documents").select("id, source, content, document_date, created_at").order("created_at", desc=True).limit(k).execute()
            else:
                result = supabase.table("meetings").select("id, meeting_name, synthesized_notes, meeting_date, created_at").order("created_at", desc=True).limit(k).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to fetch from Supabase: {e}")
            return []
    
    scored = [(ref_id, cosine(qvec, vec)) for ref_id, vec in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [ref_id for ref_id, score in scored[:k] if score > 0]

    if not top:
        return []

    supabase = get_supabase_client()
    if not supabase:
        return []
    
    try:
        if ref_type == "doc":
            result = supabase.table("documents").select("id, source, content, document_date, created_at").in_("id", top).execute()
        else:
            result = supabase.table("meetings").select("id, meeting_name, synthesized_notes, meeting_date, created_at").in_("id", top).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to fetch by IDs from Supabase: {e}")
        return []
