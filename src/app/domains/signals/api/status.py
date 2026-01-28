"""
Signal status and conversion routes.

Handles signal status updates, feedback, and conversion to tickets.
Extracted from main.py during Phase 2.9 refactoring.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ....repositories import get_signal_repository
from ....services import meeting_service, ticket_service
from ....infrastructure.supabase_client import get_supabase_client

router = APIRouter()

# Repository instances
signal_repo = get_signal_repository()
supabase = get_supabase_client()


@router.post("/feedback")
async def signal_feedback(request: Request):
    """Store thumbs up/down feedback for signals."""
    data = await request.json()
    meeting_id = data.get("meeting_id")
    signal_type = data.get("signal_type")
    signal_text = data.get("signal_text")
    feedback = data.get("feedback")  # 'up', 'down', or None to remove

    if feedback is None:
        # Remove feedback using repository
        signal_repo.delete_feedback(meeting_id, signal_type, signal_text)
    else:
        # Upsert feedback using repository
        signal_repo.upsert_feedback(meeting_id, signal_type, signal_text, feedback)

    return JSONResponse({"status": "ok"})


@router.post("/status")
async def update_signal_status(request: Request):
    """Update signal status (approve/reject/archive/complete)."""
    data = await request.json()
    meeting_id = data.get("meeting_id")
    signal_type = data.get("signal_type")
    signal_text = data.get("signal_text")
    status = data.get("status")  # pending, approved, rejected, archived, completed
    notes = data.get("notes", "")

    if not all([meeting_id, signal_type, signal_text, status]):
        return JSONResponse({"error": "Missing required fields"}, status_code=400)

    # Use signal repository for status update
    signal_repo.upsert_status(meeting_id, signal_type, signal_text, status, notes)

    return JSONResponse({"status": "ok", "new_status": status})


@router.post("/convert-to-ticket")
async def convert_signal_to_ticket(request: Request):
    """Convert a signal item into a ticket/action item."""
    data = await request.json()
    meeting_id = data.get("meeting_id")
    signal_type = data.get("signal_type")
    signal_text = data.get("signal_text")

    if not all([meeting_id, signal_type, signal_text]):
        return JSONResponse({"error": "Missing required fields"}, status_code=400)

    # Get meeting name from Supabase for context
    meeting_name = meeting_service.get_meeting_name(meeting_id) or "Unknown Meeting"

    # Generate ticket ID from Supabase
    next_num = ticket_service.get_next_ticket_number()
    ticket_id = f"SIG-{next_num}"

    # Determine priority based on signal type
    priority_map = {
        "blocker": "high",
        "risk": "high",
        "action_item": "medium",
        "decision": "low",
        "idea": "low",
    }
    priority = priority_map.get(signal_type, "medium")

    # Create ticket in Supabase
    ticket_result = supabase.table("tickets").insert({
        "ticket_id": ticket_id,
        "title": signal_text[:100],
        "description": f"Signal from: {meeting_name}\n\nOriginal Signal ({signal_type}):\n{signal_text}",
        "status": "backlog",
        "priority": priority,
        "ai_summary": f"Converted from {signal_type} signal: {signal_text[:150]}...",
    }).execute()

    ticket_db_id = ticket_result.data[0]["id"] if ticket_result.data else None

    # Update signal status using repository
    signal_repo.upsert_status(
        meeting_id, signal_type, signal_text, "completed",
        converted_to="ticket", converted_ref_id=ticket_db_id,
    )

    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "ticket_db_id": ticket_db_id})


@router.get("/unprocessed")
async def get_unprocessed_signals():
    """Get signals that haven't been promoted to DIKW yet."""
    # Get meetings with signals from Supabase
    meetings = meeting_service.get_meetings_with_signals(limit=20)

    # Get already processed signals using signal repository
    processed = signal_repo.get_converted_signals("dikw")

    processed_set = set(
        (p["meeting_id"], p["signal_type"], p["signal_text"]) for p in processed
    )

    unprocessed = []
    for meeting in meetings:
        try:
            signals = meeting.get("signals", {})
            for signal_type in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                items = signals.get(signal_type, [])
                if isinstance(items, list):
                    for item in items:
                        text = item if isinstance(item, str) else item.get("text", str(item))
                        normalized_type = signal_type.rstrip("s")  # decisions -> decision
                        if normalized_type == "action_item":
                            normalized_type = "action_item"

                        if (meeting["id"], normalized_type, text) not in processed_set:
                            unprocessed.append({
                                "meeting_id": meeting["id"],
                                "meeting_name": meeting["meeting_name"],
                                "signal_type": normalized_type,
                                "text": text,
                            })
        except:
            pass

    return JSONResponse(unprocessed)
