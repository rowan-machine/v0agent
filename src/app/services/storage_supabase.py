"""
Supabase Storage Service for file uploads.

Handles uploading attachments (screenshots, PDFs) to Supabase Storage
instead of local filesystem.
"""

import logging
import os
import uuid
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Bucket name for meeting attachments
BUCKET_NAME = "meeting-uploads"


def get_storage_client():
    """Get Supabase storage client."""
    try:
        from ..infrastructure.supabase_client import get_supabase_client
        client = get_supabase_client()
        if client:
            return client.storage
        return None
    except Exception as e:
        logger.error(f"Failed to get storage client: {e}")
        return None


async def upload_file_to_supabase(
    content: bytes,
    filename: str,
    meeting_id: str,
    content_type: str = "image/png"
) -> Tuple[Optional[str], Optional[str]]:
    """
    Upload a file to Supabase Storage.
    
    Args:
        content: File content as bytes
        filename: Original filename
        meeting_id: Meeting ID to organize files
        content_type: MIME type of the file
        
    Returns:
        Tuple of (public_url, storage_path) or (None, None) on failure
    """
    storage = get_storage_client()
    
    if not storage:
        logger.warning("Supabase Storage not available, falling back to local")
        return None, None
    
    try:
        # Generate unique path: meetings/{meeting_id}/{uuid}.{ext}
        ext = os.path.splitext(filename)[1] or ".png"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        storage_path = f"meetings/{meeting_id}/{unique_name}"
        
        # Upload to Supabase Storage
        result = storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type}
        )
        
        # Get public URL
        url_data = storage.from_(BUCKET_NAME).get_public_url(storage_path)
        public_url = url_data if isinstance(url_data, str) else url_data.get("publicUrl")
        
        logger.info(f"✅ Uploaded {filename} to Supabase Storage: {storage_path}")
        return public_url, storage_path
        
    except Exception as e:
        logger.error(f"❌ Failed to upload to Supabase Storage: {e}")
        return None, None


async def delete_file_from_supabase(storage_path: str) -> bool:
    """
    Delete a file from Supabase Storage.
    
    Args:
        storage_path: Path in storage bucket
        
    Returns:
        True if deleted, False otherwise
    """
    storage = get_storage_client()
    
    if not storage:
        return False
    
    try:
        storage.from_(BUCKET_NAME).remove([storage_path])
        logger.info(f"✅ Deleted from Supabase Storage: {storage_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete from Supabase Storage: {e}")
        return False


def get_public_url(storage_path: str) -> Optional[str]:
    """
    Get public URL for a file in Supabase Storage.
    
    Args:
        storage_path: Path in storage bucket
        
    Returns:
        Public URL or None
    """
    storage = get_storage_client()
    
    if not storage:
        return None
    
    try:
        url_data = storage.from_(BUCKET_NAME).get_public_url(storage_path)
        return url_data if isinstance(url_data, str) else url_data.get("publicUrl")
    except Exception as e:
        logger.error(f"Failed to get public URL: {e}")
        return None


async def migrate_local_uploads_to_supabase(upload_dir: str = "uploads") -> dict:
    """
    Migrate existing local uploads to Supabase Storage.
    
    Args:
        upload_dir: Local upload directory
        
    Returns:
        Dict with migration results
    """
    from ..db import connect
    
    storage = get_storage_client()
    if not storage:
        return {"error": "Supabase Storage not available"}
    
    results = {
        "total": 0,
        "migrated": 0,
        "failed": 0,
        "already_migrated": 0,
        "details": []
    }
    
    # Get all attachments from local database
    with connect() as conn:
        attachments = conn.execute("""
            SELECT id, ref_type, ref_id, filename, file_path, mime_type, file_size
            FROM attachments
            WHERE file_path LIKE 'uploads/%'
              AND (supabase_url IS NULL OR supabase_url = '')
        """).fetchall()
    
    results["total"] = len(attachments)
    
    for att in attachments:
        att_id = att["id"]
        ref_id = att["ref_id"]
        filename = att["filename"]
        local_path = att["file_path"]
        mime_type = att["mime_type"] or "image/png"
        
        full_local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), local_path)
        
        if not os.path.exists(full_local_path):
            results["failed"] += 1
            results["details"].append({"id": att_id, "error": "Local file not found"})
            continue
        
        try:
            # Read file content
            with open(full_local_path, "rb") as f:
                content = f.read()
            
            # Upload to Supabase
            public_url, storage_path = await upload_file_to_supabase(
                content=content,
                filename=filename,
                meeting_id=ref_id,
                content_type=mime_type
            )
            
            if public_url and storage_path:
                # Update database with Supabase URL
                with connect() as conn:
                    conn.execute("""
                        UPDATE attachments
                        SET supabase_url = ?, supabase_path = ?
                        WHERE id = ?
                    """, (public_url, storage_path, att_id))
                
                results["migrated"] += 1
                results["details"].append({
                    "id": att_id,
                    "filename": filename,
                    "url": public_url
                })
            else:
                results["failed"] += 1
                results["details"].append({"id": att_id, "error": "Upload failed"})
                
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"id": att_id, "error": str(e)})
    
    return results
