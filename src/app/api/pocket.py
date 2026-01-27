"""
Pocket Integration API Routes

Provides endpoints for Pocket (AI meeting recorder) integration,
including listing recordings, fetching summaries/transcripts,
and webhook handling.

Routes:
- /api/integrations/pocket/recordings - List recent recordings
- /api/integrations/pocket/fetch - Fetch summary/transcript for a recording
- /api/integrations/pocket/fetch-versions - Get all available versions
- /api/integrations/pocket/webhook - Webhook endpoint for notifications
- /api/meetings/{meeting_id}/generate-document - Generate transcript document
- /api/meetings/{meeting_id}/transcript-documents - Check transcript document status
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..integrations.pocket import (
    PocketClient,
    extract_latest_summary,
    extract_transcript_text,
    extract_mind_map,
    extract_action_items,
    get_all_summary_versions,
    get_all_mind_map_versions,
)
from ..infrastructure.supabase_client import get_supabase_client
from ..services import meetings_supabase
from ..services import documents_supabase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pocket"])


# =============================================================================
# List Recordings
# =============================================================================

@router.get("/api/integrations/pocket/recordings")
async def pocket_list_recordings(
    page: int = 1,
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """List recent Pocket recordings for selection.

    Returns paginated list with id, title, created_at for UI display.
    """
    try:
        client = PocketClient()
        resp = client.list_recordings(
            page=page,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Extract recordings from response
        data = resp.get("data") or {}
        items = data if isinstance(data, list) else data.get("items") or []
        pagination = resp.get("pagination") or {}
        
        # Build clean list for UI
        recordings = []
        for item in items:
            rec_id = item.get("id") or item.get("recording_id")
            title = item.get("title") or "(untitled)"
            created = item.get("created_at") or item.get("recording_at") or "unknown"
            if rec_id:
                recordings.append({
                    "id": rec_id,
                    "title": title,
                    "created_at": created,
                })
        
        return JSONResponse({
            "success": True,
            "recordings": recordings,
            "pagination": {
                "page": pagination.get("page", 1),
                "total_pages": pagination.get("total_pages", 1),
                "has_more": pagination.get("has_more", False),
            },
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)


# =============================================================================
# Fetch Recording Details
# =============================================================================

@router.post("/api/integrations/pocket/fetch")
async def pocket_fetch(request: Request):
    """Fetch Pocket summary, transcript, mind map, and action items for a given recording.

    Accepts JSON or form with `recording_id` and optional version selectors:
    - `summary_key`: specific summary version to fetch (e.g., 'v2_summary', 'v1_summary')
    - `mind_map_key`: specific mind map version to fetch (e.g., 'v2_mind_map')
    
    Returns `summary_text`, `transcript_text`, `mind_map_text`, and `action_items` if available.
    """
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)

    recording_id = (body.get("recording_id") or "").strip()
    if not recording_id:
        return JSONResponse({"success": False, "error": "recording_id required"}, status_code=400)

    summary_key = (body.get("summary_key") or "").strip() or None
    mind_map_key = (body.get("mind_map_key") or "").strip() or None

    try:
        client = PocketClient()
        details = client.get_recording(recording_id, include_transcript=True, include_summarizations=True)
        
        # If specific versions requested, fetch those; otherwise fetch latest
        if summary_key or mind_map_key:
            # Fetch specific versions
            payload = details.get("data", {})
            rec = payload if isinstance(payload, dict) else {}
            summ_dict = rec.get("summarizations", {}) if isinstance(rec.get("summarizations"), dict) else {}
            
            # Get selected summary
            summary_text = None
            if summary_key and summary_key in summ_dict:
                summ_obj = summ_dict[summary_key]
                if isinstance(summ_obj, dict):
                    summary_text = summ_obj.get("markdown") or summ_obj.get("text") or summ_obj.get("content")
            
            # Get selected mind map
            mind_map_text = None
            if mind_map_key and mind_map_key in summ_dict:
                mm_obj = summ_dict[mind_map_key]
                if isinstance(mm_obj, dict):
                    # Format the mind map nodes
                    nodes = mm_obj.get("nodes", [])
                    if isinstance(nodes, list):
                        lines = []
                        for node in nodes:
                            if isinstance(node, dict):
                                title = (node.get("title") or "").strip()
                                if title:
                                    node_id = node.get("node_id", "")
                                    parent_id = node.get("parent_node_id", "")
                                    indent = "  " if node_id != parent_id else ""
                                    lines.append(f"{indent}• {title}")
                        if lines:
                            mind_map_text = "\n".join(lines)
                    elif "markdown" in mm_obj:
                        mind_map_text = mm_obj.get("markdown")
        else:
            # Fetch latest versions (original behavior)
            summary_text, _summary_obj = extract_latest_summary(details)
            mind_map_text = extract_mind_map(details)
        
        transcript_text = extract_transcript_text(details)
        action_items = extract_action_items(details)

        return JSONResponse({
            "success": True,
            "recording_id": recording_id,
            "summary_text": summary_text,
            "transcript_text": transcript_text,
            "mind_map_text": mind_map_text,
            "action_items": action_items,
        })
    except Exception as e:
        # Surface any API or parsing error
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)


# =============================================================================
# Fetch All Versions
# =============================================================================

@router.post("/api/integrations/pocket/fetch-versions")
async def pocket_fetch_versions(request: Request):
    """Fetch all available summary and mind map versions for a recording.
    
    Returns lists of available versions so user can choose which to use.
    Accepts JSON or form with `recording_id`.
    """
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)

    recording_id = (body.get("recording_id") or "").strip()
    if not recording_id:
        return JSONResponse({"success": False, "error": "recording_id required"}, status_code=400)

    try:
        client = PocketClient()
        details = client.get_recording(recording_id, include_transcript=True, include_summarizations=True)
        
        # Extract all available versions
        summary_versions = get_all_summary_versions(details)
        mind_map_versions = get_all_mind_map_versions(details)
        
        # Also get transcript and action items
        transcript_text = extract_transcript_text(details)
        action_items = extract_action_items(details)

        return JSONResponse({
            "success": True,
            "recording_id": recording_id,
            "summary_versions": summary_versions,
            "mind_map_versions": mind_map_versions,
            "transcript_text": transcript_text,
            "action_items": action_items,
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)


# =============================================================================
# Webhook Endpoint
# =============================================================================

@router.post("/api/integrations/pocket/webhook")
async def pocket_webhook(request: Request):
    """Webhook endpoint for Pocket to notify of new/updated recordings.

    Body should include a `recording_id`. We fetch details immediately and return 200.
    """
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)

    recording_id = (body.get("recording_id") or "").strip()
    if not recording_id:
        return JSONResponse({"success": False, "error": "recording_id required"}, status_code=400)

    try:
        client = PocketClient()
        details = client.get_recording(recording_id, include_transcript=True, include_summarizations=True)
        summary_text, _summary_obj = extract_latest_summary(details)
        transcript_text = extract_transcript_text(details)

        # TODO: persist to DB and link to meeting if mapping exists
        return JSONResponse({
            "success": True,
            "recording_id": recording_id,
            "summary_text": summary_text,
            "transcript_text": transcript_text,
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)


# =============================================================================
# Transcript Document Generation
# =============================================================================

@router.post("/api/meetings/{meeting_id}/generate-document")
async def generate_transcript_document(meeting_id: str, request: Request):
    """
    Generate a transcript document from a meeting's raw_text field.
    
    Body:
        - transcript_type: "pocket" or "teams"
    
    Creates a document in Supabase linked to the meeting.
    Returns error if document already exists for that transcript type.
    """
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)
    
    transcript_type = (body.get("transcript_type") or "").strip().lower()
    if transcript_type not in ("pocket", "teams"):
        return JSONResponse({"success": False, "error": "transcript_type must be 'pocket' or 'teams'"}, status_code=400)
    
    # Get the meeting from Supabase
    meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    if not meeting:
        return JSONResponse({"success": False, "error": "Meeting not found"}, status_code=404)
    
    meeting_name = meeting.get("meeting_name") or meeting.get("title") or "Untitled"
    meeting_date = meeting.get("meeting_date")
    raw_text = meeting.get("raw_text") or ""
    
    # Check if document already exists
    client = get_supabase_client()
    if client:
        # Check for existing document of this type
        source_pattern = f"{'Pocket' if transcript_type == 'pocket' else 'Teams'} Transcript:%"
        existing = client.table("documents").select("id").eq("meeting_id", meeting_id).ilike("source", source_pattern).execute()
        if existing.data:
            return JSONResponse({
                "success": False, 
                "error": f"{transcript_type.title()} transcript document already exists",
                "document_id": existing.data[0]["id"]
            }, status_code=409)
    
    # Parse the transcript from raw_text
    pocket_transcript = ""
    teams_transcript = ""
    
    if "=== Pocket Transcript ===" in raw_text:
        parts = raw_text.split("=== Pocket Transcript ===")
        if len(parts) > 1:
            pocket_part = parts[1]
            if "=== Teams Transcript ===" in pocket_part:
                pocket_transcript = pocket_part.split("=== Teams Transcript ===")[0].strip()
            else:
                pocket_transcript = pocket_part.strip()
    
    if "=== Teams Transcript ===" in raw_text:
        parts = raw_text.split("=== Teams Transcript ===")
        if len(parts) > 1:
            teams_transcript = parts[1].strip()
    
    # If no section markers, use entire raw_text as teams transcript
    if raw_text and not pocket_transcript and not teams_transcript and "===" not in raw_text:
        teams_transcript = raw_text
    
    # Get the right transcript
    transcript_content = pocket_transcript if transcript_type == "pocket" else teams_transcript
    
    if not transcript_content:
        return JSONResponse({
            "success": False, 
            "error": f"No {transcript_type.title()} transcript content found in meeting"
        }, status_code=404)
    
    # Create the document
    source_name = f"{'Pocket' if transcript_type == 'pocket' else 'Teams'} Transcript: {meeting_name}"
    doc_data = {
        "meeting_id": meeting_id,
        "source": source_name,
        "content": transcript_content,
        "document_date": meeting_date,
    }
    
    created_doc = documents_supabase.create_document(doc_data)
    if not created_doc:
        return JSONResponse({"success": False, "error": "Failed to create document"}, status_code=500)
    
    logger.info(f"Created {transcript_type} transcript document {created_doc['id']} for meeting {meeting_id}")
    
    return JSONResponse({
        "success": True,
        "document_id": created_doc["id"],
        "source": source_name,
        "content_length": len(transcript_content),
    })


@router.get("/api/meetings/{meeting_id}/transcript-documents")
async def get_transcript_documents(meeting_id: str):
    """
    Check which transcript documents exist for a meeting.
    
    Returns status of pocket and teams transcript documents.
    """
    client = get_supabase_client()
    
    result = {
        "pocket": {"exists": False, "document_id": None},
        "teams": {"exists": False, "document_id": None},
    }
    
    if client:
        # Check for Pocket transcript
        pocket_docs = client.table("documents").select("id").eq("meeting_id", meeting_id).ilike("source", "Pocket Transcript:%").execute()
        if pocket_docs.data:
            result["pocket"] = {"exists": True, "document_id": pocket_docs.data[0]["id"]}
        
        # Check for Teams transcript
        teams_docs = client.table("documents").select("id").eq("meeting_id", meeting_id).ilike("source", "Teams Transcript:%").execute()
        if teams_docs.data:
            result["teams"] = {"exists": True, "document_id": teams_docs.data[0]["id"]}
        
        # Also check for generic "Transcript:" (legacy format)
        if not result["teams"]["exists"]:
            legacy_docs = client.table("documents").select("id").eq("meeting_id", meeting_id).ilike("source", "Transcript:%").execute()
            if legacy_docs.data:
                result["teams"] = {"exists": True, "document_id": legacy_docs.data[0]["id"]}
    
    return JSONResponse({"success": True, "meeting_id": meeting_id, **result})
