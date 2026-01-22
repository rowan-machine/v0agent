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
    SmartSuggestionsRequest,
    SmartSuggestionItem,
    SmartSuggestionsResponse,
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


# -------------------------
# Smart Suggestions (P5.9)
# -------------------------

def get_source_content(ref_type: str, ref_id, conn) -> Optional[dict]:
    """Fetch the source item content for embedding lookup."""
    try:
        if ref_type == "meeting":
            row = conn.execute(
                """SELECT id, meeting_name as title, synthesized_notes as content, meeting_date as date
                   FROM meeting_summaries WHERE id = ?""",
                (ref_id,)
            ).fetchone()
        elif ref_type == "document":
            row = conn.execute(
                """SELECT id, source as title, content, document_date as date
                   FROM docs WHERE id = ?""",
                (ref_id,)
            ).fetchone()
        elif ref_type == "ticket":
            row = conn.execute(
                """SELECT id, ticket_id as title, description as content, created_at as date
                   FROM tickets WHERE id = ?""",
                (ref_id,)
            ).fetchone()
        elif ref_type == "dikw":
            row = conn.execute(
                """SELECT id, level || ': ' || SUBSTR(content, 1, 50) as title, 
                   content, created_at as date
                   FROM dikw_items WHERE id = ?""",
                (ref_id,)
            ).fetchone()
        elif ref_type == "signal":
            row = conn.execute(
                """SELECT id, signal_type as title, signal_text as content, created_at as date
                   FROM signal_status WHERE id = ?""",
                (ref_id,)
            ).fetchone()
        else:
            return None
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch source content: {e}")
        return None


def get_embedding_for_ref(ref_type: str, ref_uuid: str, sb) -> Optional[List[float]]:
    """Get existing embedding from Supabase for a reference item."""
    try:
        result = sb.table("embeddings").select("embedding").eq(
            "ref_type", ref_type
        ).eq("ref_id", ref_uuid).limit(1).execute()
        
        if result.data and result.data[0].get("embedding"):
            return result.data[0]["embedding"]
        return None
    except Exception as e:
        logger.warning(f"Failed to get embedding for {ref_type}/{ref_uuid}: {e}")
        return None


@router.post("/suggestions")
async def smart_suggestions(
    request: SmartSuggestionsRequest
) -> SmartSuggestionsResponse:
    """
    Get smart content suggestions based on semantic similarity.
    
    P5.9: Uses pgvector embeddings to find related content across
    meetings, documents, tickets, and DIKW items.
    
    Args:
        request: SmartSuggestionsRequest with reference type/id
        
    Returns:
        SmartSuggestionsResponse with categorized suggestions
    """
    sb = get_supabase_client()
    
    with connect() as conn:
        # 1. Fetch the source item content
        source = get_source_content(request.ref_type, request.ref_id, conn)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source item {request.ref_type}/{request.ref_id} not found"
            )
        
        source_item = SmartSuggestionItem(
            id=source.get("id", request.ref_id),
            type=request.ref_type,
            title=source.get("title", "Untitled"),
            snippet=(source.get("content", "") or "")[:300],
            similarity=1.0,
            relationship="source",
            date=source.get("date"),
        )
        
        # 2. Try to find embedding or generate one
        embedding = None
        source_text = source.get("content") or source.get("title") or ""
        
        if sb:
            # Try to get existing embedding from Supabase
            # Note: We need UUID mapping - for now, use text-based similarity
            pass
        
        # Generate embedding from content
        if not embedding and source_text:
            embedding = get_embedding(source_text[:8000])  # Limit to model context
        
        if not embedding:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to generate embedding for source content"
            )
        
        # 3. Search for similar items
        suggestions: List[SmartSuggestionItem] = []
        
        if sb:
            try:
                # Call semantic search RPC
                result = sb.rpc("semantic_search", {
                    "query_embedding": embedding,
                    "match_threshold": request.min_similarity,
                    "match_count": request.max_results * 2,  # Fetch more to filter
                }).execute()
                
                for item in result.data or []:
                    item_type = item.get("ref_type")
                    item_id = item.get("ref_id")
                    similarity = item.get("similarity", 0)
                    
                    # Skip the source item itself
                    if item_type == request.ref_type and str(item_id) == str(request.ref_id):
                        continue
                    
                    # Filter by include_types if specified
                    if request.include_types and item_type not in request.include_types:
                        continue
                    
                    # Fetch content for each result
                    content = get_source_content(item_type, item_id, conn) if item_type else None
                    
                    if content:
                        suggestions.append(SmartSuggestionItem(
                            id=content.get("id", item_id),
                            type=item_type,
                            title=content.get("title", "Untitled"),
                            snippet=(content.get("content", "") or "")[:200],
                            similarity=round(similarity, 3),
                            relationship="semantically_similar" if similarity > 0.85 else "same_topic" if similarity > 0.75 else "related_context",
                            date=content.get("date"),
                        ))
                    
                    if len(suggestions) >= request.max_results:
                        break
                        
            except Exception as e:
                logger.error(f"Supabase semantic search failed: {e}")
                # Fall through to local fallback
        
        # 4. Fallback: Simple keyword matching if no Supabase or no results
        if not suggestions:
            keywords = source_text.lower().split()[:10]  # Top 10 words
            keyword_results = []
            
            # Search meetings
            if not request.include_types or "meeting" in request.include_types:
                for kw in keywords[:5]:
                    if len(kw) < 4:
                        continue
                    like = f"%{kw}%"
                    meetings = conn.execute(
                        """SELECT id, meeting_name as title, synthesized_notes as content, meeting_date as date
                           FROM meeting_summaries
                           WHERE id != ? AND (LOWER(synthesized_notes) LIKE ? OR LOWER(meeting_name) LIKE ?)
                           LIMIT 3""",
                        (request.ref_id if request.ref_type == "meeting" else -1, like, like)
                    ).fetchall()
                    for m in meetings:
                        if m["id"] not in [r["id"] for r in keyword_results if r.get("type") == "meeting"]:
                            keyword_results.append({**dict(m), "type": "meeting"})
            
            # Search documents
            if not request.include_types or "document" in request.include_types:
                for kw in keywords[:5]:
                    if len(kw) < 4:
                        continue
                    like = f"%{kw}%"
                    docs = conn.execute(
                        """SELECT id, source as title, content, document_date as date
                           FROM docs
                           WHERE id != ? AND (LOWER(content) LIKE ? OR LOWER(source) LIKE ?)
                           LIMIT 3""",
                        (request.ref_id if request.ref_type == "document" else -1, like, like)
                    ).fetchall()
                    for d in docs:
                        if d["id"] not in [r["id"] for r in keyword_results if r.get("type") == "document"]:
                            keyword_results.append({**dict(d), "type": "document"})
            
            # Search tickets
            if not request.include_types or "ticket" in request.include_types:
                for kw in keywords[:5]:
                    if len(kw) < 4:
                        continue
                    like = f"%{kw}%"
                    tickets = conn.execute(
                        """SELECT id, ticket_id as title, description as content, created_at as date
                           FROM tickets
                           WHERE id != ? AND (LOWER(description) LIKE ? OR LOWER(title) LIKE ?)
                           LIMIT 3""",
                        (request.ref_id if request.ref_type == "ticket" else -1, like, like)
                    ).fetchall()
                    for t in tickets:
                        if t["id"] not in [r["id"] for r in keyword_results if r.get("type") == "ticket"]:
                            keyword_results.append({**dict(t), "type": "ticket"})
            
            # Convert to suggestions (with estimated similarity based on match count)
            for item in keyword_results[:request.max_results]:
                suggestions.append(SmartSuggestionItem(
                    id=item["id"],
                    type=item["type"],
                    title=item.get("title", "Untitled"),
                    snippet=(item.get("content", "") or "")[:200],
                    similarity=0.6,  # Estimated for keyword match
                    relationship="keyword_match",
                    date=item.get("date"),
                ))
        
        # 5. Sort by similarity and limit
        suggestions.sort(key=lambda s: s.similarity, reverse=True)
        suggestions = suggestions[:request.max_results]
        
        return SmartSuggestionsResponse(
            source=source_item,
            suggestions=suggestions,
            total_found=len(suggestions),
            search_type="semantic" if sb and suggestions else "keyword",
        )


@router.get("/suggestions/{ref_type}/{ref_id}")
async def get_smart_suggestions(
    ref_type: str,
    ref_id: int,
    max_results: int = Query(5, ge=1, le=20),
    min_similarity: float = Query(0.7, ge=0.0, le=1.0),
) -> SmartSuggestionsResponse:
    """
    GET endpoint for smart suggestions (convenience wrapper).
    
    Example:
        GET /api/search/suggestions/meeting/123?max_results=5
        
    Returns semantically similar content across all types.
    """
    request = SmartSuggestionsRequest(
        ref_type=ref_type,
        ref_id=ref_id,
        max_results=max_results,
        min_similarity=min_similarity,
    )
    return await smart_suggestions(request)
