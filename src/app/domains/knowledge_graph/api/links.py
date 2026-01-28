# src/app/domains/knowledge_graph/api/links.py
"""
Knowledge Graph Link Management API

Endpoints for creating, querying, and deleting entity links.
"""

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, status

from .models import (
    LinkCreate, LinkResponse, LinkedEntity, GraphQueryResponse, EntityRef
)
from .helpers import get_entity_title, get_entity_snippet
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/links")
async def create_link(link: LinkCreate) -> LinkResponse:
    """
    Create a link between two entities.
    
    Link types:
    - semantic_similar: Content is semantically similar
    - related: General relationship
    - derived_from: Target was created from source
    - referenced: Target references source
    - same_topic: Both discuss same topic
    - blocks: Source blocks target
    - depends_on: Source depends on target
    """
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not configured"
        )
    
    # Verify both entities exist
    source_title = get_entity_title(link.source_type, link.source_id, supabase)
    target_title = get_entity_title(link.target_type, link.target_id, supabase)
    
    if source_title.startswith("Unknown") or target_title.startswith("Unknown"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both entities not found"
        )
    
    # Insert the link
    try:
        metadata_json = json.dumps(link.metadata) if link.metadata else None
        
        result = supabase.table("entity_links").insert({
            "source_type": link.source_type,
            "source_id": link.source_id,
            "target_type": link.target_type,
            "target_id": link.target_id,
            "link_type": link.link_type,
            "similarity_score": link.similarity_score,
            "confidence": link.confidence,
            "is_bidirectional": link.is_bidirectional,
            "metadata": metadata_json,
            "created_by": link.created_by
        }).execute()
        
        created = result.data[0] if result.data else {}
        
        return LinkResponse(
            id=created.get("id"),
            source_type=link.source_type,
            source_id=link.source_id,
            target_type=link.target_type,
            target_id=link.target_id,
            link_type=link.link_type,
            similarity_score=link.similarity_score,
            confidence=link.confidence,
            is_bidirectional=link.is_bidirectional,
            metadata=link.metadata,
            created_by=link.created_by,
            created_at=created.get("created_at", ""),
        )
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Link already exists between these entities"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link: {str(e)}"
        )


@router.get("/links/{entity_type}/{entity_id}")
async def get_entity_links(
    entity_type: str,
    entity_id: int,
    link_type: Optional[str] = Query(None),
    direction: str = Query("both", pattern="^(outgoing|incoming|both)$"),
    include_types: Optional[str] = Query(None, description="Comma-separated entity types to include"),
    limit: int = Query(20, ge=1, le=100),
) -> GraphQueryResponse:
    """
    Get all links for an entity.
    
    Args:
        entity_type: Type of the entity
        entity_id: ID of the entity
        link_type: Filter by link type
        direction: Filter by link direction
        include_types: Comma-separated entity types to include
        limit: Maximum number of results
    """
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not configured"
        )
    
    # Verify entity exists
    entity_title = get_entity_title(entity_type, entity_id, supabase)
    if entity_title.startswith("Unknown"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_type}/{entity_id} not found"
        )
    
    # Get outgoing links (where entity is source)
    outgoing = []
    if direction in ("outgoing", "both"):
        query = supabase.table("entity_links").select("*").eq("source_type", entity_type).eq("source_id", entity_id)
        if link_type:
            query = query.eq("link_type", link_type)
        result = query.limit(limit).execute()
        outgoing = result.data or []
    
    # Get incoming links (where entity is target)
    incoming = []
    if direction in ("incoming", "both"):
        query = supabase.table("entity_links").select("*").eq("target_type", entity_type).eq("target_id", entity_id)
        if link_type:
            query = query.eq("link_type", link_type)
        result = query.limit(limit).execute()
        incoming = result.data or []
    
    # Filter by allowed types
    allowed_types = None
    if include_types:
        allowed_types = set(include_types.split(","))
    
    # Build linked entities list
    links: List[LinkedEntity] = []
    seen = set()  # Track (type, id) to avoid duplicates
    
    for row in outgoing:
        target_type = row.get("target_type")
        target_id = row.get("target_id")
        key = (target_type, target_id)
        
        if key in seen:
            continue
        if allowed_types and target_type not in allowed_types:
            continue
        
        seen.add(key)
        links.append(LinkedEntity(
            entity_type=target_type,
            entity_id=target_id,
            title=get_entity_title(target_type, target_id, supabase),
            snippet=get_entity_snippet(target_type, target_id, supabase),
            link_type=row.get("link_type", "related"),
            link_direction="outgoing",
            similarity_score=row.get("similarity_score"),
            confidence=row.get("confidence", 0.5),
        ))
    
    for row in incoming:
        source_type = row.get("source_type")
        source_id = row.get("source_id")
        key = (source_type, source_id)
        
        if key in seen:
            # Update direction to "both" if we've seen this as outgoing
            for link in links:
                if link.entity_type == source_type and link.entity_id == source_id:
                    link.link_direction = "both"
            continue
        if allowed_types and source_type not in allowed_types:
            continue
        
        seen.add(key)
        links.append(LinkedEntity(
            entity_type=source_type,
            entity_id=source_id,
            title=get_entity_title(source_type, source_id, supabase),
            snippet=get_entity_snippet(source_type, source_id, supabase),
            link_type=row.get("link_type", "related"),
            link_direction="incoming",
            similarity_score=row.get("similarity_score"),
            confidence=row.get("confidence", 0.5),
        ))
    
    # Sort by confidence
    links.sort(key=lambda x: x.confidence, reverse=True)
    
    return GraphQueryResponse(
        entity=EntityRef(entity_type=entity_type, entity_id=entity_id),
        entity_title=entity_title,
        links=links[:limit],
        total_links=len(links),
    )


@router.delete("/links/{link_id}")
async def delete_link(link_id: int) -> dict:
    """Delete a link by ID."""
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not configured"
        )
    
    result = supabase.table("entity_links").delete().eq("id", link_id).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    return {"deleted": True, "id": link_id}
