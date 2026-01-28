# src/app/api/v1/imports/helpers.py
"""
Helper functions for import endpoints.
"""

import json
import logging
from typing import Optional

from ....infrastructure.supabase_client import get_supabase_client
from ....mcp.parser import parse_meeting_summary
from ....mcp.extract import extract_structured_signals
from ....mcp.cleaner import clean_meeting_text
from .models import MeetingDocumentResult

logger = logging.getLogger(__name__)


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
    supabase,
    filename: str,
    file_type: str,
    meeting_id: Optional[int] = None,
    status: str = "pending",
    error_message: Optional[str] = None
) -> int:
    """Record an import attempt in the import_history table."""
    result = supabase.table("import_history").insert({
        "filename": filename,
        "file_type": file_type,
        "meeting_id": meeting_id,
        "status": status,
        "error_message": error_message
    }).execute()
    return result.data[0]["id"] if result.data else None


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
    supabase,
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
    result = supabase.table("meeting_documents").insert({
        "meeting_id": meeting_id,
        "doc_type": doc_type,
        "source": source,
        "content": content,
        "format": format,
        "signals_json": json.dumps(signals) if signals else None,
        "file_path": file_path,
        "metadata_json": json.dumps(metadata) if metadata else None,
        "is_primary": 1 if is_primary else 0
    }).execute()
    
    document_id = result.data[0]["id"] if result.data else None
    
    return MeetingDocumentResult(
        document_id=document_id,
        meeting_id=meeting_id,
        doc_type=doc_type,
        source=source,
        content_length=len(content),
        signal_count=signal_count,
        is_primary=is_primary
    )
