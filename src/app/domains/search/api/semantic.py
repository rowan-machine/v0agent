# src/app/domains/search/api/semantic.py
"""
Semantic Search API Routes

Vector-based search using pgvector embeddings and OpenAI.
Includes hybrid search (keyword + semantic) with RRF ranking.
"""

from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import os
import logging

from ....infrastructure.supabase_client import get_supabase_client
from ....api.models import (
    SemanticSearchRequest,
    SearchResultItem,
    SearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search-semantic"])


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


@router.post("/semantic")
async def semantic_search(request: SemanticSearchRequest) -> SearchResponse:
    """
    Semantic search using vector embeddings.
    
    Uses pgvector for similarity search. If no embedding provided,
    generates one using OpenAI text-embedding-3-small.
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
async def hybrid_search(request: SemanticSearchRequest) -> SearchResponse:
    """
    Hybrid search combining semantic and keyword search.
    
    Uses Reciprocal Rank Fusion (RRF) to combine results from
    pgvector semantic search and PostgreSQL full-text search.
    """
    from .keyword import keyword_search
    
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
    """
    Search mindmap nodes using both hierarchy and synthesis data.
    
    Returns mindmap nodes that match the query, including:
    - Nodes with matching titles or content
    - Nodes related to synthesis results
    - Parent/child relationships for context
    """
    try:
        from src.app.services.mindmap_synthesis import MindmapSynthesizer
        
        query = request.query.lower()
        limit = request.match_count
        results: List[SearchResultItem] = []
        
        all_mindmaps = MindmapSynthesizer.get_all_mindmaps()
        
        matches = []
        for mindmap in all_mindmaps:
            try:
                import json
                mindmap_data = json.loads(mindmap['mindmap_json'])
                hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_data)
                
                for node in mindmap_data.get('nodes', []):
                    node_title = (node.get('title', '') or '').lower()
                    node_content = (node.get('content', '') or '').lower()
                    
                    score = 0
                    if query in node_title:
                        score += 100
                    if query in node_content:
                        score += 50
                    
                    if score > 0:
                        level = node.get('level', 0)
                        parent_id = node.get('parent_id')
                        
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
        
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        for match in matches[:limit]:
            results.append(SearchResultItem(
                id=f"mindmap_node_{match['node_id']}",
                type="mindmap",
                title=match['title'],
                snippet=match['content'],
                score=match['score'] / 100.0,
            ))
        
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
    """
    Hybrid search that includes mindmap data alongside documents and meetings.
    
    Combines keyword + semantic search with mindmap node search
    using Reciprocal Rank Fusion.
    """
    try:
        hybrid_results = await hybrid_search(request)
        mindmap_results = await search_mindmaps(request)
        
        all_results = hybrid_results.results + mindmap_results.results
        combined = []
        
        for i, result in enumerate(hybrid_results.results[:5]):
            result.score = result.score * 0.9
            combined.append(result)
        
        for i, result in enumerate(mindmap_results.results[:5]):
            combined.append(result)
        
        seen = set()
        deduplicated = []
        for result in combined:
            if result.id not in seen:
                seen.add(result.id)
                deduplicated.append(result)
        
        deduplicated.sort(key=lambda x: x.score, reverse=True)
        
        return SearchResponse(
            results=deduplicated[:request.match_count],
            query=request.query,
            total_results=len(deduplicated),
            search_type="hybrid_with_mindmap"
        )
        
    except Exception as e:
        logger.error(f"Hybrid search with mindmap error: {e}")
        return await hybrid_search(request)


__all__ = ["router", "get_embedding"]
