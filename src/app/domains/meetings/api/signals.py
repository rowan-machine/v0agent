# src/app/domains/meetings/api/signals.py
"""
Meeting Signals API Routes

Signal extraction and management for meetings.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_meeting_repository, get_signal_repository
from ..constants import SIGNAL_TYPES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals")


@router.get("/{meeting_id}")
async def get_meeting_signals(meeting_id: str):
    """Get extracted signals for a meeting."""
    meeting_repo = get_meeting_repository()
    
    meeting = meeting_repo.get(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    meeting_dict = meeting if isinstance(meeting, dict) else meeting.__dict__
    signals = meeting_dict.get("signals_json") or []
    
    # Group by type
    grouped = {st: [] for st in SIGNAL_TYPES}
    for signal in signals:
        signal_type = signal.get("type", "other")
        if signal_type in grouped:
            grouped[signal_type].append(signal)
    
    return JSONResponse({
        "status": "ok",
        "meeting_id": meeting_id,
        "signals": signals,
        "grouped": grouped,
        "counts": {k: len(v) for k, v in grouped.items()}
    })


@router.post("/{meeting_id}/extract")
async def extract_signals(meeting_id: str):
    """Re-extract signals from a meeting's notes."""
    from ....mcp.extract import extract_structured_signals
    from ....mcp.parser import parse_meeting_summary
    
    meeting_repo = get_meeting_repository()
    
    meeting = meeting_repo.get(meeting_id)
    if not meeting:
        return JSONResponse({"error": "Meeting not found"}, status_code=404)
    
    meeting_dict = meeting if isinstance(meeting, dict) else meeting.__dict__
    notes = meeting_dict.get("synthesized_notes", "")
    
    if not notes:
        return JSONResponse({"error": "No notes to extract from"}, status_code=400)
    
    # Parse and extract
    parsed = parse_meeting_summary(notes)
    signals = extract_structured_signals(parsed)
    
    # Update meeting
    updated = meeting_repo.update(meeting_id, {"signals_json": signals})
    
    return JSONResponse({
        "status": "ok",
        "meeting_id": meeting_id,
        "signals_extracted": len(signals),
        "signals": signals
    })


@router.get("/with-signals")
async def list_meetings_with_signals(limit: int = 50):
    """List meetings that have extracted signals."""
    repo = get_meeting_repository()
    
    meetings = repo.get_with_signals(limit=limit)
    
    return JSONResponse({
        "status": "ok",
        "meetings": [m if isinstance(m, dict) else m.__dict__ for m in meetings],
        "count": len(meetings)
    })


@router.post("/{meeting_id}/signals/{signal_index}/status")
async def update_signal_status(meeting_id: str, signal_index: int, request: Request):
    """Update the status of a specific signal."""
    data = await request.json()
    new_status = data.get("status")
    
    if not new_status:
        return JSONResponse({"error": "status is required"}, status_code=400)
    
    signal_repo = get_signal_repository()
    
    # Update signal status
    success = signal_repo.update_status(
        meeting_id=meeting_id,
        signal_index=signal_index,
        status=new_status
    )
    
    if not success:
        return JSONResponse({"error": "Failed to update signal status"}, status_code=500)
    
    return JSONResponse({
        "status": "ok",
        "meeting_id": meeting_id,
        "signal_index": signal_index,
        "new_status": new_status
    })
