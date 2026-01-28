# src/app/domains/knowledge_graph/api/suggestions.py
"""
Knowledge Graph Auto-Suggestion and Build API

Endpoints for auto-suggesting and building graph links from embeddings.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status

from .helpers import get_entity_title, get_entity_snippet, get_embedding
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/links/auto-suggest/{entity_type}/{entity_id}")
async def auto_suggest_links(
    entity_type: str,
    entity_id: int,
    min_similarity: float = Query(0.75, ge=0.5, le=1.0),
    max_suggestions: int = Query(10, ge=1, le=50),
    create_links: bool = Query(False, description="If true, actually create the links"),
) -> dict:
    """
    Auto-suggest links for an entity based on semantic similarity.
    
    This uses pgvector semantic search to find similar content
    and suggests links to those entities.
    """
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not configured"
        )
    
    # Verify entity exists and get its content
    entity_title = get_entity_title(entity_type, entity_id, supabase)
    if entity_title.startswith("Unknown"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_type}/{entity_id} not found"
        )
    
    # Get full content for embedding
    content = ""
    try:
        if entity_type == "meeting":
            result = supabase.table("meetings").select("synthesized_notes").eq("id", entity_id).execute()
            content = result.data[0]["synthesized_notes"] if result.data else ""
        elif entity_type == "document":
            result = supabase.table("documents").select("content").eq("id", entity_id).execute()
            content = result.data[0]["content"] if result.data else ""
        elif entity_type == "ticket":
            result = supabase.table("tickets").select("description").eq("id", entity_id).execute()
            content = result.data[0]["description"] if result.data else ""
        elif entity_type == "dikw":
            result = supabase.table("dikw_items").select("content").eq("id", entity_id).execute()
            content = result.data[0]["content"] if result.data else ""
        elif entity_type == "signal":
            result = supabase.table("signal_status").select("signal_text").eq("id", entity_id).execute()
            content = result.data[0]["signal_text"] if result.data else ""
    except Exception as e:
        logger.warning(f"Failed to get entity content: {e}")
    
    if not content:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "suggestions": [],
            "message": "No content available for semantic search"
        }
    
    # Generate embedding
    embedding = get_embedding(content[:8000])
    if not embedding:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "suggestions": [],
            "message": "Failed to generate embedding"
        }
    
    # Search for similar content using Supabase vector search
    try:
        result = supabase.rpc("semantic_search", {
            "query_embedding": embedding,
            "match_threshold": min_similarity,
            "match_count": max_suggestions * 2,  # Get extra to account for filtering
        }).execute()
        
        similar_items = result.data or []
    except Exception as e:
        logger.warning(f"Semantic search failed: {e}")
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "suggestions": [],
            "message": f"Semantic search failed: {str(e)}"
        }
    
    # Get existing links to filter out
    existing_result = supabase.table("entity_links").select("target_type, target_id").or_(
        f"and(source_type.eq.{entity_type},source_id.eq.{entity_id}),and(target_type.eq.{entity_type},target_id.eq.{entity_id})"
    ).execute()
    
    existing_links = set()
    for link in existing_result.data or []:
        existing_links.add((link.get("target_type"), link.get("target_id")))
    
    # Build suggestions
    suggestions = []
    created_links = []
    
    for item in similar_items:
        item_type = item.get("ref_type")
        item_id = item.get("ref_id")
        similarity = item.get("similarity", 0)
        
        # Skip self
        if item_type == entity_type and str(item_id) == str(entity_id):
            continue
        
        # Skip already linked
        if (item_type, item_id) in existing_links:
            continue
        
        # Get item details
        item_title = get_entity_title(item_type, item_id, supabase)
        item_snippet = get_entity_snippet(item_type, item_id, supabase)
        
        suggestion = {
            "entity_type": item_type,
            "entity_id": item_id,
            "title": item_title,
            "snippet": item_snippet,
            "similarity_score": round(similarity, 3),
            "suggested_link_type": "semantic_similar" if similarity > 0.85 else "same_topic",
        }
        suggestions.append(suggestion)
        
        # Create link if requested
        if create_links and len(suggestions) <= max_suggestions:
            try:
                link_type = "semantic_similar" if similarity > 0.85 else "same_topic"
                supabase.table("entity_links").insert({
                    "source_type": entity_type,
                    "source_id": entity_id,
                    "target_type": item_type,
                    "target_id": item_id,
                    "link_type": link_type,
                    "similarity_score": similarity,
                    "confidence": 0.8,
                    "is_bidirectional": True,
                    "created_by": "ai"
                }).execute()
                created_links.append({
                    "target": f"{item_type}/{item_id}",
                    "link_type": link_type
                })
            except Exception as e:
                logger.warning(f"Failed to create link: {e}")
        
        if len(suggestions) >= max_suggestions:
            break
    
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "suggestions": suggestions,
        "created_count": len(created_links),
        "created_links": created_links if create_links else None,
    }


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
