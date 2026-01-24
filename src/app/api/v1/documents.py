# src/app/api/v1/documents.py
"""
API v1 - Documents endpoints.

RESTful endpoints for document CRUD operations with proper pagination,
HTTP status codes, and Pydantic validation.

Supabase-first with SQLite fallback for Railway ephemeral storage.
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, List, Dict, Any

from ..v1.models import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    PaginatedResponse, APIResponse
)
from ...db import connect

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_documents_from_supabase(skip: int = 0, limit: int = 50) -> tuple[List[Dict[str, Any]], int]:
    """
    Fetch documents from Supabase.
    Returns (documents_list, total_count) or raises exception.
    """
    try:
        from ...infrastructure.supabase import get_supabase_client
        supabase = get_supabase_client()
        
        # Get total count
        count_result = supabase.table("documents").select("id", count="exact").execute()
        total = count_result.count if count_result.count is not None else 0
        
        # Get paginated documents
        result = supabase.table("documents").select("*").order(
            "created_at", desc=True
        ).range(skip, skip + limit - 1).execute()
        
        documents = []
        for row in result.data or []:
            documents.append({
                "id": row.get("id"),
                "title": row.get("source", ""),  # 'source' in Supabase = 'title'
                "content": row.get("content", ""),
                "doc_type": row.get("doc_type", "note"),
                "created_at": row.get("created_at"),
            })
        
        logger.info(f"✅ Fetched {len(documents)} documents from Supabase")
        return documents, total
    except Exception as e:
        logger.error(f"❌ Failed to fetch from Supabase: {e}")
        raise


def _get_documents_from_sqlite(skip: int = 0, limit: int = 50) -> tuple[List[Dict[str, Any]], int]:
    """
    Fetch documents from SQLite docs table.
    Returns (documents_list, total_count).
    """
    with connect() as conn:
        # Get total count
        total = conn.execute("SELECT COUNT(*) as count FROM docs").fetchone()["count"]
        
        # Get paginated documents
        rows = conn.execute(
            """SELECT id, source, content, document_date, created_at
               FROM docs
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, skip)
        ).fetchall()
        
        documents = []
        for row in rows:
            documents.append({
                "id": row["id"],
                "title": row["source"] or "",
                "content": row["content"] or "",
                "doc_type": "note",  # SQLite schema doesn't have doc_type
                "created_at": row["created_at"],
            })
        
        return documents, total


@router.get("", response_model=PaginatedResponse)
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    doc_type: Optional[str] = Query(None, description="Filter by document type (ignored for now)"),
):
    """
    List all documents with pagination.
    
    Returns documents ordered by most recently created first.
    Uses Supabase as primary source with SQLite fallback.
    """
    # Try Supabase first
    try:
        documents, total = _get_documents_from_supabase(skip, limit)
        return PaginatedResponse(items=documents, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.warning(f"⚠️ Supabase unavailable, falling back to SQLite: {e}")
    
    # Fall back to SQLite
    try:
        documents, total = _get_documents_from_sqlite(skip, limit)
        return PaginatedResponse(items=documents, skip=skip, limit=limit, total=total)
    except Exception as e:
        logger.error(f"❌ SQLite also failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch documents")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get a single document by ID.
    
    Returns 404 if document not found.
    Accepts either UUID (Supabase) or integer (SQLite) ID.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase import get_supabase_client
        supabase = get_supabase_client()
        
        result = supabase.table("documents").select("*").eq("id", document_id).execute()
        if result.data:
            doc = result.data[0]
            return DocumentResponse(
                id=doc.get("id"),
                title=doc.get("source", ""),
                content=doc.get("content", ""),
                doc_type=doc.get("doc_type", "note"),
                created_at=doc.get("created_at")
            )
    except Exception as e:
        logger.warning(f"⚠️ Supabase lookup failed: {e}")
    
    # Fall back to SQLite
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM docs WHERE id = ?",
                (int(document_id) if document_id.isdigit() else -1,)
            ).fetchone()
        
        if row:
            return DocumentResponse(
                id=str(row["id"]),
                title=row["source"] or "",
                content=row["content"] or "",
                doc_type="note",
                created_at=row["created_at"]
            )
    except Exception as e:
        logger.error(f"❌ SQLite lookup failed: {e}")
    
    raise HTTPException(status_code=404, detail="Document not found")


@router.post("", response_model=APIResponse, status_code=201)
async def create_document(document: DocumentCreate):
    """
    Create a new document.
    
    Creates in Supabase first, then falls back to SQLite.
    Returns the created document ID.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase import get_supabase_client
        supabase = get_supabase_client()
        
        result = supabase.table("documents").insert({
            "source": document.title,
            "content": document.content or "",
            "doc_type": document.doc_type or "note",
        }).execute()
        
        if result.data:
            document_id = result.data[0]["id"]
            logger.info(f"✅ Created document {document_id} in Supabase")
            return APIResponse(success=True, message="Document created", data={"id": document_id})
    except Exception as e:
        logger.warning(f"⚠️ Supabase create failed, trying SQLite: {e}")
    
    # Fall back to SQLite
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO docs (source, content)
               VALUES (?, ?)""",
            (document.title, document.content or "")
        )
        document_id = cursor.lastrowid
        conn.commit()
    
    return APIResponse(success=True, message="Document created", data={"id": document_id})


@router.put("/{document_id}", response_model=APIResponse)
async def update_document(document_id: str, document: DocumentUpdate):
    """
    Update an existing document.
    
    Only updates fields that are provided.
    Returns 404 if document not found.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase import get_supabase_client
        supabase = get_supabase_client()
        
        # Check if document exists
        existing = supabase.table("documents").select("id").eq("id", document_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Build update dict
        updates = {}
        if document.title is not None:
            updates["source"] = document.title
        if document.content is not None:
            updates["content"] = document.content
        
        if updates:
            supabase.table("documents").update(updates).eq("id", document_id).execute()
        
        return APIResponse(success=True, message="Document updated", data={"id": document_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"⚠️ Supabase update failed: {e}")
    
    # Fall back to SQLite
    with connect() as conn:
        sqlite_id = int(document_id) if document_id.isdigit() else -1
        existing = conn.execute("SELECT id FROM docs WHERE id = ?", (sqlite_id,)).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        
        updates = []
        params = []
        if document.title is not None:
            updates.append("source = ?")
            params.append(document.title)
        if document.content is not None:
            updates.append("content = ?")
            params.append(document.content)
        
        if updates:
            query = f"UPDATE docs SET {', '.join(updates)} WHERE id = ?"
            params.append(sqlite_id)
            conn.execute(query, tuple(params))
            conn.commit()
    
    return APIResponse(success=True, message="Document updated", data={"id": document_id})


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """
    Delete a document.
    
    Returns 204 No Content on success, 404 if document not found.
    """
    # Try Supabase first
    try:
        from ...infrastructure.supabase import get_supabase_client
        supabase = get_supabase_client()
        
        # Check if document exists
        existing = supabase.table("documents").select("id").eq("id", document_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        supabase.table("documents").delete().eq("id", document_id).execute()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"⚠️ Supabase delete failed: {e}")
    
    # Fall back to SQLite
    with connect() as conn:
        sqlite_id = int(document_id) if document_id.isdigit() else -1
        existing = conn.execute("SELECT id FROM docs WHERE id = ?", (sqlite_id,)).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        
        conn.execute("DELETE FROM docs WHERE id = ?", (sqlite_id,))
        conn.commit()
    
    return Response(status_code=204)
