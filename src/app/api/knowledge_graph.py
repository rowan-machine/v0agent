# src/app/api/knowledge_graph.py
"""
Knowledge Graph API - P5.10

⚠️  DEPRECATED: This file is being replaced by the domain-driven structure.
    New implementation: src/app/domains/knowledge_graph/api/
    New routes available at: /api/domains/graph/*
    
    This file will be removed in a future release.
    Please migrate to the new domain-based routes.

Manages entity links between meetings, documents, tickets, DIKW items, and signals.
Uses SQLite/Supabase for storage instead of requiring Neo4j.

Graph Features:
- Link any two entities with typed relationships
- Query related entities for a given item
- Auto-suggest links based on semantic similarity
- Track link provenance (system/user/ai created)
"""
import warnings
warnings.warn(
    "api/knowledge_graph.py is deprecated. Use domains/knowledge_graph/api instead. "
    "Routes available at /api/domains/graph/*",
    DeprecationWarning,
    stacklevel=2
)

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..infrastructure.supabase_client import get_supabase_client
from .search import get_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["knowledge_graph"])


# -------------------------
# Models
# -------------------------

class EntityRef(BaseModel):
    """Reference to an entity in the knowledge graph."""
    entity_type: str = Field(..., pattern="^(meeting|document|ticket|dikw|signal)$")
    entity_id: int


class LinkCreate(BaseModel):
    """Request to create a link between two entities."""
    source_type: str = Field(..., pattern="^(meeting|document|ticket|dikw|signal)$")
    source_id: int
    target_type: str = Field(..., pattern="^(meeting|document|ticket|dikw|signal)$")
    target_id: int
    link_type: str = Field(
        "related",
        pattern="^(semantic_similar|related|derived_from|referenced|same_topic|blocks|depends_on)$"
    )
    similarity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    is_bidirectional: bool = True
    metadata: Optional[dict] = None
    created_by: str = Field("user", pattern="^(system|user|ai)$")


class LinkResponse(BaseModel):
    """Response for a single link."""
    id: int
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    link_type: str
    similarity_score: Optional[float] = None
    confidence: float
    is_bidirectional: bool
    metadata: Optional[dict] = None
    created_by: str
    created_at: str


class LinkedEntity(BaseModel):
    """An entity linked to the query entity."""
    entity_type: str
    entity_id: int
    title: str
    snippet: str
    link_type: str
    link_direction: str  # "outgoing" | "incoming" | "both"
    similarity_score: Optional[float] = None
    confidence: float


class GraphQueryResponse(BaseModel):
    """Response for graph queries."""
    entity: EntityRef
    entity_title: str
    links: List[LinkedEntity]
    total_links: int


class GraphStatsResponse(BaseModel):
    """Graph statistics response."""
    total_links: int
    links_by_type: dict
    entities_with_links: dict
    avg_links_per_entity: float


# -------------------------
# Helper Functions
# -------------------------

def get_entity_title(entity_type: str, entity_id: int, supabase) -> str:
    """Get the title/name of an entity."""
    try:
        if entity_type == "meeting":
            result = supabase.table("meetings").select("meeting_name").eq("id", entity_id).execute()
            rows = result.data or []
            return rows[0]["meeting_name"] if rows else "Unknown Meeting"
        elif entity_type == "document":
            result = supabase.table("documents").select("source").eq("id", entity_id).execute()
            rows = result.data or []
            return rows[0]["source"] if rows else "Unknown Document"
        elif entity_type == "ticket":
            result = supabase.table("tickets").select("ticket_id, title").eq("id", entity_id).execute()
            rows = result.data or []
            return f"{rows[0]['ticket_id']}: {rows[0]['title']}" if rows else "Unknown Ticket"
        elif entity_type == "dikw":
            result = supabase.table("dikw_items").select("level, content").eq("id", entity_id).execute()
            rows = result.data or []
            if rows:
                return f"[{rows[0]['level'].upper()}] {rows[0]['content'][:50]}..."
            return "Unknown DIKW Item"
        elif entity_type == "signal":
            result = supabase.table("signal_status").select("signal_type, signal_text").eq("id", entity_id).execute()
            rows = result.data or []
            if rows:
                return f"[{rows[0]['signal_type']}] {rows[0]['signal_text'][:50]}..."
            return "Unknown Signal"
        return "Unknown"
    except Exception as e:
        logger.warning(f"Failed to get entity title: {e}")
        return "Unknown"


def get_entity_snippet(entity_type: str, entity_id: int, supabase) -> str:
    """Get a snippet of the entity content."""
    try:
        content = ""
        if entity_type == "meeting":
            result = supabase.table("meetings").select("synthesized_notes").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["synthesized_notes"] if rows else ""
        elif entity_type == "document":
            result = supabase.table("documents").select("content").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["content"] if rows else ""
        elif entity_type == "ticket":
            result = supabase.table("tickets").select("description").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["description"] if rows else ""
        elif entity_type == "dikw":
            result = supabase.table("dikw_items").select("content").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["content"] if rows else ""
        elif entity_type == "signal":
            result = supabase.table("signal_status").select("signal_text").eq("id", entity_id).execute()
            rows = result.data or []
            content = rows[0]["signal_text"] if rows else ""
        
        return (content or "")[:200]
    except Exception:
        return ""


# -------------------------
# API Endpoints
# -------------------------

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
        entity_type: Type of the entity (meeting, document, ticket, dikw, signal)
        entity_id: ID of the entity
        link_type: Filter by link type (optional)
        direction: Link direction (outgoing, incoming, both)
        include_types: Filter linked entities by type (comma-separated)
        limit: Maximum number of links to return
    """
    supabase = get_supabase_client()
    entity_title = get_entity_title(entity_type, entity_id, supabase)
    
    if entity_title.startswith("Unknown"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_type}/{entity_id} not found"
        )
    
    links: List[LinkedEntity] = []
    include_type_list = include_types.split(",") if include_types else None
    
    # Get outgoing links (entity is source)
    if direction in ("outgoing", "both"):
        query_builder = supabase.table("entity_links").select(
            "id, target_type, target_id, link_type, similarity_score, confidence, is_bidirectional"
        ).eq("source_type", entity_type).eq("source_id", entity_id)
        
        if link_type:
            query_builder = query_builder.eq("link_type", link_type)
        
        if include_type_list:
            query_builder = query_builder.in_("target_type", include_type_list)
        
        query_builder = query_builder.order("similarity_score", desc=True, nullsfirst=False).order("confidence", desc=True).limit(limit)
        
        result = query_builder.execute()
        rows = result.data or []
        
        for row in rows:
            links.append(LinkedEntity(
                entity_type=row["target_type"],
                entity_id=row["target_id"],
                title=get_entity_title(row["target_type"], row["target_id"], supabase),
                snippet=get_entity_snippet(row["target_type"], row["target_id"], supabase),
                link_type=row["link_type"],
                link_direction="both" if row["is_bidirectional"] else "outgoing",
                similarity_score=row["similarity_score"],
                confidence=row["confidence"],
            ))
    
    # Get incoming links (entity is target)
    if direction in ("incoming", "both"):
        query_builder = supabase.table("entity_links").select(
            "id, source_type, source_id, link_type, similarity_score, confidence, is_bidirectional"
        ).eq("target_type", entity_type).eq("target_id", entity_id)
        
        if link_type:
            query_builder = query_builder.eq("link_type", link_type)
        
        if include_type_list:
            query_builder = query_builder.in_("source_type", include_type_list)
        
        query_builder = query_builder.order("similarity_score", desc=True, nullsfirst=False).order("confidence", desc=True).limit(limit)
        
        result = query_builder.execute()
        rows = result.data or []
        
        for row in rows:
            # Avoid duplicates for bidirectional links already captured
            existing = next(
                (link for link in links 
                 if link.entity_type == row["source_type"] and link.entity_id == row["source_id"]),
                None
            )
            if existing:
                existing.link_direction = "both"
            else:
                links.append(LinkedEntity(
                    entity_type=row["source_type"],
                    entity_id=row["source_id"],
                    title=get_entity_title(row["source_type"], row["source_id"], supabase),
                    snippet=get_entity_snippet(row["source_type"], row["source_id"], supabase),
                    link_type=row["link_type"],
                    link_direction="both" if row["is_bidirectional"] else "incoming",
                    similarity_score=row["similarity_score"],
                    confidence=row["confidence"],
                ))
    
    # Sort by similarity/confidence
    links.sort(key=lambda item: (item.similarity_score or 0, item.confidence), reverse=True)
    
    return GraphQueryResponse(
        entity=EntityRef(entity_type=entity_type, entity_id=entity_id),
        entity_title=entity_title,
        links=links[:limit],
        total_links=len(links),
    )


@router.delete("/links/{link_id}")
async def delete_link(link_id: int):
    """Delete a link by ID."""
    supabase = get_supabase_client()
    
    # First check if the link exists
    check_result = supabase.table("entity_links").select("id").eq("id", link_id).execute()
    if not check_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link {link_id} not found"
        )
    
    # Delete the link
    supabase.table("entity_links").delete().eq("id", link_id).execute()
    
    return JSONResponse({"status": "ok", "deleted_id": link_id})


@router.post("/links/auto-suggest/{entity_type}/{entity_id}")
async def auto_suggest_links(
    entity_type: str,
    entity_id: int,
    min_similarity: float = Query(0.75, ge=0.5, le=1.0),
    max_suggestions: int = Query(5, ge=1, le=20),
    create_links: bool = Query(False, description="Actually create the suggested links"),
) -> dict:
    """
    Auto-suggest links based on semantic similarity.
    
    Uses embeddings to find related content and optionally creates the links.
    """
    sb = get_supabase_client()
    
    # Get entity content for embedding
    content = None
    if entity_type == "meeting":
        result = sb.table("meeting_summaries").select("synthesized_notes").eq("id", entity_id).execute()
        if result.data:
            content = result.data[0].get("synthesized_notes")
    elif entity_type == "document":
        result = sb.table("docs").select("content").eq("id", entity_id).execute()
        if result.data:
            content = result.data[0].get("content")
    elif entity_type == "ticket":
        result = sb.table("tickets").select("description").eq("id", entity_id).execute()
        if result.data:
            content = result.data[0].get("description")
    elif entity_type == "dikw":
        result = sb.table("dikw_items").select("content").eq("id", entity_id).execute()
        if result.data:
            content = result.data[0].get("content")
    elif entity_type == "signal":
        result = sb.table("signal_status").select("signal_text").eq("id", entity_id).execute()
        if result.data:
            content = result.data[0].get("signal_text")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity type: {entity_type}"
        )
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_type}/{entity_id} not found or has no content"
        )
    
    # Generate embedding
    embedding = get_embedding(content[:8000])
    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to generate embedding"
        )
    
    suggestions = []
    
    # Use Supabase semantic search
    if sb:
        try:
            result = sb.rpc("semantic_search", {
                "query_embedding": embedding,
                "match_threshold": min_similarity,
                "match_count": max_suggestions * 2,  # Fetch extra to filter
            }).execute()
            
            for item in result.data or []:
                item_type = item.get("ref_type")
                item_id = item.get("ref_id")
                similarity = item.get("similarity", 0)
                
                # Skip self
                if item_type == entity_type and str(item_id) == str(entity_id):
                    continue
                
                # Check if link already exists
                existing_check = sb.table("entity_links").select("id").or_(
                    f"and(source_type.eq.{entity_type},source_id.eq.{entity_id},target_type.eq.{item_type},target_id.eq.{item_id})," +
                    f"and(source_type.eq.{item_type},source_id.eq.{item_id},target_type.eq.{entity_type},target_id.eq.{entity_id})"
                ).execute()
                
                if existing_check.data:
                    continue
                
                suggestions.append({
                    "target_type": item_type,
                    "target_id": item_id,
                    "target_title": get_entity_title(item_type, item_id, sb),
                    "similarity_score": round(similarity, 3),
                    "suggested_link_type": "semantic_similar" if similarity > 0.85 else "same_topic",
                })
                
                if len(suggestions) >= max_suggestions:
                    break
                    
        except Exception as e:
            logger.error(f"Semantic search for auto-suggest failed: {e}")
    
    # Create links if requested
    created_links = []
    if create_links and suggestions:
        for sug in suggestions:
            try:
                sb.table("entity_links").insert({
                    "source_type": entity_type,
                    "source_id": entity_id,
                    "target_type": sug["target_type"],
                    "target_id": sug["target_id"],
                    "link_type": sug["suggested_link_type"],
                    "similarity_score": sug["similarity_score"],
                    "confidence": 0.8,
                    "is_bidirectional": True,
                    "created_by": "ai"
                }).execute()
                created_links.append({
                    "target_type": sug["target_type"],
                    "target_id": sug["target_id"],
                })
            except Exception as e:
                logger.warning(f"Failed to create suggested link: {e}")
    
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "suggestions": suggestions,
        "created_count": len(created_links),
        "created_links": created_links if create_links else None,
    }


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


@router.post("/build-from-embeddings")
async def build_graph_from_embeddings(
    min_similarity: float = Query(0.8, ge=0.5, le=1.0),
    entity_types: Optional[str] = Query("meeting,document,ticket,dikw", description="Comma-separated"),
    dry_run: bool = Query(True, description="If true, don't actually create links"),
) -> dict:
    """
    Build knowledge graph links from existing embeddings.
    
    This is a batch operation that finds all semantically similar
    pairs of entities and creates links between them.
    """
    sb = get_supabase_client()
    if not sb:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase not available for embedding search"
        )
    
    types = entity_types.split(",") if entity_types else ["meeting", "document", "ticket", "dikw"]
    
    created = 0
    skipped = 0
    suggestions = []
    
    # For each entity type, get all entities and find similar ones
    for etype in types:
        # Get all entities of this type from Supabase
        rows = []
        if etype == "meeting":
            result = sb.table("meeting_summaries").select("id, synthesized_notes").not_.is_("synthesized_notes", "null").limit(100).execute()
            rows = [{"id": r["id"], "content": r["synthesized_notes"]} for r in result.data or []]
        elif etype == "document":
            result = sb.table("docs").select("id, content").not_.is_("content", "null").limit(100).execute()
            rows = [{"id": r["id"], "content": r["content"]} for r in result.data or []]
        elif etype == "ticket":
            result = sb.table("tickets").select("id, description").not_.is_("description", "null").limit(100).execute()
            rows = [{"id": r["id"], "content": r["description"]} for r in result.data or []]
        elif etype == "dikw":
            result = sb.table("dikw_items").select("id, content").not_.is_("content", "null").limit(100).execute()
            rows = [{"id": r["id"], "content": r["content"]} for r in result.data or []]
        else:
            continue
        
        for row in rows:
            if not row.get("content"):
                continue
            
            embedding = get_embedding(row["content"][:8000])
            if not embedding:
                continue
            
            try:
                result = sb.rpc("semantic_search", {
                    "query_embedding": embedding,
                    "match_threshold": min_similarity,
                    "match_count": 10,
                }).execute()
                
                for item in result.data or []:
                    item_type = item.get("ref_type")
                    item_id = item.get("ref_id")
                    similarity = item.get("similarity", 0)
                    
                    # Skip self
                    if item_type == etype and str(item_id) == str(row["id"]):
                        continue
                    
                    # Skip if not in allowed types
                    if item_type not in types:
                        continue
                    
                    # Check if link exists
                    existing_check = sb.table("entity_links").select("id").or_(
                        f"and(source_type.eq.{etype},source_id.eq.{row['id']},target_type.eq.{item_type},target_id.eq.{item_id})," +
                        f"and(source_type.eq.{item_type},source_id.eq.{item_id},target_type.eq.{etype},target_id.eq.{row['id']})"
                    ).execute()
                    
                    if existing_check.data:
                        skipped += 1
                        continue
                    
                    link_type = "semantic_similar" if similarity > 0.85 else "same_topic"
                    
                    if not dry_run:
                        sb.table("entity_links").insert({
                            "source_type": etype,
                            "source_id": row["id"],
                            "target_type": item_type,
                            "target_id": item_id,
                            "link_type": link_type,
                            "similarity_score": similarity,
                            "confidence": 0.8,
                            "is_bidirectional": True,
                            "created_by": "system"
                        }).execute()
                        created += 1
                    else:
                        suggestions.append({
                            "source": f"{etype}/{row['id']}",
                            "target": f"{item_type}/{item_id}",
                            "similarity": round(similarity, 3),
                            "link_type": link_type,
                        })
                        
            except Exception as e:
                logger.warning(f"Failed to process {etype}/{row['id']}: {e}")
    
    return {
        "dry_run": dry_run,
        "links_created": created,
        "links_skipped": skipped,
        "suggestions": suggestions[:50] if dry_run else None,
    }


@router.post("/link-documents")
async def link_all_documents(
    min_similarity: float = Query(0.78, ge=0.5, le=1.0),
    dry_run: bool = Query(True, description="If true, show what would be linked"),
    limit: int = Query(50, ge=1, le=200, description="Max documents to process"),
) -> dict:
    """
    P5.11: Batch link existing documents to related meetings/tickets/DIKW items.
    
    This processes unlinked documents and creates entity_links based on
    semantic similarity to other content.
    """
    sb = get_supabase_client()
    if not sb:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase not available for semantic search"
        )
    
    # Get documents - we'll filter by link count after fetching
    # since Supabase doesn't support complex LEFT JOIN with GROUP BY in client
    docs_result = sb.table("docs").select("id, source, content").not_.is_("content", "null").order("id", desc=True).limit(limit * 2).execute()
    
    # Get existing link counts for documents
    existing_links_result = sb.table("entity_links").select("source_id").eq("source_type", "document").eq("created_by", "system").execute()
    
    # Count links per document
    doc_link_counts = {}
    for link in existing_links_result.data or []:
        sid = link.get("source_id")
        if sid:
            doc_link_counts[sid] = doc_link_counts.get(sid, 0) + 1
    
    # Filter documents with fewer than 3 links and valid content
    docs = []
    for d in docs_result.data or []:
        content = d.get("content", "")
        if content and len(content) > 50 and doc_link_counts.get(d["id"], 0) < 3:
            docs.append(d)
            if len(docs) >= limit:
                break
    
    processed = 0
    links_created = 0
    suggestions = []
    
    for doc in docs:
        try:
            # Generate embedding
            embedding = get_embedding(doc["content"][:8000])
            if not embedding:
                continue
            
            # Search for similar content
            result = sb.rpc("semantic_search", {
                "query_embedding": embedding,
                "match_threshold": min_similarity,
                "match_count": 10,
            }).execute()
            
            for item in result.data or []:
                item_type = item.get("ref_type")
                item_id = item.get("ref_id")
                similarity = item.get("similarity", 0)
                
                # Skip self and other documents
                if item_type == "document":
                    continue
                
                # Check if link exists
                existing_check = sb.table("entity_links").select("id").eq(
                    "source_type", "document"
                ).eq("source_id", doc["id"]).eq(
                    "target_type", item_type
                ).eq("target_id", item_id).execute()
                
                if existing_check.data:
                    continue
                
                link_type = "semantic_similar" if similarity > 0.85 else "same_topic"
                
                if not dry_run:
                    sb.table("entity_links").insert({
                        "source_type": "document",
                        "source_id": doc["id"],
                        "target_type": item_type,
                        "target_id": item_id,
                        "link_type": link_type,
                        "similarity_score": similarity,
                        "confidence": 0.8,
                        "is_bidirectional": True,
                        "created_by": "system"
                    }).execute()
                    links_created += 1
                else:
                    suggestions.append({
                        "document_id": doc["id"],
                        "document_source": (doc.get("source") or "")[:50],
                        "target": f"{item_type}/{item_id}",
                        "similarity": round(similarity, 3),
                        "link_type": link_type,
                    })
            
            processed += 1
            
        except Exception as e:
            logger.warning(f"Failed to process document {doc['id']}: {e}")
    
    return {
        "dry_run": dry_run,
        "documents_processed": processed,
        "links_created": links_created,
        "suggestions": suggestions[:30] if dry_run else None,
    }
