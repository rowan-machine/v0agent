# src/app/domains/tickets/api/attachments.py
"""
Ticket Attachments API Routes

File upload, listing, and deletion for tickets and other entities.
"""

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import logging

from ....infrastructure.supabase_client import get_supabase_client
from ....memory.embed import embed_text, EMBED_MODEL
from ....memory.vector_store import upsert_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attachments")

VALID_REF_TYPES = {"meeting", "doc", "ticket"}


@router.post("/upload/{ref_type}/{ref_id}")
async def upload_files(
    ref_type: str,
    ref_id: int,
    files: list[UploadFile] = File(...),
):
    """Upload multiple files (screenshots, etc.) for a meeting, doc, or ticket.
    
    Files are uploaded to Supabase Storage and metadata saved to attachments table.
    """
    from ....services.storage_supabase import upload_file_to_supabase
    
    if ref_type not in VALID_REF_TYPES:
        return JSONResponse({"error": f"Invalid ref_type. Must be one of: {VALID_REF_TYPES}"}, status_code=400)
    
    uploaded = []
    
    for file in files:
        content = await file.read()
        
        # Upload to Supabase Storage
        public_url, storage_path = await upload_file_to_supabase(
            content=content,
            filename=file.filename,
            meeting_id=str(ref_id),  # Use ref_id as folder
            content_type=file.content_type or "application/octet-stream"
        )
        
        if not public_url:
            logger.warning(f"Failed to upload {file.filename} to Supabase Storage")
            continue
        
        # Generate AI description for images
        ai_description = None
        if file.content_type and file.content_type.startswith("image/"):
            ai_description = f"Screenshot uploaded for {ref_type} {ref_id}: {file.filename}"
        
        # Save to database
        supabase = get_supabase_client()
        insert_result = supabase.table("attachments").insert({
            "ref_type": ref_type,
            "ref_id": ref_id,
            "filename": file.filename,
            "file_path": storage_path,
            "file_url": public_url,
            "mime_type": file.content_type,
            "file_size": len(content),
            "ai_description": ai_description
        }).execute()
        attach_id = insert_result.data[0]["id"] if insert_result.data else None
        
        # Create embedding for the attachment
        embed_text_content = f"Attachment: {file.filename} for {ref_type}. {ai_description or ''}"
        vector = embed_text(embed_text_content)
        upsert_embedding("attachment", attach_id, EMBED_MODEL, vector)
        
        uploaded.append({
            "id": attach_id,
            "filename": file.filename,
            "url": public_url,
        })
    
    return JSONResponse({"uploaded": uploaded, "count": len(uploaded)})


@router.delete("/{attachment_id}")
async def delete_attachment(attachment_id: int):
    """Delete an attachment from Supabase Storage and database."""
    from ....services.storage_supabase import delete_file_from_supabase
    
    supabase = get_supabase_client()
    
    # Get file path first
    attach_result = supabase.table("attachments").select("file_path").eq("id", attachment_id).single().execute()
    attach = attach_result.data
    
    # Delete from Supabase Storage if path exists
    if attach and attach.get("file_path"):
        await delete_file_from_supabase(attach["file_path"])
    
    supabase.table("attachments").delete().eq("id", attachment_id).execute()
    supabase.table("embeddings").delete().eq("ref_type", "attachment").eq("ref_id", attachment_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/{ref_type}/{ref_id}")
async def list_attachments(ref_type: str, ref_id: int):
    """List attachments for a reference."""
    if ref_type not in VALID_REF_TYPES:
        return JSONResponse({"error": f"Invalid ref_type. Must be one of: {VALID_REF_TYPES}"}, status_code=400)
    
    supabase = get_supabase_client()
    result = supabase.table("attachments").select("*").eq("ref_type", ref_type).eq("ref_id", ref_id).execute()
    
    return JSONResponse({
        "attachments": result.data or []
    })
