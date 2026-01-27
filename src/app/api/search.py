# src/app/api/search.py
"""
Search API Routes - Keyword, Semantic, Hybrid, and Unified Search

P5.2: Implements hybrid search combining pgvector semantic search
with PostgreSQL full-text search using Reciprocal Rank Fusion (RRF).

F5: Unified Semantic Search across all entity types.
"""

from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import os
import logging
import asyncio
import time

from .models import (
    SearchRequest,
    SemanticSearchRequest,
    SearchResultItem,
    SearchResponse,
    SmartSuggestionsRequest,
    SmartSuggestionItem,
    SmartSuggestionsResponse,
    UnifiedSearchRequest,
    UnifiedSearchResultItem,
    UnifiedSearchResponse,
    APIResponse,
    ErrorResponse,
)
from ..infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


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
    supabase = get_supabase_client()
    
    if not supabase:
        logger.warning("Supabase not configured for keyword search")
        return SearchResponse(
            results=[],
            query=q,
            total_results=0,
            search_type="keyword"
        )
    
    # Search documents
    if source_type in ("docs", "both"):
        query = supabase.table("documents").select("id, source, content, document_date, created_at")
        query = query.or_(f"content.ilike.%{q}%,source.ilike.%{q}%")
        
        if start_date:
            query = query.gte("document_date", start_date)
        if end_date:
            query = query.lte("document_date", end_date)
        
        query = query.order("document_date", desc=True).limit(limit)
        result = query.execute()
        docs = result.data or []
        
        for d in docs:
            results.append(SearchResultItem(
                id=d["id"],
                type="document",
                title=d.get("source") or "Untitled",
                snippet=(d.get("content") or "")[:300],
                date=d.get("document_date") or d.get("created_at"),
            ))
    
    # Search meetings
    if source_type in ("meetings", "both"):
        query = supabase.table("meetings").select("id, meeting_name, synthesized_notes, meeting_date, created_at")
        query = query.or_(f"synthesized_notes.ilike.%{q}%,meeting_name.ilike.%{q}%")
        
        if start_date:
            query = query.gte("meeting_date", start_date)
        if end_date:
            query = query.lte("meeting_date", end_date)
        
        query = query.order("meeting_date", desc=True).limit(limit)
        result = query.execute()
        meetings = result.data or []
        
        for m in meetings:
            results.append(SearchResultItem(
                id=m["id"],
                type="meeting",
                title=m.get("meeting_name") or "Untitled Meeting",
                snippet=(m.get("synthesized_notes") or "")[:300],
                date=m.get("meeting_date") or m.get("created_at"),
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


@router.post("/mindmap")
async def search_mindmaps(request: SemanticSearchRequest):
    """Search mindmap nodes using both hierarchy and synthesis data.
    
    Returns mindmap nodes that match the query, including:
    - Nodes with matching titles or content
    - Nodes related to synthesis results
    - Parent/child relationships for context
    
    Returns:
        SearchResponse with mindmap node results
    """
    try:
        from ..services.mindmap_synthesis import MindmapSynthesizer
        
        query = request.query.lower()
        limit = request.match_count
        results: List[SearchResultItem] = []
        
        # Search all mindmaps for nodes matching the query
        all_mindmaps = MindmapSynthesizer.get_all_mindmaps()
        
        matches = []
        for mindmap in all_mindmaps:
            try:
                import json
                mindmap_data = json.loads(mindmap['mindmap_json'])
                hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_data)
                
                # Search nodes by title and content
                for node in mindmap_data.get('nodes', []):
                    node_title = (node.get('title', '') or '').lower()
                    node_content = (node.get('content', '') or '').lower()
                    
                    # Calculate match score
                    score = 0
                    if query in node_title:
                        score += 100  # Title match is highest priority
                    if query in node_content:
                        score += 50   # Content match is secondary
                    
                    if score > 0:
                        level = node.get('level', 0)
                        parent_id = node.get('parent_id')
                        
                        # Find parent and children
                        parent_title = None
                        children = []
                        
                        for other_node in mindmap_data.get('nodes', []):
                            if other_node.get('id') == parent_id:
                                parent_title = other_node.get('title')
                            if other_node.get('parent_id') == node.get('id'):
                                children.append({
                                    'id': other_node.get('id'),
                                    'title': other_node.get('title')
                                })
                        
                        matches.append({
                            'score': score,
                            'node_id': node.get('id'),
                            'title': node.get('title', 'Untitled'),
                            'content': node_content[:200],
                            'level': level,
                            'parent_id': parent_id,
                            'parent_title': parent_title,
                            'children': children,
                            'conversation_id': mindmap['conversation_id'],
                            'mindmap_id': mindmap['id']
                        })
            except Exception as e:
                logger.warning(f"Error searching mindmap {mindmap['id']}: {e}")
        
        # Sort by score (highest first) and limit results
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        for match in matches[:limit]:
            results.append(SearchResultItem(
                id=f"mindmap_node_{match['node_id']}",
                type="mindmap",
                title=match['title'],
                snippet=match['content'],
                score=match['score'] / 100.0,  # Normalize to 0-1
            ))
        
        # Also search synthesis for high-level topics
        synthesis = MindmapSynthesizer.get_current_synthesis()
        if synthesis:
            synthesis_text = (synthesis.get('synthesis_text', '') or '').lower()
            if query in synthesis_text:
                results.append(SearchResultItem(
                    id="mindmap_synthesis",
                    type="mindmap_synthesis",
                    title="Knowledge Synthesis",
                    snippet=synthesis_text[:300],
                    score=0.8,
                ))
        
        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results),
            search_type="mindmap"
        )
        
    except Exception as e:
        logger.error(f"Mindmap search error: {e}")
        return SearchResponse(
            results=[],
            query=request.query,
            total_results=0,
            search_type="mindmap"
        )


@router.post("/hybrid-with-mindmap")
async def hybrid_search_with_mindmap(request: SemanticSearchRequest):
    """Hybrid search that includes mindmap data alongside documents and meetings.
    
    Combines keyword + semantic search with mindmap node search
    using Reciprocal Rank Fusion.
    
    Returns:
        SearchResponse with mixed results (documents, meetings, mindmap nodes)
    """
    try:
        # Get results from both searches
        hybrid_results = await hybrid_search(request)
        mindmap_results = await search_mindmaps(request)
        
        # Combine and re-rank using RRF
        all_results = hybrid_results.results + mindmap_results.results
        
        # Simple re-ranking: take top results from each type
        combined = []
        
        # Add hybrid results (weighted)
        for i, result in enumerate(hybrid_results.results[:5]):
            result.score = result.score * 0.9  # Slight boost for traditional search
            combined.append(result)
        
        # Add mindmap results (interleaved)
        for i, result in enumerate(mindmap_results.results[:5]):
            combined.append(result)
        
        # Remove duplicates (keeping highest score)
        seen = set()
        deduplicated = []
        for result in combined:
            if result.id not in seen:
                seen.add(result.id)
                deduplicated.append(result)
        
        # Re-sort by score
        deduplicated.sort(key=lambda x: x.score, reverse=True)
        
        return SearchResponse(
            results=deduplicated[:request.match_count],
            query=request.query,
            total_results=len(deduplicated),
            search_type="hybrid_with_mindmap"
        )
        
    except Exception as e:
        logger.error(f"Hybrid search with mindmap error: {e}")
        # Fall back to regular hybrid search
        return await hybrid_search(request)


@router.get("/health")
async def search_health():
    """Check search service health."""
    status_info = {
        "keyword_search": True,  # Always available
        "semantic_search": False,
        "hybrid_search": False,
        "unified_search": True,  # F5: Always available (falls back to keyword)
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
# F5: Unified Semantic Search
# -------------------------

# Entity type configuration
# Note: table names differ between SQLite and Supabase
# - SQLite: meeting_summaries, docs
# - Supabase: meetings, documents
ENTITY_CONFIG = {
    "meetings": {
        "icon": "📅",
        "table": "meeting_summaries",  # SQLite name
        "table_supabase": "meetings",  # Supabase name
        "id_field": "id",
        "title_field": "meeting_name",
        "content_field": "synthesized_notes",
        "date_field": "meeting_date",
        "url_template": "/meetings/{id}",
    },
    "documents": {
        "icon": "📄",
        "table": "docs",  # SQLite name
        "table_supabase": "documents",  # Supabase name
        "id_field": "id",
        "title_field": "source",
        "content_field": "content",
        "date_field": "document_date",
        "url_template": "/documents/{id}",
    },
    "tickets": {
        "icon": "🎫",
        "table": "tickets",
        "table_supabase": "tickets",
        "id_field": "id",
        "title_field": "title",
        "content_field": "description",
        "date_field": "created_at",
        "url_template": "/tickets/{id}",
        "extra_fields": ["ticket_id", "status"],
    },
    "dikw": {
        "icon": "💡",
        "table": "dikw_items",
        "table_supabase": "dikw_items",
        "id_field": "id",
        "title_field": "level",
        "content_field": "content",
        "date_field": "created_at",
        "url_template": "/dikw/{id}",
        "extra_fields": ["level", "summary"],
    },
    "signals": {
        "icon": "📡",
        "table": "signal_status",
        "table_supabase": "signal_status",
        "id_field": "id",
        "title_field": "signal_type",
        "content_field": "signal_text",
        "date_field": "created_at",
        "url_template": "/signals/{id}",
        "extra_fields": ["status", "meeting_id"],
    },
}


def highlight_snippet(text: str, query: str, max_length: int = 200) -> str:
    """Extract relevant snippet with search term highlighted."""
    if not text:
        return ""
    
    text = text.strip()
    query_lower = query.lower()
    text_lower = text.lower()
    
    # Find query position
    pos = text_lower.find(query_lower)
    
    if pos >= 0:
        # Extract window around match
        start = max(0, pos - 50)
        end = min(len(text), pos + len(query) + 150)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
    else:
        # No match, take beginning
        snippet = text[:max_length]
        if len(text) > max_length:
            snippet += "..."
    
    return snippet


async def search_entity_keyword(
    entity_type: str,
    query: str,
    limit: int,
    my_mentions_only: bool = False,
) -> List[UnifiedSearchResultItem]:
    """Keyword search for a single entity type.
    
    Uses Supabase if available, falls back to SQLite.
    """
    config = ENTITY_CONFIG.get(entity_type)
    if not config:
        return []
    
    results = []
    
    # Try Supabase first (where the data lives)
    sb = get_supabase_client()
    if sb:
        try:
            table_name = config.get("table_supabase", config["table"])
            title_field = config["title_field"]
            content_field = config["content_field"]
            date_field = config["date_field"]
            
            # Build select columns
            select_cols = [config["id_field"], title_field, content_field, date_field]
            if "extra_fields" in config:
                select_cols.extend(config["extra_fields"])
            
            # Execute Supabase query with ilike filter (case-insensitive)
            # Note: Supabase PostgREST uses ilike for case-insensitive search
            query_builder = sb.table(table_name).select(",".join(select_cols))
            
            # Apply search filter (title OR content contains query)
            # PostgREST doesn't support OR easily, so we search both and dedupe
            title_results = query_builder.ilike(title_field, f"%{query}%").order(date_field, desc=True).limit(limit).execute()
            
            query_builder2 = sb.table(table_name).select(",".join(select_cols))
            content_results = query_builder2.ilike(content_field, f"%{query}%").order(date_field, desc=True).limit(limit).execute()
            
            # Combine and dedupe
            seen_ids = set()
            all_rows = []
            for row in (title_results.data or []) + (content_results.data or []):
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    all_rows.append(row)
            
            # Apply my_mentions filter if needed
            if my_mentions_only:
                all_rows = [r for r in all_rows if "@rowan" in (r.get(content_field) or "").lower()]
            
            # Process results
            for row in all_rows[:limit]:
                title = row.get(title_field) or "Untitled"
                if entity_type == "dikw":
                    level = row.get("level", "")
                    title = f"{level}: {title[:50]}" if level else title[:50]
                elif entity_type == "tickets" and row.get("ticket_id"):
                    title = f"{row['ticket_id']}: {title}"
                
                content = row.get(content_field) or ""
                score = 0.5
                query_lower = query.lower()
                
                if query_lower in title.lower():
                    score += 0.3
                
                match_count = content.lower().count(query_lower)
                if match_count > 1:
                    score += min(0.2, match_count * 0.05)
                
                results.append(UnifiedSearchResultItem(
                    id=str(row["id"]),  # Supabase uses UUIDs
                    entity_type=entity_type,
                    title=title,
                    snippet=highlight_snippet(content, query),
                    date=str(row.get(date_field) or ""),
                    score=round(score, 3),
                    match_type="keyword",
                    icon=config["icon"],
                    url=config["url_template"].format(id=row["id"]),
                    metadata={k: row.get(k) for k in config.get("extra_fields", []) if row.get(k)},
                ))
            
            logger.debug(f"Supabase keyword search for {entity_type}: found {len(results)} results")
            return results
            
        except Exception as e:
            logger.warning(f"Supabase keyword search failed for {entity_type}, falling back to SQLite: {e}")
    
    # Fallback to Supabase query
    search_term = query.lower()
    
    try:
        supabase = get_supabase_client()
        # Build query
        title_field = config["title_field"]
        content_field = config["content_field"]
        date_field = config["date_field"]
        
        # Build select fields
        select_fields = f"{config['id_field']}, {title_field}, {content_field}, {date_field}"
        if "extra_fields" in config:
            select_fields += ", " + ", ".join(config["extra_fields"])
        
        # Execute Supabase query with text search
        query_builder = supabase.table(config['table']).select(select_fields)
        
        # Apply text search filter (using ilike for case-insensitive search)
        query_builder = query_builder.or_(f"{content_field}.ilike.%{search_term}%,{title_field}.ilike.%{search_term}%")
        
        # My mentions filter
        if my_mentions_only and content_field:
            query_builder = query_builder.ilike(content_field, "%@rowan%")
        
        # Order and limit
        query_builder = query_builder.order(date_field, desc=True, nullsfirst=False).limit(limit)
        
        result = query_builder.execute()
        rows = result.data or []
        
        for row in rows:
            row_dict = dict(row) if not isinstance(row, dict) else row
            
            # Build title - map from Supabase field names
            title = row_dict.get(title_field) or row_dict.get("title") or "Untitled"
            if entity_type == "dikw":
                level = row_dict.get("level", "")
                title = f"{level}: {title[:50]}" if level else title[:50]
            elif entity_type == "tickets" and row_dict.get("ticket_id"):
                title = f"{row_dict['ticket_id']}: {title}"
            
            # Calculate score (keyword matches get base score)
            content = row_dict.get(content_field) or row_dict.get("content") or ""
            score = 0.5  # Base score for keyword match
            query_lower = query.lower()
            content_lower = content.lower()
            title_lower = title.lower()
            
            # Boost for title match
            if query_lower in title_lower:
                score += 0.3
            
            # Boost for multiple content matches
            match_count = content_lower.count(query_lower)
            if match_count > 1:
                score += min(0.2, match_count * 0.05)
            
            # Get the ID field value
            item_id = row_dict.get(config['id_field']) or row_dict.get("id")
            
            results.append(UnifiedSearchResultItem(
                id=item_id,
                entity_type=entity_type,
                title=title,
                snippet=highlight_snippet(content, query),
                date=str(row_dict.get(date_field) or row_dict.get("date") or ""),
                score=round(score, 3),
                match_type="keyword",
                icon=config["icon"],
                url=config["url_template"].format(id=item_id),
                metadata={k: row_dict.get(k) for k in config.get("extra_fields", []) if row_dict.get(k)},
            ))
    
    except Exception as e:
        logger.error(f"Keyword search failed for {entity_type}: {e}")
    
    return results


async def search_entity_semantic(
    entity_type: str,
    embedding: List[float],
    limit: int,
    min_score: float,
) -> List[UnifiedSearchResultItem]:
    """Semantic search for a single entity type using embeddings."""
    config = ENTITY_CONFIG.get(entity_type)
    if not config:
        return []
    
    results = []
    sb = get_supabase_client()
    
    if not sb:
        return results
    
    try:
        # Map entity_type to ref_type used in embeddings table
        ref_type_map = {
            "meetings": "meeting",
            "documents": "document",
            "tickets": "ticket",
            "dikw": "dikw",
            "signals": "signal",
        }
        ref_type = ref_type_map.get(entity_type, entity_type)
        
        # Call semantic_search RPC filtered by type
        response = sb.rpc("semantic_search", {
            "query_embedding": embedding,
            "match_threshold": min_score,
            "match_count": limit,
        }).execute()
        
        # Fetch actual content from Supabase for each result
        for item in response.data or []:
            if item.get("ref_type") != ref_type:
                continue
            
            ref_id = item.get("ref_id")
            similarity = item.get("similarity", 0)
            
            # Fetch actual content from Supabase
            title_field = config["title_field"]
            content_field = config["content_field"]
            date_field = config["date_field"]
            
            select_fields = f"{config['id_field']}, {title_field}, {content_field}, {date_field}"
            if "extra_fields" in config:
                select_fields += ", " + ", ".join(config["extra_fields"])
            
            row_result = sb.table(config['table']).select(select_fields).eq(config['id_field'], ref_id).execute()
            if not row_result.data:
                continue
            
            row_dict = row_result.data[0]
            
            # Build title
            title = row_dict.get(title_field) or "Untitled"
            if entity_type == "dikw":
                level = row_dict.get("level", "")
                title = f"{level}: {title[:50]}" if level else title[:50]
            elif entity_type == "tickets" and row_dict.get("ticket_id"):
                title = f"{row_dict['ticket_id']}: {title}"
            
            item_id = row_dict.get(config['id_field'])
            
            results.append(UnifiedSearchResultItem(
                id=item_id,
                entity_type=entity_type,
                title=title,
                snippet=highlight_snippet(row_dict.get(content_field, ""), ""),
                date=str(row_dict.get(date_field) or ""),
                score=round(similarity, 3),
                match_type="semantic",
                icon=config["icon"],
                url=config["url_template"].format(id=item_id),
                metadata={k: row_dict.get(k) for k in config.get("extra_fields", []) if row_dict.get(k)},
            ))
    
    except Exception as e:
        logger.error(f"Semantic search failed for {entity_type}: {e}")
    
    return results


@router.get("/unified")
async def unified_search(
    q: str = Query(..., min_length=1, max_length=1000, description="Search query"),
    entity_types: str = Query("meetings,documents,tickets,dikw", description="Comma-separated entity types"),
    limit: int = Query(20, ge=1, le=100),
    use_semantic: bool = Query(True, description="Use semantic similarity"),
    use_keyword: bool = Query(True, description="Use keyword matching"),
    min_score: float = Query(0.3, ge=0.0, le=1.0),
    my_mentions: bool = Query(False, description="Filter to @Rowan mentions"),
) -> UnifiedSearchResponse:
    """
    F5: Unified search across all entity types.
    
    Combines semantic (embedding-based) and keyword search with
    intelligent ranking and deduplication.
    
    Args:
        q: Search query
        entity_types: Comma-separated list of types to search
        limit: Max results per entity type
        use_semantic: Enable semantic similarity search
        use_keyword: Enable keyword matching
        min_score: Minimum relevance score (0.0-1.0)
        my_mentions: Only show items mentioning @Rowan
    
    Returns:
        UnifiedSearchResponse with ranked, merged results
    """
    start_time = time.time()
    
    # Parse entity types
    types_list = [t.strip() for t in entity_types.split(",") if t.strip()]
    valid_types = [t for t in types_list if t in ENTITY_CONFIG]
    
    if not valid_types:
        valid_types = ["meetings", "documents", "tickets", "dikw"]
    
    all_results: List[UnifiedSearchResultItem] = []
    entity_counts: Dict[str, int] = {}
    
    # Run keyword search if enabled
    if use_keyword:
        keyword_tasks = [
            search_entity_keyword(et, q, limit, my_mentions)
            for et in valid_types
        ]
        keyword_results = await asyncio.gather(*keyword_tasks)
        
        for et, results in zip(valid_types, keyword_results):
            entity_counts[et] = entity_counts.get(et, 0) + len(results)
            all_results.extend(results)
    
    # Run semantic search if enabled
    if use_semantic:
        embedding = get_embedding(q)
        if embedding:
            semantic_tasks = [
                search_entity_semantic(et, embedding, limit, min_score)
                for et in valid_types
            ]
            semantic_results = await asyncio.gather(*semantic_tasks)
            
            for et, results in zip(valid_types, semantic_results):
                # Avoid duplicates - only add if not already from keyword
                existing_ids = {(r.entity_type, r.id) for r in all_results}
                for r in results:
                    if (r.entity_type, r.id) not in existing_ids:
                        entity_counts[et] = entity_counts.get(et, 0) + 1
                        all_results.append(r)
                    else:
                        # Boost score for items found in both keyword and semantic
                        for existing in all_results:
                            if existing.entity_type == r.entity_type and existing.id == r.id:
                                existing.score = min(1.0, existing.score + 0.2)
                                existing.match_type = "hybrid"
                                break
    
    # Sort by score (descending) then date
    all_results.sort(key=lambda r: (r.score, r.date or ""), reverse=True)
    
    # Limit total results
    all_results = all_results[:limit]
    
    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)
    
    return UnifiedSearchResponse(
        query=q,
        results=all_results,
        total_results=len(all_results),
        entity_counts=entity_counts,
        search_duration_ms=duration_ms,
        search_type="unified",
    )


@router.post("/unified")
async def unified_search_post(request: UnifiedSearchRequest) -> UnifiedSearchResponse:
    """
    F5: POST endpoint for unified search (allows complex requests).
    """
    entity_types_str = ",".join(request.entity_types)
    return await unified_search(
        q=request.query,
        entity_types=entity_types_str,
        limit=request.limit,
        use_semantic=request.use_semantic,
        use_keyword=request.use_keyword,
        min_score=request.min_score,
        my_mentions=request.my_mentions_only,
    )


# -------------------------
# Smart Suggestions (P5.9)
# -------------------------

def get_source_content(ref_type: str, ref_id, supabase) -> Optional[dict]:
    """Fetch the source item content for embedding lookup."""
    try:
        if ref_type == "meeting":
            result = supabase.table("meetings").select(
                "id, meeting_name, synthesized_notes, meeting_date"
            ).eq("id", ref_id).execute()
            if result.data:
                row = result.data[0]
                return {
                    "id": row["id"],
                    "title": row.get("meeting_name"),
                    "content": row.get("synthesized_notes"),
                    "date": row.get("meeting_date")
                }
        elif ref_type == "document":
            result = supabase.table("documents").select(
                "id, source, content, document_date"
            ).eq("id", ref_id).execute()
            if result.data:
                row = result.data[0]
                return {
                    "id": row["id"],
                    "title": row.get("source"),
                    "content": row.get("content"),
                    "date": row.get("document_date")
                }
        elif ref_type == "ticket":
            result = supabase.table("tickets").select(
                "id, ticket_id, description, created_at"
            ).eq("id", ref_id).execute()
            if result.data:
                row = result.data[0]
                return {
                    "id": row["id"],
                    "title": row.get("ticket_id"),
                    "content": row.get("description"),
                    "date": row.get("created_at")
                }
        elif ref_type == "dikw":
            result = supabase.table("dikw_items").select(
                "id, level, content, created_at"
            ).eq("id", ref_id).execute()
            if result.data:
                row = result.data[0]
                level = row.get("level", "")
                content = row.get("content", "")
                return {
                    "id": row["id"],
                    "title": f"{level}: {content[:50]}" if level else content[:50],
                    "content": content,
                    "date": row.get("created_at")
                }
        elif ref_type == "signal":
            result = supabase.table("signal_status").select(
                "id, signal_type, signal_text, created_at"
            ).eq("id", ref_id).execute()
            if result.data:
                row = result.data[0]
                return {
                    "id": row["id"],
                    "title": row.get("signal_type"),
                    "content": row.get("signal_text"),
                    "date": row.get("created_at")
                }
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
    
    # 1. Fetch the source item content
    source = get_source_content(request.ref_type, request.ref_id, sb)
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
                content = get_source_content(item_type, item_id, sb) if item_type else None
                
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
    
    # 4. Fallback: Simple keyword matching if no results
    if not suggestions and sb:
        keywords = source_text.lower().split()[:10]  # Top 10 words
        keyword_results = []
        
        # Search meetings
        if not request.include_types or "meeting" in request.include_types:
            for kw in keywords[:5]:
                if len(kw) < 4:
                    continue
                try:
                    meetings_result = sb.table("meetings").select(
                        "id, meeting_name, synthesized_notes, meeting_date"
                    ).neq("id", request.ref_id if request.ref_type == "meeting" else -1).or_(
                        f"synthesized_notes.ilike.%{kw}%,meeting_name.ilike.%{kw}%"
                    ).limit(3).execute()
                    for m in meetings_result.data or []:
                        if m["id"] not in [r["id"] for r in keyword_results if r.get("type") == "meeting"]:
                            keyword_results.append({
                                "id": m["id"],
                                "title": m.get("meeting_name"),
                                "content": m.get("synthesized_notes"),
                                "date": m.get("meeting_date"),
                                "type": "meeting"
                            })
                except Exception as e:
                    logger.warning(f"Meeting keyword search failed: {e}")
        
        # Search documents
        if not request.include_types or "document" in request.include_types:
            for kw in keywords[:5]:
                if len(kw) < 4:
                    continue
                try:
                    docs_result = sb.table("docs").select(
                        "id, source, content, document_date"
                    ).neq("id", request.ref_id if request.ref_type == "document" else -1).or_(
                        f"content.ilike.%{kw}%,source.ilike.%{kw}%"
                    ).limit(3).execute()
                    for d in docs_result.data or []:
                        if d["id"] not in [r["id"] for r in keyword_results if r.get("type") == "document"]:
                            keyword_results.append({
                                "id": d["id"],
                                "title": d.get("source"),
                                "content": d.get("content"),
                                "date": d.get("document_date"),
                                "type": "document"
                            })
                except Exception as e:
                    logger.warning(f"Document keyword search failed: {e}")
        
        # Search tickets
        if not request.include_types or "ticket" in request.include_types:
            for kw in keywords[:5]:
                if len(kw) < 4:
                    continue
                try:
                    tickets_result = sb.table("tickets").select(
                        "id, ticket_id, description, created_at"
                    ).neq("id", request.ref_id if request.ref_type == "ticket" else -1).or_(
                        f"description.ilike.%{kw}%,title.ilike.%{kw}%"
                    ).limit(3).execute()
                    for t in tickets_result.data or []:
                        if t["id"] not in [r["id"] for r in keyword_results if r.get("type") == "ticket"]:
                            keyword_results.append({
                                "id": t["id"],
                                "title": t.get("ticket_id"),
                                "content": t.get("description"),
                                "date": t.get("created_at"),
                                "type": "ticket"
                            })
                except Exception as e:
                    logger.warning(f"Ticket keyword search failed: {e}")
        
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
