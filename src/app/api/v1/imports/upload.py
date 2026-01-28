# src/app/api/v1/imports/upload.py
"""
API v1 - File Upload endpoints.

Handles markdown/text file uploads to create meeting transcripts.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from datetime import datetime
import logging

from ....infrastructure.supabase_client import get_supabase_client
from ....mcp.parser import parse_meeting_summary
from ....mcp.extract import extract_structured_signals
from ....mcp.cleaner import clean_meeting_text
from .models import ImportResult, ImportHistoryItem
from .helpers import (
    extract_markdown_text,
    infer_meeting_name_from_content,
    record_import_history,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=ImportResult)
async def import_transcript(
    file: UploadFile = File(..., description="Markdown file to import"),
    meeting_name: Optional[str] = Form(None, description="Optional meeting name (auto-detected if not provided)"),
    meeting_date: Optional[str] = Form(None, description="Meeting date in YYYY-MM-DD format"),
    source_url: Optional[str] = Form(None, description="Original source URL (e.g., Pocket link)"),
):
    """
    Import a meeting transcript from an uploaded markdown file.
    
    The file content becomes the meeting's synthesized_notes.
    Signals are automatically extracted using the existing pipeline.
    
    **Supported formats:** .md, .markdown, .txt
    
    **Auto-detection:**
    - Meeting name is inferred from H1 header or first line if not provided
    - Meeting date defaults to today if not provided
    
    **Returns:**
    - meeting_id: The created meeting's ID
    - signal_count: Number of signals extracted
    - warnings: Any non-fatal issues encountered
    """
    warnings = []
    
    # Validate file type
    filename = file.filename or "unknown.md"
    file_ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    
    if file_ext not in ('md', 'markdown', 'txt'):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{file_ext}'. Supported: .md, .markdown, .txt"
        )
    
    # Read file content
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")
    
    # Extract text
    try:
        text = extract_markdown_text(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not text or len(text) < 10:
        raise HTTPException(status_code=400, detail="File content is too short (minimum 10 characters)")
    
    # Infer meeting name if not provided
    if not meeting_name:
        meeting_name = infer_meeting_name_from_content(text, filename)
        warnings.append(f"Meeting name auto-detected: '{meeting_name}'")
    
    # Default date to today if not provided
    if not meeting_date:
        meeting_date = datetime.now().strftime('%Y-%m-%d')
        warnings.append(f"Meeting date set to today: {meeting_date}")
    
    # Create meeting and extract signals
    try:
        supabase = get_supabase_client()
        
        # Record import attempt
        import_id = record_import_history(supabase, filename, file_ext, status="processing")
        
        # Insert meeting
        result = supabase.table("meetings").insert({
            "meeting_name": meeting_name,
            "synthesized_notes": text,
            "meeting_date": meeting_date,
            "raw_text": text,
            "import_source": "markdown_upload",
            "source_url": source_url
        }).execute()
        
        meeting_id = result.data[0]["id"] if result.data else None
        
        # Extract signals using the proper pipeline: clean -> parse -> extract
        try:
            cleaned_text = clean_meeting_text(text)
            parsed_sections = parse_meeting_summary(cleaned_text)
            signals = extract_structured_signals(parsed_sections)
            signal_count = sum(len(v) for v in signals.values() if isinstance(v, list))
            
            # Store signals as JSON
            supabase.table("meetings").update({
                "signals": signals
            }).eq("id", meeting_id).execute()
        except Exception as e:
            logger.warning(f"Signal extraction failed for import: {e}")
            signals = {}
            signal_count = 0
            warnings.append(f"Signal extraction failed: {str(e)}")
            
            # Update import history with success
            supabase.table("import_history").update({
                "status": "completed",
                "meeting_id": meeting_id
            }).eq("id", import_id).execute()
            
            logger.info(f"Imported meeting '{meeting_name}' (id={meeting_id}) with {signal_count} signals from {filename}")
            
            return ImportResult(
                meeting_id=meeting_id,
                meeting_name=meeting_name,
                transcript_length=len(text),
                signal_count=signal_count,
                import_source='markdown_upload',
                warnings=warnings
            )
            
    except Exception as e:
        logger.error(f"Import failed for {filename}: {e}")
        # Try to record failure
        try:
            supabase = get_supabase_client()
            supabase.table("import_history").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("filename", filename).eq("status", "processing").execute()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/history", response_model=list[ImportHistoryItem])
async def get_import_history(
    limit: int = 50,
    status: Optional[str] = None
):
    """
    Get import history records.
    
    **Parameters:**
    - limit: Maximum number of records to return (default: 50)
    - status: Filter by status ('pending', 'processing', 'completed', 'failed')
    """
    supabase = get_supabase_client()
    
    query = supabase.table("import_history").select("*").order("created_at", desc=True).limit(limit)
    
    if status:
        query = query.eq("status", status)
    
    result = query.execute()
    
    return [
        ImportHistoryItem(
            id=row['id'],
            filename=row['filename'],
            file_type=row['file_type'],
            meeting_id=row.get('meeting_id'),
            status=row['status'],
            error_message=row.get('error_message'),
            created_at=row['created_at']
        )
        for row in (result.data or [])
    ]


@router.delete("/history/{import_id}")
async def delete_import_record(import_id: int):
    """
    Delete an import history record.
    
    Note: This does NOT delete the associated meeting if one was created.
    """
    supabase = get_supabase_client()
    
    result = supabase.table("import_history").delete().eq("id", import_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Import record {import_id} not found")
    
    return {"deleted": True, "id": import_id}
