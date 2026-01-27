# src/app/domains/signals/api/extraction.py
"""
Signal Extraction API - Extract signals from documents and transcripts.

Provides endpoints for:
- Extracting signals from documents using MeetingAnalyzerAgent
- Saving extracted signals to meetings
- Merging new signals with existing meeting signals
"""

from datetime import datetime
from typing import Dict, Any
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# SIGNAL EXTRACTION ENDPOINTS
# =============================================================================

@router.post("/extract-from-document")
async def extract_signals_from_document(request: Request):
    """Extract signals from a document (transcript) using MeetingAnalyzerAgent.
    
    Delegates to MeetingAnalyzerAgent (Checkpoint 2.4) for signal extraction.
    This is useful for finding signals that weren't captured during the initial
    meeting summarization process.
    
    Request Body:
        document_id: ID of the document to extract signals from
        meeting_id: Optional meeting ID to merge signals into
    
    Returns:
        Extracted signals with counts
    """
    from ....infrastructure.supabase_client import get_supabase_client
    from ....agents.meeting_analyzer import get_meeting_analyzer
    
    data = await request.json()
    doc_id = data.get("document_id")
    meeting_id = data.get("meeting_id")  # Optional: associate with existing meeting
    
    if not doc_id:
        return JSONResponse({"error": "document_id is required"}, status_code=400)

    supabase = get_supabase_client()
    doc_result = supabase.table("documents").select(
        "id, source, content"
    ).eq("id", doc_id).single().execute()
    doc = doc_result.data
    
    if not doc:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    
    content = doc["content"]
    source = doc["source"]
    
    # Truncate if too long
    if len(content) > 15000:
        content = content[:15000] + "\n\n[... truncated for processing ...]"
    
    try:
        # Use MeetingAnalyzerAgent for signal extraction
        agent = get_meeting_analyzer()
        
        # First, try adaptive parsing to extract sections
        parsed_sections = agent.parse_adaptive(content)
        
        # Then extract signals from sections
        signals_result = agent.extract_signals_from_sections(parsed_sections)
        
        # If parsing didn't yield many signals, use AI extraction
        if agent._should_use_ai_extraction(signals_result):
            ai_signals = await agent._extract_signals_with_ai(content, source)
            # Merge with parsed signals
            signals = agent._merge_signals(signals_result, ai_signals)
        else:
            signals = signals_result
        
        # Deduplicate
        signals = agent._deduplicate_signals(signals)
        
        # Convert to expected format
        extracted_signals = {
            "decisions": signals.get("decisions", []),
            "action_items": signals.get("action_items", []),
            "blockers": signals.get("blockers", []),
            "risks": signals.get("risks", []),
            "ideas": signals.get("ideas", []),
        }
        
        # Count extracted signals
        total_extracted = sum(
            len(extracted_signals.get(k, [])) 
            for k in ["decisions", "action_items", "blockers", "risks", "ideas"]
        )
        
        # If meeting_id provided, merge with existing signals
        if meeting_id:
            return await _merge_with_meeting(
                supabase, meeting_id, extracted_signals, total_extracted
            )
        
        return JSONResponse({
            "status": "ok",
            "action": "extracted",
            "document_id": doc_id,
            "total_signals": total_extracted,
            "signals": extracted_signals
        })
        
    except Exception as e:
        logger.exception(f"Error extracting signals from document {doc_id}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def _merge_with_meeting(
    supabase,
    meeting_id: str,
    extracted_signals: Dict[str, Any],
    total_extracted: int
) -> JSONResponse:
    """Merge extracted signals with an existing meeting's signals."""
    meeting_result = supabase.table("meetings").select(
        "signals"
    ).eq("id", meeting_id).single().execute()
    meeting = meeting_result.data

    if meeting and meeting.get("signals"):
        existing = meeting["signals"] if isinstance(meeting["signals"], dict) else json.loads(meeting["signals"])
        
        # Merge new signals (avoiding duplicates)
        for key in ["decisions", "action_items", "blockers", "risks", "ideas"]:
            existing_items = existing.get(key, [])
            new_items = extracted_signals.get(key, [])
            for item in new_items:
                if item not in existing_items:
                    existing_items.append(item)
            existing[key] = existing_items

        # Update meeting with merged signals
        supabase.table("meetings").update({
            "signals": existing
        }).eq("id", meeting_id).execute()
        
        return JSONResponse({
            "status": "ok",
            "action": "merged",
            "meeting_id": meeting_id,
            "new_signals": total_extracted,
            "signals": extracted_signals
        })
    
    return JSONResponse({
        "status": "ok",
        "action": "extracted",
        "meeting_id": meeting_id,
        "total_signals": total_extracted,
        "signals": extracted_signals
    })


@router.post("/save-from-document")
async def save_signals_from_document(request: Request):
    """Save extracted signals from a document to the meetings table.
    
    This creates a pseudo-meeting record to store signals extracted from documents,
    making them visible in the signals dashboard.
    
    Request Body:
        document_id: ID of the source document
        signals: Dictionary of signals by type
    
    Returns:
        Status with meeting ID and signal counts
    """
    from ....infrastructure.supabase_client import get_supabase_client
    
    data = await request.json()
    doc_id = data.get("document_id")
    signals = data.get("signals")
    
    if not doc_id or not signals:
        return JSONResponse(
            {"error": "document_id and signals are required"}, 
            status_code=400
        )
    
    supabase = get_supabase_client()
    
    # Get document info
    doc_result = supabase.table("documents").select(
        "id, source, content, document_date"
    ).eq("id", doc_id).single().execute()
    doc = doc_result.data

    if not doc:
        return JSONResponse({"error": "Document not found"}, status_code=404)

    # Check if signals already saved for this document
    existing_result = supabase.table("meetings").select(
        "id"
    ).eq("source_document_id", doc_id).execute()
    existing = existing_result.data[0] if existing_result.data else None

    if existing:
        # Update existing record
        supabase.table("meetings").update({
            "signals": signals,
            "updated_at": datetime.now().isoformat()
        }).eq("source_document_id", doc_id).execute()
        
        return JSONResponse({
            "status": "ok",
            "action": "updated",
            "meeting_id": existing["id"]
        })
    
    # Create new meeting record for document signals
    meeting_name = f"[Document] {doc['source']}"
    meeting_date = doc.get("document_date") or datetime.now().strftime("%Y-%m-%d")
    
    # Count total signals
    total_signals = sum(
        len(signals.get(k, [])) 
        for k in ["decisions", "action_items", "blockers", "risks", "ideas"]
    )
    
    # Generate a brief summary of the signals for synthesized_notes
    signal_summary_parts = []
    if signals.get("decisions"):
        signal_summary_parts.append(f"{len(signals['decisions'])} decisions")
    if signals.get("action_items"):
        signal_summary_parts.append(f"{len(signals['action_items'])} action items")
    if signals.get("blockers"):
        signal_summary_parts.append(f"{len(signals['blockers'])} blockers")
    if signals.get("risks"):
        signal_summary_parts.append(f"{len(signals['risks'])} risks")
    if signals.get("ideas"):
        signal_summary_parts.append(f"{len(signals['ideas'])} ideas")
    
    synthesized_notes = (
        f"Signals extracted from document: "
        f"{', '.join(signal_summary_parts) if signal_summary_parts else 'none'}"
    )
    
    insert_result = supabase.table("meetings").insert({
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "synthesized_notes": synthesized_notes,
        "signals": signals,
        "source_document_id": doc_id,
        "created_at": datetime.now().isoformat()
    }).execute()
    
    new_id = insert_result.data[0]["id"] if insert_result.data else None
    
    return JSONResponse({
        "status": "ok",
        "action": "created",
        "meeting_id": new_id,
        "total_signals": total_signals
    })
