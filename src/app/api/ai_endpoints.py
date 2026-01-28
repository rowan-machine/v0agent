"""
AI-related API routes for the SignalFlow application.

Handles AI transcript summarization and AI memory management.
Extracted from main.py during Phase 2.9 refactoring.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..infrastructure.supabase_client import get_supabase_client
from ..services import ticket_service

router = APIRouter(tags=["AI"])

# Get supabase client for direct table access
supabase = get_supabase_client()


@router.post("/api/ai/draft-summary")
async def draft_summary_from_transcript_api(request: Request):
    """
    Generate a structured meeting summary from a transcript using GPT-4o.

    This endpoint does not require a meeting ID - useful for Load Bundle flow
    where the meeting doesn't exist yet.

    Model: gpt-4o (configured in model_routing.yaml task_type: transcript_summarization)

    Body:
        - transcript: The meeting transcript text (required)
        - meeting_name: Name of the meeting (optional, default: "Meeting")
        - focus_areas: List of areas to emphasize (optional)

    Returns:
        - status: "draft_generated" or "error"
        - draft_summary: Structured summary in template format
        - model_used: "gpt-4o"
    """
    from ..mcp.tools import draft_summary_from_transcript

    try:
        body = await request.json()
    except Exception:
        body = {}

    transcript = body.get("transcript", "")
    meeting_name = body.get("meeting_name", "Meeting")
    focus_areas = body.get("focus_areas", [])

    if not transcript or len(transcript) < 100:
        return JSONResponse(
            {"status": "error", "error": "Transcript too short. Provide at least 100 characters."},
            status_code=400,
        )

    # Call the MCP tool which uses GPT-4o
    result = draft_summary_from_transcript({
        "transcript": transcript,
        "meeting_name": meeting_name,
        "focus_areas": focus_areas,
    })

    if result.get("status") == "error" or result.get("error"):
        return JSONResponse(
            {"status": "error", "error": result.get("error", "Unknown error during summarization")},
            status_code=500,
        )

    return JSONResponse({
        "status": "draft_generated",
        "draft_summary": result.get("draft_summary"),
        "model_used": result.get("model_used", "gpt-4o"),
        "meeting_name": meeting_name,
        "instructions": "Review and edit this summary, then save with your meeting.",
    })


@router.post("/api/ai-memory/save")
async def save_ai_memory(request: Request):
    """Save an AI response to memory (approve)."""
    data = await request.json()
    source_type = data.get("source_type", "quick_ask")
    source_query = data.get("query", "")
    content = data.get("content", "")
    tags = data.get("tags", "")
    importance = data.get("importance", 5)

    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)

    result = supabase.table("ai_memory").insert({
        "source_type": source_type,
        "source_query": source_query,
        "content": content,
        "status": "approved",
        "tags": tags,
        "importance": importance,
    }).execute()

    memory_id = result.data[0]["id"] if result.data else None

    return JSONResponse({"status": "ok", "memory_id": memory_id})


@router.post("/api/ai-memory/reject")
async def reject_ai_response(request: Request):
    """Mark an AI response as rejected (don't save to memory)."""
    data = await request.json()
    source_query = data.get("query", "")
    content = data.get("content", "")

    # We can optionally log rejected responses for ML training
    supabase.table("ai_memory").insert({
        "source_type": "quick_ask",
        "source_query": source_query,
        "content": content[:500],  # Store truncated for training feedback
        "status": "rejected",
        "importance": 0,
    }).execute()

    return JSONResponse({"status": "ok"})


@router.post("/api/ai-memory/to-action")
async def convert_ai_to_action(request: Request):
    """Convert an AI response into a ticket/action item."""
    data = await request.json()
    content = data.get("content", "")
    query = data.get("query", "")

    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)

    # Generate ticket ID from Supabase
    next_num = ticket_service.get_next_ticket_number()
    ticket_id = f"AI-{next_num}"

    # Extract first line as title
    title = content.split("\n")[0][:100].strip("*#- ")
    if not title:
        title = query[:100] if query else "AI Generated Action Item"

    # Create ticket in Supabase
    result = supabase.table("tickets").insert({
        "ticket_id": ticket_id,
        "title": title,
        "description": f"From AI Query: {query}\n\nAI Response:\n{content}",
        "status": "backlog",
        "priority": "medium",
        "ai_summary": f"AI insight: {content[:150]}...",
    }).execute()

    ticket_db_id = result.data[0]["id"] if result.data else None

    return JSONResponse({"status": "ok", "ticket_id": ticket_id, "ticket_db_id": ticket_db_id})
