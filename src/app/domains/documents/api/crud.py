# src/app/domains/documents/api/crud.py
"""
Document CRUD API Routes

Basic create, read, update, delete operations for documents.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_document_repository
from ..constants import DEFAULT_DOCUMENT_LIMIT, DOCUMENT_STATUSES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items")


@router.get("")
async def list_documents(
    limit: int = Query(DEFAULT_DOCUMENT_LIMIT, le=200),
    offset: int = Query(0, ge=0),
    doc_type: str = Query(None),
    status: str = Query("active")
):
    """List documents with pagination and optional filters."""
    repo = get_document_repository()
    
    documents = repo.list(limit=limit, offset=offset)
    
    # Apply filters
    if doc_type:
        documents = [d for d in documents if (d.get("doc_type") if isinstance(d, dict) else getattr(d, "doc_type", None)) == doc_type]
    if status:
        documents = [d for d in documents if (d.get("status") if isinstance(d, dict) else getattr(d, "status", "active")) == status]
    
    return JSONResponse({
        "status": "ok",
        "documents": [d if isinstance(d, dict) else d.__dict__ for d in documents],
        "count": len(documents),
        "limit": limit,
        "offset": offset
    })


@router.get("/{document_id}")
async def get_document(document_id: str):
    """Get a specific document by ID."""
    repo = get_document_repository()
    
    document = repo.get(document_id)
    if not document:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    
    doc_dict = document if isinstance(document, dict) else document.__dict__
    return JSONResponse({"status": "ok", "document": doc_dict})


@router.post("")
async def create_document(request: Request):
    """Create a new document."""
    data = await request.json()
    
    repo = get_document_repository()
    
    # Validate required fields
    if not data.get("title"):
        return JSONResponse({"error": "title is required"}, status_code=400)
    
    # Set defaults
    data.setdefault("status", "draft")
    data.setdefault("doc_type", "note")
    
    document = repo.create(data)
    if not document:
        return JSONResponse({"error": "Failed to create document"}, status_code=500)
    
    doc_dict = document if isinstance(document, dict) else document.__dict__
    return JSONResponse({"status": "ok", "document": doc_dict}, status_code=201)


@router.put("/{document_id}")
async def update_document(document_id: str, request: Request):
    """Update an existing document."""
    data = await request.json()
    
    repo = get_document_repository()
    
    existing = repo.get(document_id)
    if not existing:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    
    updated = repo.update(document_id, data)
    if not updated:
        return JSONResponse({"error": "Failed to update document"}, status_code=500)
    
    doc_dict = updated if isinstance(updated, dict) else updated.__dict__
    return JSONResponse({"status": "ok", "document": doc_dict})


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document (soft delete - sets status to archived)."""
    repo = get_document_repository()
    
    existing = repo.get(document_id)
    if not existing:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    
    # Soft delete by archiving
    updated = repo.update(document_id, {"status": "archived"})
    if not updated:
        return JSONResponse({"error": "Failed to delete document"}, status_code=500)
    
    return JSONResponse({"status": "ok", "message": "Document archived"})


@router.put("/{document_id}/status")
async def update_document_status(document_id: str, request: Request):
    """Update document status."""
    data = await request.json()
    new_status = data.get("status")
    
    if not new_status:
        return JSONResponse({"error": "status is required"}, status_code=400)
    
    if new_status not in DOCUMENT_STATUSES:
        return JSONResponse({"error": f"Invalid status. Must be one of: {DOCUMENT_STATUSES}"}, status_code=400)
    
    repo = get_document_repository()
    
    updated = repo.update(document_id, {"status": new_status})
    if not updated:
        return JSONResponse({"error": "Failed to update status"}, status_code=500)
    
    return JSONResponse({"status": "ok", "document_id": document_id, "new_status": new_status})
