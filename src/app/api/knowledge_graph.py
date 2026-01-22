# src/app/api/knowledge_graph.py
"""
Knowledge Graph API - P5.10

Manages entity links between meetings, documents, tickets, DIKW items, and signals.
Uses SQLite/Supabase for storage instead of requiring Neo4j.

Graph Features:
- Link any two entities with typed relationships
- Query related entities for a given item
- Auto-suggest links based on semantic similarity
- Track link provenance (system/user/ai created)
"""

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..db import connect
from .search import get_embedding, get_supabase_client

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

def get_entity_title(entity_type: str, entity_id: int, conn) -> str:
    """Get the title/name of an entity."""
    try:
        if entity_type == "meeting":
            row = conn.execute(
                "SELECT meeting_name FROM meeting_summaries WHERE id = ?", (entity_id,)
            ).fetchone()
            return row["meeting_name"] if row else "Unknown Meeting"
        elif entity_type == "document":
            row = conn.execute(
                "SELECT source FROM docs WHERE id = ?", (entity_id,)
            ).fetchone()
            return row["source"] if row else "Unknown Document"
        elif entity_type == "ticket":
            row = conn.execute(
                "SELECT ticket_id, title FROM tickets WHERE id = ?", (entity_id,)
            ).fetchone()
            return f"{row['ticket_id']}: {row['title']}" if row else "Unknown Ticket"
        elif entity_type == "dikw":
            row = conn.execute(
                "SELECT level, content FROM dikw_items WHERE id = ?", (entity_id,)
            ).fetchone()
            if row:
                return f"[{row['level'].upper()}] {row['content'][:50]}..."
            return "Unknown DIKW Item"
        elif entity_type == "signal":
            row = conn.execute(
                "SELECT signal_type, signal_text FROM signal_status WHERE id = ?", (entity_id,)
            ).fetchone()
            if row:
                return f"[{row['signal_type']}] {row['signal_text'][:50]}..."
            return "Unknown Signal"
        return "Unknown"
    except Exception as e:
        logger.warning(f"Failed to get entity title: {e}")
        return "Unknown"


def get_entity_snippet(entity_type: str, entity_id: int, conn) -> str:
    """Get a snippet of the entity content."""
    try:
        if entity_type == "meeting":
            row = conn.execute(
                "SELECT synthesized_notes FROM meeting_summaries WHERE id = ?", (entity_id,)
            ).fetchone()
            content = row["synthesized_notes"] if row else ""
        elif entity_type == "document":
            row = conn.execute(
                "SELECT content FROM docs WHERE id = ?", (entity_id,)
            ).fetchone()
            content = row["content"] if row else ""
        elif entity_type == "ticket":
            row = conn.execute(
                "SELECT description FROM tickets WHERE id = ?", (entity_id,)
            ).fetchone()
            content = row["description"] if row else ""
        elif entity_type == "dikw":
            row = conn.execute(
                "SELECT content FROM dikw_items WHERE id = ?", (entity_id,)
            ).fetchone()
            content = row["content"] if row else ""
        elif entity_type == "signal":
            row = conn.execute(
                "SELECT signal_text FROM signal_status WHERE id = ?", (entity_id,)
            ).fetchone()
            content = row["signal_text"] if row else ""
        else:
            content = ""
        
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
    with connect() as conn:
        # Verify both entities exist
        source_title = get_entity_title(link.source_type, link.source_id, conn)
        target_title = get_entity_title(link.target_type, link.target_id, conn)
        
        if source_title.startswith("Unknown") or target_title.startswith("Unknown"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both entities not found"
            )
        
        # Insert the link
        try:
            metadata_json = json.dumps(link.metadata) if link.metadata else None
            
            result = conn.execute(
                """INSERT INTO entity_links 
                   (source_type, source_id, target_type, target_id, link_type,
                    similarity_score, confidence, is_bidirectional, metadata, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id, created_at""",
                (link.source_type, link.source_id, link.target_type, link.target_id,
                 link.link_type, link.similarity_score, link.confidence,
                 1 if link.is_bidirectional else 0, metadata_json, link.created_by)
            ).fetchone()
            
            conn.commit()
            
            return LinkResponse(
                id=result["id"],
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
                created_at=result["created_at"],
            )
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
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
    with connect() as conn:
        entity_title = get_entity_title(entity_type, entity_id, conn)
        
        if entity_title.startswith("Unknown"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_type}/{entity_id} not found"
            )
        
        links: List[LinkedEntity] = []
        include_type_list = include_types.split(",") if include_types else None
        
        # Get outgoing links (entity is source)
        if direction in ("outgoing", "both"):
            query = """
                SELECT id, target_type, target_id, link_type, similarity_score, confidence, is_bidirectional
                FROM entity_links
                WHERE source_type = ? AND source_id = ?
            """
            params = [entity_type, entity_id]
            
            if link_type:
                query += " AND link_type = ?"
                params.append(link_type)
            
            if include_type_list:
                placeholders = ",".join("?" * len(include_type_list))
                query += f" AND target_type IN ({placeholders})"
                params.extend(include_type_list)
            
            query += " ORDER BY similarity_score DESC NULLS LAST, confidence DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
            for row in rows:
                links.append(LinkedEntity(
                    entity_type=row["target_type"],
                    entity_id=row["target_id"],
                    title=get_entity_title(row["target_type"], row["target_id"], conn),
                    snippet=get_entity_snippet(row["target_type"], row["target_id"], conn),
                    link_type=row["link_type"],
                    link_direction="both" if row["is_bidirectional"] else "outgoing",
                    similarity_score=row["similarity_score"],
                    confidence=row["confidence"],
                ))
        
        # Get incoming links (entity is target)
        if direction in ("incoming", "both"):
            query = """
                SELECT id, source_type, source_id, link_type, similarity_score, confidence, is_bidirectional
                FROM entity_links
                WHERE target_type = ? AND target_id = ?
            """
            params = [entity_type, entity_id]
            
            if link_type:
                query += " AND link_type = ?"
                params.append(link_type)
            
            if include_type_list:
                placeholders = ",".join("?" * len(include_type_list))
                query += f" AND source_type IN ({placeholders})"
                params.extend(include_type_list)
            
            query += " ORDER BY similarity_score DESC NULLS LAST, confidence DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
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
                        title=get_entity_title(row["source_type"], row["source_id"], conn),
                        snippet=get_entity_snippet(row["source_type"], row["source_id"], conn),
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
    with connect() as conn:
        result = conn.execute(
            "DELETE FROM entity_links WHERE id = ? RETURNING id", (link_id,)
        ).fetchone()
        conn.commit()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Link {link_id} not found"
            )
        
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
    
    with connect() as conn:
        # Get entity content for embedding
        if entity_type == "meeting":
            row = conn.execute(
                "SELECT synthesized_notes as content FROM meeting_summaries WHERE id = ?",
                (entity_id,)
            ).fetchone()
        elif entity_type == "document":
            row = conn.execute(
                "SELECT content FROM docs WHERE id = ?", (entity_id,)
            ).fetchone()
        elif entity_type == "ticket":
            row = conn.execute(
                "SELECT description as content FROM tickets WHERE id = ?", (entity_id,)
            ).fetchone()
        elif entity_type == "dikw":
            row = conn.execute(
                "SELECT content FROM dikw_items WHERE id = ?", (entity_id,)
            ).fetchone()
        elif entity_type == "signal":
            row = conn.execute(
                "SELECT signal_text as content FROM signal_status WHERE id = ?",
                (entity_id,)
            ).fetchone()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entity type: {entity_type}"
            )
        
        if not row or not row["content"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_type}/{entity_id} not found or has no content"
            )
        
        content = row["content"]
        
        # Generate embedding
        embedding = get_embedding(content[:8000])
        if not embedding:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to generate embedding"
            )
        
        suggestions = []
        
        # Use Supabase semantic search if available
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
                    existing = conn.execute(
                        """SELECT id FROM entity_links 
                           WHERE (source_type = ? AND source_id = ? AND target_type = ? AND target_id = ?)
                              OR (source_type = ? AND source_id = ? AND target_type = ? AND target_id = ?)""",
                        (entity_type, entity_id, item_type, item_id,
                         item_type, item_id, entity_type, entity_id)
                    ).fetchone()
                    
                    if existing:
                        continue
                    
                    suggestions.append({
                        "target_type": item_type,
                        "target_id": item_id,
                        "target_title": get_entity_title(item_type, item_id, conn),
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
                    conn.execute(
                        """INSERT INTO entity_links 
                           (source_type, source_id, target_type, target_id, link_type,
                            similarity_score, confidence, is_bidirectional, created_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'ai')""",
                        (entity_type, entity_id, sug["target_type"], sug["target_id"],
                         sug["suggested_link_type"], sug["similarity_score"], 0.8)
                    )
                    created_links.append({
                        "target_type": sug["target_type"],
                        "target_id": sug["target_id"],
                    })
                except Exception as e:
                    logger.warning(f"Failed to create suggested link: {e}")
            
            conn.commit()
        
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
    with connect() as conn:
        # Total links
        total = conn.execute("SELECT COUNT(*) as c FROM entity_links").fetchone()["c"]
        
        # Links by type
        by_type = conn.execute(
            """SELECT link_type, COUNT(*) as c 
               FROM entity_links 
               GROUP BY link_type 
               ORDER BY c DESC"""
        ).fetchall()
        links_by_type = {row["link_type"]: row["c"] for row in by_type}
        
        # Entities with links
        source_counts = conn.execute(
            """SELECT source_type, COUNT(DISTINCT source_id) as c 
               FROM entity_links 
               GROUP BY source_type"""
        ).fetchall()
        target_counts = conn.execute(
            """SELECT target_type, COUNT(DISTINCT target_id) as c 
               FROM entity_links 
               GROUP BY target_type"""
        ).fetchall()
        
        entities_with_links = {}
        for row in source_counts:
            entities_with_links[row["source_type"]] = row["c"]
        for row in target_counts:
            existing = entities_with_links.get(row["target_type"], 0)
            entities_with_links[row["target_type"]] = max(existing, row["c"])
        
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
    
    with connect() as conn:
        created = 0
        skipped = 0
        suggestions = []
        
        # For each entity type, get all entities and find similar ones
        for etype in types:
            # Get all entities of this type
            if etype == "meeting":
                rows = conn.execute(
                    "SELECT id, synthesized_notes as content FROM meeting_summaries WHERE synthesized_notes IS NOT NULL LIMIT 100"
                ).fetchall()
            elif etype == "document":
                rows = conn.execute(
                    "SELECT id, content FROM docs WHERE content IS NOT NULL LIMIT 100"
                ).fetchall()
            elif etype == "ticket":
                rows = conn.execute(
                    "SELECT id, description as content FROM tickets WHERE description IS NOT NULL LIMIT 100"
                ).fetchall()
            elif etype == "dikw":
                rows = conn.execute(
                    "SELECT id, content FROM dikw_items WHERE content IS NOT NULL LIMIT 100"
                ).fetchall()
            else:
                continue
            
            for row in rows:
                if not row["content"]:
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
                        existing = conn.execute(
                            """SELECT id FROM entity_links 
                               WHERE (source_type = ? AND source_id = ? AND target_type = ? AND target_id = ?)
                                  OR (source_type = ? AND source_id = ? AND target_type = ? AND target_id = ?)""",
                            (etype, row["id"], item_type, item_id,
                             item_type, item_id, etype, row["id"])
                        ).fetchone()
                        
                        if existing:
                            skipped += 1
                            continue
                        
                        link_type = "semantic_similar" if similarity > 0.85 else "same_topic"
                        
                        if not dry_run:
                            conn.execute(
                                """INSERT INTO entity_links 
                                   (source_type, source_id, target_type, target_id, link_type,
                                    similarity_score, confidence, is_bidirectional, created_by)
                                   VALUES (?, ?, ?, ?, ?, ?, 0.8, 1, 'system')""",
                                (etype, row["id"], item_type, item_id, link_type, similarity)
                            )
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
        
        if not dry_run:
            conn.commit()
        
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
    
    with connect() as conn:
        # Get documents without many links
        docs = conn.execute(
            """SELECT d.id, d.source, d.content 
               FROM docs d
               LEFT JOIN (
                   SELECT source_id, COUNT(*) as link_count 
                   FROM entity_links 
                   WHERE source_type = 'document' AND created_by = 'system'
                   GROUP BY source_id
               ) el ON d.id = el.source_id
               WHERE d.content IS NOT NULL AND LENGTH(d.content) > 50
               AND (el.link_count IS NULL OR el.link_count < 3)
               ORDER BY d.id DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        
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
                    existing = conn.execute(
                        """SELECT id FROM entity_links 
                           WHERE source_type = 'document' AND source_id = ? 
                           AND target_type = ? AND target_id = ?""",
                        (doc["id"], item_type, item_id)
                    ).fetchone()
                    
                    if existing:
                        continue
                    
                    link_type = "semantic_similar" if similarity > 0.85 else "same_topic"
                    
                    if not dry_run:
                        conn.execute(
                            """INSERT INTO entity_links 
                               (source_type, source_id, target_type, target_id, link_type,
                                similarity_score, confidence, is_bidirectional, created_by)
                               VALUES ('document', ?, ?, ?, ?, ?, 0.8, 1, 'system')""",
                            (doc["id"], item_type, item_id, link_type, similarity)
                        )
                        links_created += 1
                    else:
                        suggestions.append({
                            "document_id": doc["id"],
                            "document_source": doc["source"][:50],
                            "target": f"{item_type}/{item_id}",
                            "similarity": round(similarity, 3),
                            "link_type": link_type,
                        })
                
                processed += 1
                
            except Exception as e:
                logger.warning(f"Failed to process document {doc['id']}: {e}")
        
        if not dry_run:
            conn.commit()
        
        return {
            "dry_run": dry_run,
            "documents_processed": processed,
            "links_created": links_created,
            "suggestions": suggestions[:30] if dry_run else None,
        }
