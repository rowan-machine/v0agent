# src/app/domains/dashboard/api/context.py
"""
Dashboard Context API

Drill-down context for highlight items.
"""

import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/highlight-context")
async def get_highlight_context(request: Request):
    """Get drill-down context for a highlight item."""
    from ....services.meeting_service import meeting_service
    
    data = await request.json()
    source = data.get("source", "")
    text = data.get("text", "")
    meeting_id = data.get("meeting_id")
    
    # Find the meeting from Supabase
    meeting = None
    if meeting_id:
        meeting = meeting_service.get_meeting_by_id(meeting_id)
    
    # If not found by id, search by name (less common case)
    if not meeting and source:
        all_meetings = meeting_service.get_all_meetings(limit=50)
        for m in all_meetings:
            if m.get("meeting_name") == source:
                meeting = m
                break
    
    if not meeting:
        return JSONResponse({
            "summary": "Meeting not found.",
            "context": None,
            "transcript": None,
            "meeting_link": None
        })
    
    # Build progressive context levels
    summary = None
    context = None
    transcript = None
    
    # Level 1: AI-generated summary of the issue
    if meeting.get("synthesized_notes"):
        # Find relevant section in notes
        notes = meeting["synthesized_notes"]
        # Try to find the specific text in notes
        text_lower = text.lower()
        lines = notes.split('\n')
        relevant_lines = []
        for i, line in enumerate(lines):
            if text_lower[:30] in line.lower() or any(word in line.lower() for word in text_lower.split()[:3]):
                # Get surrounding context
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                relevant_lines = lines[start:end]
                break
        
        if relevant_lines:
            summary = '\n'.join(relevant_lines)
        else:
            summary = notes[:500] + ('...' if len(notes) > 500 else '')
    
    # Level 2: Full context from signals
    if meeting.get("signals_json"):
        try:
            signals = meeting["signals_json"]
            if isinstance(signals, str):
                signals = json.loads(signals)
            context_parts = []
            for stype in ["blockers", "decisions", "action_items", "risks", "ideas"]:
                items = signals.get(stype, [])
                if items:
                    context_parts.append(f"**{stype.replace('_', ' ').title()}:**\n" + '\n'.join(f"• {item}" for item in items))
            context = '\n\n'.join(context_parts) if context_parts else None
        except Exception:
            pass
    
    # Level 3: Transcript excerpt
    if meeting.get("raw_text"):
        raw = meeting["raw_text"]
        # Try to find the text in the transcript
        text_lower = text.lower()
        if text_lower[:30] in raw.lower():
            # Find position and get surrounding context
            idx = raw.lower().find(text_lower[:30])
            start = max(0, idx - 200)
            end = min(len(raw), idx + 500)
            transcript = ('...' if start > 0 else '') + raw[start:end] + ('...' if end < len(raw) else '')
        else:
            # Just show first 500 chars of transcript
            transcript = raw[:500] + ('...' if len(raw) > 500 else '')
    
    return JSONResponse({
        "summary": summary,
        "context": context,
        "transcript": transcript,
        "meeting_link": f"/meetings/{meeting['id']}" if meeting else None
    })


__all__ = ["router"]
