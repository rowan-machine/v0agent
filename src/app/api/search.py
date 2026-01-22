# src/app/api/search.py
"""
Search API Routes - Keyword, Semantic, and Hybrid Search

P5.2: Implements hybrid search combining pgvector semantic search
with PostgreSQL full-text search using Reciprocal Rank Fusion (RRF).
"""

from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, List
import os
import logging

from .models import (
    SearchRequest,
    SemanticSearchRequest,
    SearchResultItem,
    SearchResponse,
    APIResponse,
    ErrorResponse,
)
from ..db import connect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


def get_supabase_client():
    """Get Supabase client for semantic search."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for search query using OpenAI."""
    try:
        import openai
        client = openai.OpenAI()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"Failed to generate embedding: {e}")
        return None


@router.get("")
async def keyword_search(
    q: str = Query(None, min_length=2, max_length=1000, description="Search query"),
    source_type: str = Query("both", pattern="^(docs|meetings|both)$"),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(10, ge=1, le=100),
) -> SearchResponse:
    """
    Keyword-based search across documents and meetings.
    
    Returns:
        SearchResponse with matching results
    """
    if not q:
        return SearchResponse(
            results=[],
            query="",
            total_results=0,
            search_type="keyword"
        )
    
    results: List[SearchResultItem] = []
    like = f"%{q.lower()}%"
    
    with connect() as conn:
        # Search documents
        if source_type in ("docs", "both"):
            date_clauses = []
            params = [like, like]
            
            if start_date:
                date_clauses.append("document_date >= ?")
                params.append(start_date)
            if end_date:
                date_clauses.append("document_date <= ?")
                params.append(end_date)
            
            where = "(LOWER(content) LIKE ? OR LOWER(source) LIKE ?)"
            if date_clauses:
                where += " AND " + " AND ".join(date_clauses)
            
            docs = conn.execute(f"""
                SELECT id, source AS title, content, document_date, created_at
                FROM docs
                WHERE {where}
                ORDER BY document_date DESC
                LIMIT ?
            """, (*params, limit)).fetchall()
            
            for d in docs:
                results.append(SearchResultItem(
                    id=d["id"],
                    type="document",
                    title=d["title"] or "Untitled",
                    snippet=(d["content"] or "")[:300],
                    date=d["document_date"] or d["created_at"],
                ))
        
        # Search meetings
        if source_type in ("meetings", "both"):
            date_clauses = []
            params = [like, like]
            
            if start_date:
                date_clauses.append("meeting_date >= ?")
                params.append(start_date)
            if end_date:
                date_clauses.append("meeting_date <= ?")
                params.append(end_date)
            
            where = "(LOWER(synthesized_notes) LIKE ? OR LOWER(meeting_name) LIKE ?)"
            if date_clauses:
                where += " AND " + " AND ".join(date_clauses)
            
            meetings = conn.execute(f"""
                SELECT id, meeting_name AS title, synthesized_notes, meeting_date, created_at
                FROM meeting_summaries
                WHERE {where}
                ORDER BY meeting_date DESC
                LIMIT ?
            """, (*params, limit)).fetchall()
            
            for m in meetings:
                results.append(SearchResultItem(
                    id=m["id"],
                    type="meeting",
                    title=m["title"] or "Untitled Meeting",
                    snippet=(m["synthesized_notes"] or "")[:300],
                    date=m["meeting_date"] or m["created_at"],
                ))
    
    # Sort by date
    results.sort(key=lambda r: r.date or "", reverse=True)
    
    return SearchResponse(
        results=results[:limit],
        query=q,
        total_results=len(results),
        search_type="keyword"
    )


@router.post("/semantic")
async def semantic_search(
    request: SemanticSearchRequest
) -> SearchResponse:
    """
    Semantic search using vector embeddings.
    
    Uses pgvector for similarity search. If no embedding provided,
    generates one using OpenAI text-embedding-3-small.
    
    Returns:
        SearchResponse with semantically similar results
    """
    sb = get_supabase_client()
    if not sb:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase not configured for semantic search"
        )
    
    # Get or generate embedding
    embedding = request.embedding
    if not embedding:
        embedding = get_embedding(request.query)
        if not embedding:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to generate embedding for query"
            )
    
    try:
        # Call Supabase semantic_search function
        response = sb.rpc("semantic_search", {
            "query_embedding": embedding,
            "match_threshold": request.match_threshold,
            "match_count": request.match_count,
        }).execute()
        
        results: List[SearchResultItem] = []
        
        for item in response.data:
            # Fetch the actual content
            ref_type = item.get("ref_type")
            ref_id = item.get("ref_id")
            similarity = item.get("similarity", 0)
            
            if ref_type == "document":
                doc = sb.table("documents").select("id, source, content").eq("id", ref_id).single().execute()
                if doc.data:
                    results.append(SearchResultItem(
                        id=doc.data["id"],
                        type="document",
                        title=doc.data.get("source", "Untitled"),
                        snippet=(doc.data.get("content", ""))[:300],
                        score=similarity,
                    ))
            elif ref_type == "meeting":
                meeting = sb.table("meetings").select("id, meeting_name, synthesized_notes").eq("id", ref_id).single().execute()
                if meeting.data:
                    results.append(SearchResultItem(
                        id=meeting.data["id"],
                        type="meeting",
                        title=meeting.data.get("meeting_name", "Untitled"),
                        snippet=(meeting.data.get("synthesized_notes", ""))[:300],
                        score=similarity,
                    ))
        
        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results),
            search_type="semantic"
        )
        
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/hybrid")
async def hybrid_search(
    request: SemanticSearchRequest
) -> SearchResponse:
    """
    Hybrid search combining semantic and keyword search.
    
    Uses Reciprocal Rank Fusion (RRF) to combine results from
    pgvector semantic search and PostgreSQL full-text search.
    
    Returns:
        SearchResponse with combined results ranked by RRF score
    """
    sb = get_supabase_client()
    if not sb:
        # Fall back to keyword search if Supabase not available
        return await keyword_search(
            q=request.query,
            source_type="both",
            limit=request.match_count
        )
    
    # Get or generate embedding
    embedding = request.embedding
    if not embedding:
        embedding = get_embedding(request.query)
        if not embedding:
            # Fall back to keyword search if embedding fails
            logger.warning("Embedding generation failed, falling back to keyword search")
            return await keyword_search(
                q=request.query,
                source_type="both",
                limit=request.match_count
            )
    
    try:
        # Call Supabase hybrid_search function
        response = sb.rpc("hybrid_search", {
            "query_text": request.query,
            "query_embedding": embedding,
            "match_count": request.match_count,
            "full_text_weight": request.full_text_weight,
            "semantic_weight": request.semantic_weight,
        }).execute()
        
        results: List[SearchResultItem] = []
        
        for item in response.data:
            results.append(SearchResultItem(
                id=item.get("id"),
                type=item.get("ref_type", "unknown"),
                title=item.get("source_name", "Untitled"),
                snippet=(item.get("content", ""))[:300],
                score=item.get("rrf_score"),
            ))
        
        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results),
            search_type="hybrid"
        )
        
    except Exception as e:
        logger.error(f"Hybrid search error: {e}")
        # Fall back to keyword search on error
        return await keyword_search(
            q=request.query,
            source_type="both",
            limit=request.match_count
        )


@router.get("/health")
async def search_health():
    """Check search service health."""
    status_info = {
        "keyword_search": True,  # Always available
        "semantic_search": False,
        "hybrid_search": False,
    }
    
    # Check Supabase connection
    try:
        sb = get_supabase_client()
        if sb:
            # Quick test query
            sb.table("embeddings").select("id").limit(1).execute()
            status_info["semantic_search"] = True
            status_info["hybrid_search"] = True
    except Exception as e:
        logger.warning(f"Supabase health check failed: {e}")
    
    # Check embedding service
    try:
        import openai
        status_info["embedding_service"] = bool(os.getenv("OPENAI_API_KEY"))
    except:
        status_info["embedding_service"] = False
    
    return JSONResponse(
        content={
            "status": "ok" if any(status_info.values()) else "degraded",
            "services": status_info,
        },
        status_code=status.HTTP_200_OK
    )
