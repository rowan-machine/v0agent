from fastapi import APIRouter, Form, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from .db import connect
from .memory.embed import embed_text, EMBED_MODEL
from .memory.vector_store import upsert_embedding
from .services import documents_supabase  # Supabase-first reads

# NOTE: Neo4j removed - using Supabase knowledge graph instead (Phase 5.10)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


# -------------------------
# P5.11: Intelligent Document Linking
# -------------------------

def auto_link_document(doc_id: int, content: str, min_similarity: float = 0.78):
    """
    Automatically create entity links for a new document based on semantic similarity.
    
    Uses pgvector semantic search to find related meetings, tickets, and DIKW items,
    then creates links in the entity_links table.
    
    Args:
        doc_id: ID of the newly created document
        content: Document content for embedding
        min_similarity: Minimum similarity threshold for auto-linking
    """
    try:
        # Try to use Supabase for semantic search
        import os
        from supabase import create_client
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            logger.debug("Supabase not configured, skipping auto-link")
            return
        
        sb = create_client(url, key)
        
        # Generate embedding for the document
        import openai
        client = openai.OpenAI()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=content[:8000]  # Limit to model context
        )
        embedding = response.data[0].embedding
        
        # Search for similar content
        result = sb.rpc("semantic_search", {
            "query_embedding": embedding,
            "match_threshold": min_similarity,
            "match_count": 10,
        }).execute()
        
        with connect() as conn:
            links_created = 0
            
            for item in result.data or []:
                item_type = item.get("ref_type")
                item_id = item.get("ref_id")
                similarity = item.get("similarity", 0)
                
                # Skip self-references (same document)
                if item_type == "document" and str(item_id) == str(doc_id):
                    continue
                
                # Skip documents with same content (likely transcripts)
                if item_type == "document":
                    continue
                
                # Determine link type based on similarity
                link_type = "semantic_similar" if similarity > 0.85 else "same_topic"
                
                # Check if link already exists
                existing = conn.execute(
                    """SELECT id FROM entity_links 
                       WHERE source_type = 'document' AND source_id = ? 
                       AND target_type = ? AND target_id = ?""",
                    (doc_id, item_type, item_id)
                ).fetchone()
                
                if existing:
                    continue
                
                # Create the link
                conn.execute(
                    """INSERT INTO entity_links 
                       (source_type, source_id, target_type, target_id, link_type,
                        similarity_score, confidence, is_bidirectional, created_by)
                       VALUES ('document', ?, ?, ?, ?, ?, 0.8, 1, 'system')""",
                    (doc_id, item_type, item_id, link_type, similarity)
                )
                links_created += 1
                
                if links_created >= 5:  # Limit auto-links per document
                    break
            
            conn.commit()
            
            if links_created > 0:
                logger.info(f"Auto-linked document {doc_id} to {links_created} related items")
                
    except ImportError as e:
        logger.debug(f"Auto-link skipped (missing module): {e}")
    except Exception as e:
        logger.warning(f"Auto-link failed for document {doc_id}: {e}")


@router.post("/documents/store")
def store_doc(
    source: str = Form(...),
    content: str = Form(...),
    document_date: str = Form(...)
):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO docs (source, content, document_date) VALUES (?, ?, ?)",
            (source, content, document_date),
        )
        doc_id = cur.lastrowid

    # ---- VX.2b: embedding on ingest ----
    text_for_embedding = f"{source}\n{content}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("doc", doc_id, EMBED_MODEL, vector)

    # ---- P5.11: Intelligent document linking ----
    auto_link_document(doc_id, content)

    return RedirectResponse(url="/documents?success=document_created", status_code=303)


@router.get("/documents")
def list_documents(request: Request, success: str = Query(default=None)):
    # Read from Supabase directly
    rows = documents_supabase.get_all_documents(limit=500)

    formatted_docs = []
    for row in rows:
        doc = dict(row)
        date_str = doc.get("document_date") or doc.get("created_at")
        if date_str:
            try:
                if " " in str(date_str):
                    dt = datetime.strptime(str(date_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
                    dt_utc = dt.replace(tzinfo=ZoneInfo("UTC"))
                    dt_central = dt_utc.astimezone(ZoneInfo("America/Chicago"))
                    doc["display_date"] = dt_central.strftime("%Y-%m-%d %I:%M %p %Z")
                elif "T" in str(date_str):
                    # ISO format from Supabase
                    dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    dt_central = dt.astimezone(ZoneInfo("America/Chicago"))
                    doc["display_date"] = dt_central.strftime("%Y-%m-%d %I:%M %p %Z")
                else:
                    doc["display_date"] = date_str
            except Exception:
                doc["display_date"] = date_str
        else:
            doc["display_date"] = ""

        formatted_docs.append(doc)

    return templates.TemplateResponse(
        "list_docs.html",
        {"request": request, "docs": formatted_docs, "success": success},
    )


@router.get("/documents/{doc_id}")
def view_document(doc_id: str, request: Request, highlight: str = None):
    # Read from Supabase directly
    doc = documents_supabase.get_document_by_id(doc_id)

    return templates.TemplateResponse(
        "view_doc.html",
        {"request": request, "doc": doc, "highlight": highlight},
    )


@router.get("/documents/{doc_id}/edit")
def edit_document(doc_id: str, request: Request):
    # Read from Supabase directly
    doc = documents_supabase.get_document_by_id(doc_id)
    
    if doc and doc.get('source') and doc.get('source').startswith('Transcript: '):
        meeting_name = doc['source'].replace('Transcript: ', '').split(' (')[0]
        with connect() as conn:
            meeting = conn.execute(
                "SELECT id FROM meeting_summaries WHERE meeting_name = ?",
                (meeting_name,)
            ).fetchone()
            if meeting:
                # Redirect to the meeting edit page instead
                return RedirectResponse(
                    url=f"/meetings/{meeting['id']}/edit?from_transcript={doc_id}",
                    status_code=302
                )

    return templates.TemplateResponse(
        "edit_doc.html",
        {"request": request, "doc": doc},
    )


@router.post("/documents/{doc_id}/edit")
def update_document(
    doc_id: int,
    source: str = Form(...),
    content: str = Form(...),
    document_date: str = Form(...)
):
    # Update in Supabase
    documents_supabase.update_document(doc_id, {
        "source": source,
        "content": content,
        "document_date": document_date
    })
    
    # Also update SQLite for backwards compatibility
    with connect() as conn:
        conn.execute(
            """
            UPDATE docs
            SET source = ?, content = ?, document_date = ?
            WHERE id = ?
            """,
            (source, content, document_date, doc_id),
        )

    # ---- VX.2b: embedding on update ----
    text_for_embedding = f"{source}\n{content}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("doc", doc_id, EMBED_MODEL, vector)

    # ---- P5.11: Re-link on content change ----
    # Clear old auto-links and regenerate
    with connect() as conn:
        conn.execute(
            """DELETE FROM entity_links 
               WHERE source_type = 'document' AND source_id = ? 
               AND created_by = 'system'""",
            (doc_id,)
        )
        conn.commit()
    auto_link_document(doc_id, content)

    return RedirectResponse(url="/documents?success=document_updated", status_code=303)


@router.post("/documents/{doc_id}/delete")
def delete_document(doc_id: str):
    # Delete from Supabase first (source of truth)
    documents_supabase.delete_document(doc_id)
    
    # Also clean up SQLite for backwards compatibility
    with connect() as conn:
        conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
        conn.execute(
            "DELETE FROM embeddings WHERE ref_type = 'doc' AND ref_id = ?",
            (doc_id,),
        )

    return RedirectResponse(url="/documents?success=document_deleted", status_code=303)
