# src/app/domains/search/api/unified.py
"""
Unified Search API Routes

F5: Unified Semantic Search across all entity types.
Includes smart suggestions for semantic similarity recommendations.
"""

from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import os
import logging
import asyncio
import time

from src.app.infrastructure.supabase_client import get_supabase_client
from src.app.api.models import (
    UnifiedSearchRequest,
    UnifiedSearchResultItem,
    UnifiedSearchResponse,
    SmartSuggestionsRequest,
    SmartSuggestionItem,
    SmartSuggestionsResponse,
)
from .semantic import get_embedding

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search-unified"])


# Entity type configuration
ENTITY_CONFIG = {
    "meetings": {
        "icon": "📅",
        "table": "meeting_summaries",
        "table_supabase": "meetings",
        "id_field": "id",
        "title_field": "meeting_name",
        "content_field": "synthesized_notes",
        "date_field": "meeting_date",
        "url_template": "/meetings/{id}",
    },
    "documents": {
        "icon": "📄",
        "table": "docs",
        "table_supabase": "documents",
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
    
    pos = text_lower.find(query_lower)
    
    if pos >= 0:
        start = max(0, pos - 50)
        end = min(len(text), pos + len(query) + 150)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
    else:
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
    """Keyword search for a single entity type."""
    config = ENTITY_CONFIG.get(entity_type)
    if not config:
        return []
    
    results = []
    sb = get_supabase_client()
    
    if sb:
        try:
            table_name = config.get("table_supabase", config["table"])
            title_field = config["title_field"]
            content_field = config["content_field"]
            date_field = config["date_field"]
            
            select_cols = [config["id_field"], title_field, content_field, date_field]
            if "extra_fields" in config:
                select_cols.extend(config["extra_fields"])
            
            query_builder = sb.table(table_name).select(",".join(select_cols))
            title_results = query_builder.ilike(title_field, f"%{query}%").order(date_field, desc=True).limit(limit).execute()
            
            query_builder2 = sb.table(table_name).select(",".join(select_cols))
            content_results = query_builder2.ilike(content_field, f"%{query}%").order(date_field, desc=True).limit(limit).execute()
            
            seen_ids = set()
            all_rows = []
            for row in (title_results.data or []) + (content_results.data or []):
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    all_rows.append(row)
            
            if my_mentions_only:
                all_rows = [r for r in all_rows if "@rowan" in (r.get(content_field) or "").lower()]
            
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
                    id=str(row["id"]),
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
            logger.warning(f"Supabase keyword search failed for {entity_type}: {e}")
    
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
        ref_type_map = {
            "meetings": "meeting",
            "documents": "document",
            "tickets": "ticket",
            "dikw": "dikw",
            "signals": "signal",
        }
        ref_type = ref_type_map.get(entity_type, entity_type)
        
        response = sb.rpc("semantic_search", {
            "query_embedding": embedding,
            "match_threshold": min_score,
            "match_count": limit,
        }).execute()
        
        for item in response.data or []:
            if item.get("ref_type") != ref_type:
                continue
            
            ref_id = item.get("ref_id")
            similarity = item.get("similarity", 0)
            
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
    """
    start_time = time.time()
    
    types_list = [t.strip() for t in entity_types.split(",") if t.strip()]
    valid_types = [t for t in types_list if t in ENTITY_CONFIG]
    
    if not valid_types:
        valid_types = ["meetings", "documents", "tickets", "dikw"]
    
    all_results: List[UnifiedSearchResultItem] = []
    entity_counts: Dict[str, int] = {}
    
    if use_keyword:
        keyword_tasks = [
            search_entity_keyword(et, q, limit, my_mentions)
            for et in valid_types
        ]
        keyword_results = await asyncio.gather(*keyword_tasks)
        
        for et, results in zip(valid_types, keyword_results):
            entity_counts[et] = entity_counts.get(et, 0) + len(results)
            all_results.extend(results)
    
    if use_semantic:
        embedding = get_embedding(q)
        if embedding:
            semantic_tasks = [
                search_entity_semantic(et, embedding, limit, min_score)
                for et in valid_types
            ]
            semantic_results = await asyncio.gather(*semantic_tasks)
            
            for et, results in zip(valid_types, semantic_results):
                existing_ids = {(r.entity_type, r.id) for r in all_results}
                for r in results:
                    if (r.entity_type, r.id) not in existing_ids:
                        entity_counts[et] = entity_counts.get(et, 0) + 1
                        all_results.append(r)
                    else:
                        for existing in all_results:
                            if existing.entity_type == r.entity_type and existing.id == r.id:
                                existing.score = min(1.0, existing.score + 0.2)
                                existing.match_type = "hybrid"
                                break
    
    all_results.sort(key=lambda r: (r.score, r.date or ""), reverse=True)
    all_results = all_results[:limit]
    
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
    """F5: POST endpoint for unified search (allows complex requests)."""
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


@router.post("/suggestions")
async def smart_suggestions(request: SmartSuggestionsRequest) -> SmartSuggestionsResponse:
    """
    Get smart content suggestions based on semantic similarity.
    
    P5.9: Uses pgvector embeddings to find related content across
    meetings, documents, tickets, and DIKW items.
    """
    sb = get_supabase_client()
    
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
    
    embedding = None
    source_text = source.get("content") or source.get("title") or ""
    
    if source_text:
        embedding = get_embedding(source_text[:8000])
    
    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to generate embedding for source content"
        )
    
    suggestions: List[SmartSuggestionItem] = []
    
    if sb:
        try:
            result = sb.rpc("semantic_search", {
                "query_embedding": embedding,
                "match_threshold": request.min_similarity,
                "match_count": request.max_results * 2,
            }).execute()
            
            for item in result.data or []:
                item_type = item.get("ref_type")
                item_id = item.get("ref_id")
                similarity = item.get("similarity", 0)
                
                if item_type == request.ref_type and str(item_id) == str(request.ref_id):
                    continue
                
                if request.include_types and item_type not in request.include_types:
                    continue
                
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
    """GET endpoint for smart suggestions (convenience wrapper)."""
    request = SmartSuggestionsRequest(
        ref_type=ref_type,
        ref_id=ref_id,
        max_results=max_results,
        min_similarity=min_similarity,
    )
    return await smart_suggestions(request)


__all__ = ["router", "ENTITY_CONFIG", "highlight_snippet"]
