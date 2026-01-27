# src/app/domains/meetings/api/transcripts.py
"""
Meeting Transcripts API Routes

Transcript upload, processing, and retrieval.
"""

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging

from ....repositories import get_meeting_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcripts")


@router.get("/{meeting_id}")
async def get_transcript(meeting_id: str):
    """Get the transcript for a meeting."""
    repo = get_meeting_repository()
    
    meeting = repo.get(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    meeting_dict = meeting if isinstance(meeting, dict) else meeting.__dict__
    transcript = meeting_dict.get("transcript_text")
    
    if not transcript:
        return JSONResponse({
            "status": "ok",
            "meeting_id": meeting_id,
            "transcript": None,
            "message": "No transcript available"
        })
    
    return JSONResponse({
        "status": "ok",
        "meeting_id": meeting_id,
        "transcript": transcript,
        "word_count": len(transcript.split()) if transcript else 0
    })


@router.post("/{meeting_id}")
async def upload_transcript(meeting_id: str, request: Request):
    """Upload or update transcript text for a meeting."""
    data = await request.json()
    transcript_text = data.get("transcript_text")
    
    if not transcript_text:
        return JSONResponse({"error": "transcript_text is required"}, status_code=400)
    
    repo = get_meeting_repository()
    
    meeting = repo.get(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    updated = repo.update(meeting_id, {"transcript_text": transcript_text})
    
    if not updated:
        return JSONResponse({"error": "Failed to update transcript"}, status_code=500)
    
    return JSONResponse({
        "status": "ok",
        "meeting_id": meeting_id,
        "message": "Transcript uploaded",
        "word_count": len(transcript_text.split())
    })


@router.post("/{meeting_id}/process")
async def process_transcript(meeting_id: str):
    """Process a transcript to generate synthesized notes."""
    from ....llm import ask as ask_llm
    
    repo = get_meeting_repository()
    
    meeting = repo.get(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    meeting_dict = meeting if isinstance(meeting, dict) else meeting.__dict__
    transcript = meeting_dict.get("transcript_text")
    
    if not transcript:
        return JSONResponse({"error": "No transcript to process"}, status_code=400)
    
    # Generate synthesized notes from transcript
    prompt = f"""Analyze this meeting transcript and create structured notes:

{transcript[:8000]}  # Limit for token constraints

Include:
1. Key decisions made
2. Action items with owners
3. Important discussion points
4. Blockers or risks mentioned
5. Next steps

Format as clear, concise bullet points."""

    try:
        synthesized = ask_llm(prompt, model="gpt-4o-mini")
        
        # Update meeting with synthesized notes
        repo.update(meeting_id, {"synthesized_notes": synthesized})
        
        return JSONResponse({
            "status": "ok",
            "meeting_id": meeting_id,
            "synthesized_notes": synthesized
        })
    except Exception as e:
        logger.error(f"Failed to process transcript: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/{meeting_id}")
async def delete_transcript(meeting_id: str):
    """Remove transcript from a meeting."""
    repo = get_meeting_repository()
    
    meeting = repo.get(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    updated = repo.update(meeting_id, {"transcript_text": None})
    
    return JSONResponse({
        "status": "ok",
        "meeting_id": meeting_id,
        "message": "Transcript removed"
    })
