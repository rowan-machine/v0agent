# src/app/api/v1/imports.py
"""
API v1 - File Import endpoints.

F1: Pocket App Import Pipeline
Supports importing meeting transcripts from file uploads.
Initial implementation: Markdown files only (simplest, no external dependencies).

Future: PDF, DOCX, TXT support can be added.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
import logging

from ...db import connect
from ...mcp.parser import parse_meeting_summary
from ...mcp.extract import extract_structured_signals
from ...mcp.cleaner import clean_meeting_text

router = APIRouter()
logger = logging.getLogger(__name__)


# ============== Pydantic Models ==============

class ImportResult(BaseModel):
    """Result of a successful file import."""
    meeting_id: int
    meeting_name: str
    transcript_length: int
    signal_count: int
    import_source: str
    warnings: list[str] = []


class ImportHistoryItem(BaseModel):
    """Import history record."""
    id: int
    filename: str
    file_type: str
    meeting_id: Optional[int]
    status: str
    error_message: Optional[str]
    created_at: str


# ============== Helper Functions ==============

def extract_markdown_text(content: bytes) -> str:
    """
    Extract plain text from markdown file content.
    
    Args:
        content: Raw bytes from uploaded file
        
    Returns:
        Decoded text content (markdown is already text)
        
    Raises:
        ValueError: If content cannot be decoded as UTF-8
    """
    try:
        text = content.decode('utf-8')
        return text.strip()
    except UnicodeDecodeError:
        # Try with latin-1 as fallback
        try:
            text = content.decode('latin-1')
            return text.strip()
        except:
            raise ValueError("Could not decode file as text. Ensure it's a valid text/markdown file.")


def infer_meeting_name_from_content(text: str, filename: str) -> str:
    """
    Try to infer a meeting name from the content or filename.
    
    Checks for:
    1. First H1 header (# Title)
    2. First line if it looks like a title
    3. Filename without extension
    """
    lines = text.split('\n')
    
    # Look for H1 header
    for line in lines[:10]:  # Check first 10 lines
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()[:100]  # Remove # and limit length
    
    # Check if first non-empty line looks like a title (short, no punctuation at end)
    for line in lines[:5]:
        line = line.strip()
        if line and len(line) < 80 and not line.endswith(('.', '?', '!')):
            if not line.startswith(('#', '-', '*', '>')):  # Not a markdown element
                return line[:100]
    
    # Fall back to filename
    name = filename.rsplit('.', 1)[0]  # Remove extension
    name = name.replace('_', ' ').replace('-', ' ')  # Clean up
    return name[:100]


def record_import_history(
    conn,
    filename: str,
    file_type: str,
    meeting_id: Optional[int] = None,
    status: str = "pending",
    error_message: Optional[str] = None
) -> int:
    """Record an import attempt in the import_history table."""
    cursor = conn.execute("""
        INSERT INTO import_history (filename, file_type, meeting_id, status, error_message)
        VALUES (?, ?, ?, ?, ?)
    """, (filename, file_type, meeting_id, status, error_message))
    return cursor.lastrowid


# ============== API Endpoints ==============

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
        with connect() as conn:
            # Record import attempt
            import_id = record_import_history(conn, filename, file_ext, status="processing")
            
            # Insert meeting
            cursor = conn.execute("""
                INSERT INTO meeting_summaries 
                (meeting_name, synthesized_notes, meeting_date, raw_text, import_source, source_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (meeting_name, text, meeting_date, text, 'markdown_upload', source_url))
            
            meeting_id = cursor.lastrowid
            
            # Extract signals using the proper pipeline: clean -> parse -> extract
            try:
                cleaned_text = clean_meeting_text(text)
                parsed_sections = parse_meeting_summary(cleaned_text)
                signals = extract_structured_signals(parsed_sections)
                signal_count = sum(len(v) for v in signals.values() if isinstance(v, list))
                
                # Store signals as JSON
                conn.execute("""
                    UPDATE meeting_summaries SET signals_json = ? WHERE id = ?
                """, (json.dumps(signals), meeting_id))
            except Exception as e:
                logger.warning(f"Signal extraction failed for import: {e}")
                signals = {}
                signal_count = 0
                warnings.append(f"Signal extraction failed: {str(e)}")
            
            # Update import history with success
            conn.execute("""
                UPDATE import_history SET status = 'completed', meeting_id = ? WHERE id = ?
            """, (meeting_id, import_id))
            
            conn.commit()
            
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
            with connect() as conn:
                conn.execute("""
                    UPDATE import_history SET status = 'failed', error_message = ? 
                    WHERE filename = ? AND status = 'processing'
                """, (str(e), filename))
                conn.commit()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/history", response_model=list[ImportHistoryItem])
async def get_import_history(
    limit: int = 50,
    status: Optional[str] = None
):
    """
    Get import history.
    
    **Query parameters:**
    - limit: Maximum number of records to return (default 50)
    - status: Filter by status ('completed', 'failed', 'processing')
    """
    with connect() as conn:
        query = "SELECT * FROM import_history"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, tuple(params)).fetchall()
    
    return [
        ImportHistoryItem(
            id=row['id'],
            filename=row['filename'],
            file_type=row['file_type'],
            meeting_id=row['meeting_id'],
            status=row['status'],
            error_message=row['error_message'],
            created_at=row['created_at']
        )
        for row in rows
    ]


@router.delete("/history/{import_id}")
async def delete_import_record(import_id: int):
    """
    Delete an import history record.
    
    Note: This does NOT delete the associated meeting.
    """
    with connect() as conn:
        result = conn.execute("DELETE FROM import_history WHERE id = ?", (import_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Import record not found")
        conn.commit()
    
    return {"message": "Import record deleted", "id": import_id}


# ============== F1b: Pocket Bundle Amend ==============

class MeetingDocumentResult(BaseModel):
    """Result of adding a document to a meeting."""
    document_id: int
    meeting_id: int
    doc_type: str
    source: str
    content_length: int
    signal_count: int
    is_primary: bool


class AmendMeetingResult(BaseModel):
    """Result of amending a meeting with Pocket bundle."""
    meeting_id: int
    meeting_name: str
    documents_added: list[MeetingDocumentResult]
    total_signals_extracted: int
    holistic_signals_merged: int
    warnings: list[str] = []


class MeetingDocumentInfo(BaseModel):
    """Info about a meeting document."""
    id: int
    doc_type: str
    source: str
    content_length: int
    format: Optional[str]
    is_primary: bool
    created_at: str


def extract_signals_from_content(content: str) -> tuple[dict, int]:
    """
    Extract signals from content using the standard pipeline.
    
    Returns:
        Tuple of (signals_dict, signal_count)
    """
    try:
        cleaned_text = clean_meeting_text(content)
        parsed_sections = parse_meeting_summary(cleaned_text)
        signals = extract_structured_signals(parsed_sections)
        signal_count = sum(len(v) for v in signals.values() if isinstance(v, list))
        return signals, signal_count
    except Exception as e:
        logger.warning(f"Signal extraction failed: {e}")
        return {}, 0


def merge_signals_holistically(existing_signals: dict, new_signals: dict) -> tuple[dict, int]:
    """
    Merge signals from multiple sources holistically (no duplicates).
    
    Deduplicates based on normalized signal text similarity.
    
    Returns:
        Tuple of (merged_signals, count_of_merged_items)
    """
    merged = {}
    merged_count = 0
    
    signal_types = ['decisions', 'action_items', 'blockers', 'risks', 'ideas', 'key_points']
    
    for sig_type in signal_types:
        existing_items = existing_signals.get(sig_type, [])
        new_items = new_signals.get(sig_type, [])
        
        if not existing_items and not new_items:
            continue
        
        # Normalize existing items for comparison
        existing_normalized = set()
        merged_items = []
        
        for item in existing_items:
            text = item.get('text', item) if isinstance(item, dict) else str(item)
            normalized = text.lower().strip()[:100]  # First 100 chars normalized
            existing_normalized.add(normalized)
            merged_items.append(item)
        
        # Add non-duplicate new items
        for item in new_items:
            text = item.get('text', item) if isinstance(item, dict) else str(item)
            normalized = text.lower().strip()[:100]
            
            if normalized not in existing_normalized:
                merged_items.append(item)
                existing_normalized.add(normalized)
                merged_count += 1
        
        if merged_items:
            merged[sig_type] = merged_items
    
    return merged, merged_count


def add_document_to_meeting(
    conn,
    meeting_id: int,
    doc_type: str,
    source: str,
    content: str,
    format: str = 'markdown',
    is_primary: bool = False,
    file_path: Optional[str] = None,
    metadata: Optional[dict] = None
) -> MeetingDocumentResult:
    """
    Add a document (transcript or summary) to a meeting.
    
    Extracts signals from the document and stores them.
    """
    # Extract signals from this document
    signals, signal_count = extract_signals_from_content(content)
    
    # Insert document
    cursor = conn.execute("""
        INSERT INTO meeting_documents 
        (meeting_id, doc_type, source, content, format, signals_json, file_path, metadata_json, is_primary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        meeting_id,
        doc_type,
        source,
        content,
        format,
        json.dumps(signals) if signals else None,
        file_path,
        json.dumps(metadata) if metadata else None,
        1 if is_primary else 0
    ))
    
    document_id = cursor.lastrowid
    
    return MeetingDocumentResult(
        document_id=document_id,
        meeting_id=meeting_id,
        doc_type=doc_type,
        source=source,
        content_length=len(content),
        signal_count=signal_count,
        is_primary=is_primary
    )


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
    with connect() as conn:
        meeting = conn.execute(
            "SELECT id, meeting_name, signals_json FROM meeting_summaries WHERE id = ?",
            (meeting_id,)
        ).fetchone()
        
        if not meeting:
            raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
        
        meeting_name = meeting['meeting_name']
        existing_signals = json.loads(meeting['signals_json'] or '{}')
        
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
        existing_docs = conn.execute(
            "SELECT doc_type FROM meeting_documents WHERE meeting_id = ? AND source = ?",
            (meeting_id, source)
        ).fetchall()
        existing_types = {row['doc_type'] for row in existing_docs}
        
        # Add transcript if provided
        if transcript_content:
            is_primary = 'transcript' not in existing_types
            doc_result = add_document_to_meeting(
                conn, meeting_id, 'transcript', source, transcript_content,
                format=transcript_format, is_primary=is_primary
            )
            documents_added.append(doc_result)
            
            # Also update raw_text if this is primary
            if is_primary:
                conn.execute(
                    "UPDATE meeting_summaries SET raw_text = ? WHERE id = ?",
                    (transcript_content, meeting_id)
                )
        
        # Add summary if provided
        if summary_content:
            is_primary = 'summary' not in existing_types
            doc_result = add_document_to_meeting(
                conn, meeting_id, 'summary', source, summary_content,
                format=summary_format, is_primary=is_primary
            )
            documents_added.append(doc_result)
        
        # Merge signals holistically from all summaries
        all_summary_signals = [existing_signals]
        for doc in documents_added:
            if doc.doc_type == 'summary' and doc.signal_count > 0:
                # Get the signals we just extracted
                doc_row = conn.execute(
                    "SELECT signals_json FROM meeting_documents WHERE id = ?",
                    (doc.document_id,)
                ).fetchone()
                if doc_row and doc_row['signals_json']:
                    all_summary_signals.append(json.loads(doc_row['signals_json']))
        
        # Merge all signals
        merged_signals = existing_signals
        total_merged = 0
        for new_signals in all_summary_signals[1:]:
            merged_signals, merged_count = merge_signals_holistically(merged_signals, new_signals)
            total_merged += merged_count
        
        # Update meeting with merged signals
        total_signal_count = sum(len(v) for v in merged_signals.values() if isinstance(v, list))
        conn.execute(
            "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
            (json.dumps(merged_signals), meeting_id)
        )
        
        conn.commit()
        
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
    with connect() as conn:
        meeting = conn.execute(
            "SELECT id FROM meeting_summaries WHERE id = ?",
            (meeting_id,)
        ).fetchone()
        
        if not meeting:
            raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
        
        rows = conn.execute("""
            SELECT id, doc_type, source, LENGTH(content) as content_length, 
                   format, is_primary, created_at
            FROM meeting_documents
            WHERE meeting_id = ?
            ORDER BY created_at
        """, (meeting_id,)).fetchall()
    
    return [
        MeetingDocumentInfo(
            id=row['id'],
            doc_type=row['doc_type'],
            source=row['source'],
            content_length=row['content_length'],
            format=row['format'],
            is_primary=bool(row['is_primary']),
            created_at=row['created_at']
        )
        for row in rows
    ]


@router.get("/meetings/{meeting_id}/documents/{doc_id}")
async def get_meeting_document(meeting_id: int, doc_id: int):
    """
    Get a specific document's full content.
    """
    with connect() as conn:
        row = conn.execute("""
            SELECT * FROM meeting_documents
            WHERE id = ? AND meeting_id = ?
        """, (doc_id, meeting_id)).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": row['id'],
        "meeting_id": row['meeting_id'],
        "doc_type": row['doc_type'],
        "source": row['source'],
        "content": row['content'],
        "format": row['format'],
        "signals_json": json.loads(row['signals_json']) if row['signals_json'] else None,
        "is_primary": bool(row['is_primary']),
        "created_at": row['created_at']
    }
