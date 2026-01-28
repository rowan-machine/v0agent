# src/app/api/v1/imports/amend.py
"""
API v1 - Amend meetings with additional documents.

Supports adding transcripts and summaries from various sources (Pocket, Teams, Zoom).
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import json
import logging

from ....infrastructure.supabase_client import get_supabase_client
from .models import MeetingDocumentResult, AmendMeetingResult, MeetingDocumentInfo
from .helpers import (
    extract_markdown_text,
    add_document_to_meeting,
    merge_signals_holistically,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Supported file extensions for transcript/summary uploads
ALLOWED_EXTENSIONS = {'md', 'markdown', 'txt', 'text'}


@router.post("/amend/{meeting_id}")
async def amend_meeting_with_pocket(
    meeting_id: int,
    transcript: Optional[str] = Form(None),
    transcript_file: Optional[UploadFile] = File(None),
    summary: Optional[str] = Form(None),
    summary_file: Optional[UploadFile] = File(None),
    source: str = Form("pocket")
):
    """
    F1b: Amend an existing meeting with Pocket transcript and/or summary.
    
    This endpoint supports the workflow where you:
    1. Create a meeting during the call (with notes and screenshots)
    2. Later add Teams transcript + summary
    3. Finally add Pocket transcript + summary from your phone
    
    Documents are linked to the meeting and signals are merged holistically
    (no duplicates across Teams and Pocket summaries).
    
    **Parameters:**
    - meeting_id: ID of the existing meeting to amend
    - transcript: Plain text transcript (copy-paste)
    - transcript_file: Uploaded transcript file (md, txt)
    - summary: Plain text summary (copy-paste)
    - summary_file: Uploaded summary file (md, txt, pdf, docx)
    - source: Source identifier ('pocket', 'teams', 'zoom', etc.)
    
    At least one of transcript or summary (text or file) must be provided.
    """
    warnings = []
    documents_added = []
    
    # Verify meeting exists
    supabase = get_supabase_client()
    
    meeting_result = supabase.table("meetings").select(
        "id, meeting_name, signals"
    ).eq("id", meeting_id).execute()

    if not meeting_result.data:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    meeting = meeting_result.data[0]
    meeting_name = meeting['meeting_name']
    existing_signals = meeting['signals'] or {}
    if isinstance(existing_signals, str):
        existing_signals = json.loads(existing_signals)
    
    # Process transcript (text or file)
    transcript_content = None
    transcript_format = 'txt'
    
    if transcript_file:
        # Read transcript file
        file_ext = transcript_file.filename.split('.')[-1].lower() if '.' in transcript_file.filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            warnings.append(f"Transcript file type .{file_ext} not supported, skipping")
        else:
            content_bytes = await transcript_file.read()
            try:
                transcript_content = extract_markdown_text(content_bytes)
                transcript_format = file_ext or 'txt'
            except ValueError as e:
                warnings.append(f"Could not read transcript file: {e}")
    elif transcript:
        transcript_content = transcript.strip()
    
    # Process summary (text or file)
    summary_content = None
    summary_format = 'txt'
    
    if summary_file:
        file_ext = summary_file.filename.split('.')[-1].lower() if '.' in summary_file.filename else ''
        
        # For F1b, we support more formats for summaries
        summary_allowed = {'md', 'markdown', 'txt', 'text'}  # PDF/DOCX support deferred
        
        if file_ext not in summary_allowed:
            if file_ext in {'pdf', 'docx'}:
                warnings.append(f"PDF/DOCX summary support coming soon, skipping .{file_ext} file")
            else:
                warnings.append(f"Summary file type .{file_ext} not supported, skipping")
        else:
            content_bytes = await summary_file.read()
            try:
                summary_content = extract_markdown_text(content_bytes)
                summary_format = file_ext or 'txt'
            except ValueError as e:
                warnings.append(f"Could not read summary file: {e}")
    elif summary:
        summary_content = summary.strip()
    
    # Require at least one document
    if not transcript_content and not summary_content:
        raise HTTPException(
            status_code=400,
            detail="At least one of transcript or summary (text or file) must be provided"
        )
    
    # Check if this is the first document from this source
    existing_docs = supabase.table("meeting_documents").select("doc_type").eq(
        "meeting_id", meeting_id
    ).eq("source", source).execute()
    existing_types = {row['doc_type'] for row in (existing_docs.data or [])}
    
    # Add transcript if provided
    if transcript_content:
        is_primary = 'transcript' not in existing_types
        doc_result = add_document_to_meeting(
            supabase, meeting_id, 'transcript', source, transcript_content,
            format=transcript_format, is_primary=is_primary
        )
        documents_added.append(doc_result)
        
        # Also update raw_text if this is primary
        if is_primary:
            supabase.table("meetings").update({
                "raw_text": transcript_content
            }).eq("id", meeting_id).execute()
    
    # Add summary if provided
    if summary_content:
        is_primary = 'summary' not in existing_types
        doc_result = add_document_to_meeting(
            supabase, meeting_id, 'summary', source, summary_content,
            format=summary_format, is_primary=is_primary
        )
        documents_added.append(doc_result)
    
    # Merge signals holistically from all summaries
    all_summary_signals = [existing_signals]
    for doc in documents_added:
        if doc.doc_type == 'summary' and doc.signal_count > 0:
            # Get the signals we just extracted
            doc_row = supabase.table("meeting_documents").select("signals_json").eq(
                "id", doc.document_id
            ).execute()
            if doc_row.data and doc_row.data[0].get('signals_json'):
                all_summary_signals.append(json.loads(doc_row.data[0]['signals_json']))
    
    # Merge all signals
    merged_signals = existing_signals
    total_merged = 0
    for new_signals in all_summary_signals[1:]:
        merged_signals, merged_count = merge_signals_holistically(merged_signals, new_signals)
        total_merged += merged_count
    
    # Update meeting with merged signals
    total_signal_count = sum(len(v) for v in merged_signals.values() if isinstance(v, list))
    supabase.table("meetings").update({
        "signals": merged_signals
    }).eq("id", meeting_id).execute()
    
    logger.info(f"Amended meeting '{meeting_name}' (id={meeting_id}) with {len(documents_added)} documents from {source}")
    
    return AmendMeetingResult(
        meeting_id=meeting_id,
        meeting_name=meeting_name,
        documents_added=documents_added,
        total_signals_extracted=total_signal_count,
        holistic_signals_merged=total_merged,
        warnings=warnings
    )


@router.get("/meetings/{meeting_id}/documents")
async def list_meeting_documents(meeting_id: int):
    """
    List all documents (transcripts and summaries) linked to a meeting.
    """
    supabase = get_supabase_client()
    
    meeting = supabase.table("meetings").select("id").eq("id", meeting_id).execute()
    
    if not meeting.data:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    
    rows = supabase.table("meeting_documents").select(
        "id, doc_type, source, content, format, is_primary, created_at"
    ).eq("meeting_id", meeting_id).order("created_at").execute()
    
    return [
        MeetingDocumentInfo(
            id=row['id'],
            doc_type=row['doc_type'],
            source=row['source'],
            content_length=len(row.get('content') or ''),
            format=row.get('format'),
            is_primary=bool(row['is_primary']),
            created_at=row['created_at']
        )
        for row in (rows.data or [])
    ]


@router.get("/meetings/{meeting_id}/documents/{doc_id}")
async def get_meeting_document(meeting_id: int, doc_id: int):
    """
    Get a specific document's full content.
    """
    supabase = get_supabase_client()
    
    result = supabase.table("meeting_documents").select("*").eq(
        "id", doc_id
    ).eq("meeting_id", meeting_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    
    row = result.data[0]
    return {
        "id": row['id'],
        "meeting_id": row['meeting_id'],
        "doc_type": row['doc_type'],
        "source": row['source'],
        "content": row['content'],
        "format": row['format'],
        "signals_json": json.loads(row['signals_json']) if row.get('signals_json') else None,
        "is_primary": bool(row['is_primary']),
        "created_at": row['created_at']
    }
