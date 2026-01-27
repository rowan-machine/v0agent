# src/app/meetings/transcripts.py
"""
Meeting transcript summarization module.

Handles:
- Generating structured meeting summaries from Teams transcripts
- Using GPT-4o for transcript summarization
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

from ..services import meetings_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/meetings/{meeting_id}/summarize-transcript")
async def summarize_meeting_transcript(meeting_id: str, request: Request):
    """
    Generate structured meeting summary from Teams transcript using GPT-4o.
    
    Uses the meeting notes template defined in config/templates/meeting_summary.md.
    Model: gpt-4o (configured in model_routing.yaml task_type: transcript_summarization)
    
    Body (optional):
        - transcript_text: Override transcript (otherwise uses meeting's teams_transcript)
        - focus_areas: List of areas to emphasize in extraction
    
    Returns:
        - draft_summary: Structured summary in template format
        - model_used: "gpt-4o"
        - sections: Parsed sections for programmatic access
    """
    from ..mcp.tools import draft_summary_from_transcript
    
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    transcript_text = body.get("transcript_text")
    focus_areas = body.get("focus_areas", [])
    
    # Get meeting from Supabase
    meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    if not meeting:
        return JSONResponse({"success": False, "error": "Meeting not found"}, status_code=404)
    
    meeting_name = meeting.get("meeting_name") or meeting.get("title") or "Untitled Meeting"
    
    # Use provided transcript or extract from meeting's raw_text
    if not transcript_text:
        raw_text = meeting.get("raw_text") or ""
        
        # Try to extract Teams transcript from raw_text
        if "=== Teams Transcript ===" in raw_text:
            parts = raw_text.split("=== Teams Transcript ===")
            if len(parts) > 1:
                transcript_text = parts[1].strip()
        
        # Fallback to entire raw_text if no Teams section
        if not transcript_text:
            transcript_text = raw_text
    
    if not transcript_text or len(transcript_text) < 100:
        return JSONResponse({
            "success": False, 
            "error": "No transcript available. Paste Teams transcript in Edit Meeting first."
        }, status_code=400)
    
    # Call the MCP tool which uses GPT-4o
    result = draft_summary_from_transcript({
        "transcript": transcript_text,
        "meeting_name": meeting_name,
        "focus_areas": focus_areas
    })
    
    if result.get("status") == "error":
        return JSONResponse({
            "success": False,
            "error": result.get("error", "Unknown error during summarization")
        }, status_code=500)
    
    return JSONResponse({
        "success": True,
        "meeting_id": meeting_id,
        "meeting_name": meeting_name,
        "draft_summary": result.get("draft_summary"),
        "model_used": result.get("model_used", "gpt-4o"),
        "instructions": "Review and edit this summary, then save to the Summarized Notes field."
    })
