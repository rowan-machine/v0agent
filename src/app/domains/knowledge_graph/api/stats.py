# src/app/domains/knowledge_graph/api/stats.py
"""
Knowledge Graph Statistics API

Endpoints for getting graph statistics.
"""

import logging
from fastapi import APIRouter

from .models import GraphStatsResponse
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def graph_stats() -> GraphStatsResponse:
    """Get statistics about the knowledge graph."""
    supabase = get_supabase_client()
    
    # Total links - use count option
    total_result = supabase.table("entity_links").select("id", count="exact").execute()
    total = total_result.count or 0
    
    # Links by type - we need to aggregate manually since Supabase doesn't have GROUP BY in client
    # Fetch all link types and count them
    all_links = supabase.table("entity_links").select("link_type, source_type, source_id, target_type, target_id").execute()
    
    links_by_type = {}
    source_entities = {}  # {type: set of ids}
    target_entities = {}  # {type: set of ids}
    
    for row in all_links.data or []:
        # Count by link type
        lt = row.get("link_type")
        if lt:
            links_by_type[lt] = links_by_type.get(lt, 0) + 1
        
        # Track unique source entities
        st = row.get("source_type")
        sid = row.get("source_id")
        if st and sid:
            if st not in source_entities:
                source_entities[st] = set()
            source_entities[st].add(sid)
        
        # Track unique target entities
        tt = row.get("target_type")
        tid = row.get("target_id")
        if tt and tid:
            if tt not in target_entities:
                target_entities[tt] = set()
            target_entities[tt].add(tid)
    
    # Combine source and target counts
    entities_with_links = {}
    for etype, ids in source_entities.items():
        entities_with_links[etype] = len(ids)
    for etype, ids in target_entities.items():
        existing = entities_with_links.get(etype, 0)
        entities_with_links[etype] = max(existing, len(ids))
    
    # Average links per entity
    total_entities = sum(entities_with_links.values()) or 1
    avg_links = total / total_entities if total_entities > 0 else 0
    
    return GraphStatsResponse(
        total_links=total,
        links_by_type=links_by_type,
        entities_with_links=entities_with_links,
        avg_links_per_entity=round(avg_links, 2),
    )
