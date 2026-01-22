# src/app/api/v1/documents.py
"""
API v1 - Documents endpoints.

RESTful endpoints for document CRUD operations with proper pagination,
HTTP status codes, and Pydantic validation.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional

from ..v1.models import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    PaginatedResponse, APIResponse
)
from ...db import connect

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
):
    """
    List all documents with pagination.
    
    Returns documents ordered by most recently created first.
    """
    with connect() as conn:
        query = "SELECT * FROM document"
        params = []
        
        if doc_type:
            query += " WHERE doc_type = ?"
            params.append(doc_type)
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
        total = conn.execute(count_query, tuple(params)).fetchone()["count"]
        
        # Add pagination
        query += " ORDER BY pk DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])
        
        rows = conn.execute(query, tuple(params)).fetchall()
        documents = [dict(row) for row in rows]
    
    return PaginatedResponse(
        items=documents,
        skip=skip,
        limit=limit,
        total=total
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int):
    """
    Get a single document by ID.
    
    Returns 404 if document not found.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM document WHERE pk = ?",
            (document_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = dict(row)
    return DocumentResponse(
        id=doc.get("pk"),
        title=doc.get("title", ""),
        content=doc.get("content", ""),
        doc_type=doc.get("doc_type", "note"),
        created_at=doc.get("created_at")
    )


@router.post("", response_model=APIResponse, status_code=201)
async def create_document(document: DocumentCreate):
    """
    Create a new document.
    
    Returns the created document ID.
    """
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO document (title, content, doc_type)
               VALUES (?, ?, ?)""",
            (document.title, document.content, document.doc_type)
        )
        document_id = cursor.lastrowid
        conn.commit()
    
    return APIResponse(
        success=True,
        message="Document created",
        data={"id": document_id}
    )


@router.put("/{document_id}", response_model=APIResponse)
async def update_document(document_id: int, document: DocumentUpdate):
    """
    Update an existing document.
    
    Only updates fields that are provided.
    Returns 404 if document not found.
    """
    with connect() as conn:
        # Check if document exists
        existing = conn.execute(
            "SELECT pk FROM document WHERE pk = ?",
            (document_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Build dynamic update query
        updates = []
        params = []
        
        if document.title is not None:
            updates.append("title = ?")
            params.append(document.title)
        if document.content is not None:
            updates.append("content = ?")
            params.append(document.content)
        
        if updates:
            query = f"UPDATE document SET {', '.join(updates)} WHERE pk = ?"
            params.append(document_id)
            conn.execute(query, tuple(params))
            conn.commit()
    
    return APIResponse(
        success=True,
        message="Document updated",
        data={"id": document_id}
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: int):
    """
    Delete a document.
    
    Returns 204 No Content on success, 404 if document not found.
    """
    with connect() as conn:
        # Check if document exists
        existing = conn.execute(
            "SELECT pk FROM document WHERE pk = ?",
            (document_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        
        conn.execute("DELETE FROM document WHERE pk = ?", (document_id,))
        conn.commit()
    
    return Response(status_code=204)
