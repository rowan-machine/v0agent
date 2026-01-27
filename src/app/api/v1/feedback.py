# src/app/api/v1/feedback.py
"""
Signal Feedback Loop API

Provides endpoints for collecting user feedback on AI-extracted signals
and using that feedback to improve extraction confidence scores.

Key features:
1. Upvote/downvote signals (thumbs up/down)
2. Query positive feedback to boost confidence
3. Use feedback patterns to improve future extractions
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

from ...infrastructure.supabase_client import get_supabase_client

router = APIRouter()


# ============== Pydantic Models ==============

class FeedbackCreate(BaseModel):
    """Create feedback for a signal."""
    meeting_id: int = Field(..., description="Meeting containing the signal")
    signal_type: str = Field(..., description="Signal type: decision, action_item, blocker, risk, idea")
    signal_text: str = Field(..., description="The signal text being rated")
    feedback: Literal["up", "down"] = Field(..., description="Thumbs up or down")
    include_in_chat: bool = Field(default=True, description="Include in chat context")
    notes: Optional[str] = Field(default=None, description="Optional user notes")


class FeedbackResponse(BaseModel):
    """Response for feedback operations."""
    id: int
    meeting_id: int
    signal_type: str
    signal_text: str
    feedback: str
    include_in_chat: bool
    notes: Optional[str]
    created_at: str


class ConfidenceBoostResult(BaseModel):
    """Result of confidence boost calculation."""
    signal_type: str
    pattern: str
    boost_factor: float = Field(..., description="Multiplier for confidence (0.5-1.5)")
    sample_signals: List[str] = Field(default_factory=list)
    feedback_count: int


class FeedbackStats(BaseModel):
    """Statistics about signal feedback."""
    total_feedback: int
    upvotes: int
    downvotes: int
    by_signal_type: dict


# ============== Endpoints ==============

@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def create_feedback(feedback: FeedbackCreate):
    """
    Record user feedback (upvote/downvote) for a signal.
    
    This feedback is used to:
    1. Filter which signals to include in chat context
    2. Boost confidence scores for similar future signals
    3. Improve signal extraction patterns
    """
    supabase = get_supabase_client()
    
    # Check if feedback already exists (upsert pattern)
    existing = supabase.table("signal_feedback").select("id").eq(
        "meeting_id", feedback.meeting_id
    ).eq("signal_type", feedback.signal_type).eq("signal_text", feedback.signal_text).execute()
    
    if existing.data:
        # Update existing feedback
        feedback_id = existing.data[0]["id"]
        supabase.table("signal_feedback").update({
            "feedback": feedback.feedback,
            "include_in_chat": feedback.include_in_chat,
            "notes": feedback.notes
        }).eq("id", feedback_id).execute()
    else:
        # Insert new feedback
        result = supabase.table("signal_feedback").insert({
            "meeting_id": feedback.meeting_id,
            "signal_type": feedback.signal_type,
            "signal_text": feedback.signal_text,
            "feedback": feedback.feedback,
            "include_in_chat": feedback.include_in_chat,
            "notes": feedback.notes
        }).execute()
        feedback_id = result.data[0]["id"] if result.data else None
    
    # Update DIKW item confidence if this signal was promoted
    _update_dikw_confidence(supabase, feedback.signal_type, feedback.signal_text, feedback.feedback)
    
    # Fetch the created/updated record
    row = supabase.table("signal_feedback").select("*").eq("id", feedback_id).execute()
    
    return FeedbackResponse(**row.data[0])


def _update_dikw_confidence(supabase, signal_type: str, signal_text: str, feedback: str):
    """
    Update confidence score for DIKW items based on feedback.
    
    Upvote: Increase confidence by 10% (max 1.0)
    Downvote: Decrease confidence by 10% (min 0.1)
    """
    # Find matching DIKW item
    dikw_result = supabase.table("dikw_items").select(
        "id, confidence, validation_count"
    ).ilike("content", f"%{signal_text}%").eq("original_signal_type", signal_type).execute()
    
    if dikw_result.data:
        dikw_item = dikw_result.data[0]
        current_confidence = dikw_item.get("confidence") or 0.5
        current_validations = dikw_item.get("validation_count") or 0
        
        if feedback == "up":
            new_confidence = min(1.0, current_confidence + 0.1)
            new_validations = current_validations + 1
        else:
            new_confidence = max(0.1, current_confidence - 0.1)
            new_validations = current_validations  # Don't count downvotes as validations
        
        supabase.table("dikw_items").update({
            "confidence": new_confidence,
            "validation_count": new_validations
        }).eq("id", dikw_item["id"]).execute()


@router.get("/feedback", response_model=List[FeedbackResponse])
async def list_feedback(
    meeting_id: Optional[int] = Query(None, description="Filter by meeting"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    feedback_type: Optional[Literal["up", "down"]] = Query(None, description="Filter by feedback type"),
    limit: int = Query(100, ge=1, le=500),
):
    """List all feedback with optional filtering."""
    supabase = get_supabase_client()
    
    query = supabase.table("signal_feedback").select("*")
    
    if meeting_id:
        query = query.eq("meeting_id", meeting_id)
    if signal_type:
        query = query.eq("signal_type", signal_type)
    if feedback_type:
        query = query.eq("feedback", feedback_type)
    
    result = query.order("created_at", desc=True).limit(limit).execute()
    rows = result.data or []
    
    return [FeedbackResponse(**row) for row in rows]


@router.get("/feedback/stats", response_model=FeedbackStats)
async def get_feedback_stats():
    """Get aggregated statistics about all signal feedback."""
    supabase = get_supabase_client()
    
    # Get all feedback for stats
    all_feedback = supabase.table("signal_feedback").select("signal_type, feedback").execute()
    rows = all_feedback.data or []
    
    total = len(rows)
    upvotes = sum(1 for r in rows if r.get("feedback") == "up")
    downvotes = sum(1 for r in rows if r.get("feedback") == "down")
    
    # Group by signal type
    type_stats = {}
    for row in rows:
        sig_type = row.get("signal_type")
        fb = row.get("feedback")
        if sig_type not in type_stats:
            type_stats[sig_type] = {"up": 0, "down": 0}
        if fb in ["up", "down"]:
            type_stats[sig_type][fb] += 1
    
    return FeedbackStats(
        total_feedback=total,
        upvotes=upvotes,
        downvotes=downvotes,
        by_signal_type=type_stats
    )


@router.get("/feedback/confidence-boost", response_model=List[ConfidenceBoostResult])
async def get_confidence_boosts():
    """
    Calculate confidence boost factors based on positive feedback patterns.
    
    This endpoint analyzes upvoted signals to identify patterns that should
    receive higher confidence scores in future extractions.
    
    Returns boost factors for each signal type based on:
    - Ratio of upvotes to total feedback
    - Number of distinct positive patterns
    """
    supabase = get_supabase_client()
    
    # Get all feedback
    all_feedback = supabase.table("signal_feedback").select("signal_type, signal_text, feedback").execute()
    rows = all_feedback.data or []
    
    # Process upvoted signals
    type_patterns = {}
    type_totals = {}
    
    for row in rows:
        sig_type = row.get("signal_type")
        fb = row.get("feedback")
        signal_text = row.get("signal_text")
        
        if sig_type not in type_totals:
            type_totals[sig_type] = {"ups": 0, "downs": 0}
        if sig_type not in type_patterns:
            type_patterns[sig_type] = []
        
        if fb == "up":
            type_totals[sig_type]["ups"] += 1
            type_patterns[sig_type].append(signal_text)
        elif fb == "down":
            type_totals[sig_type]["downs"] += 1
    
    results = []
    for sig_type, patterns in type_patterns.items():
        total_row = type_totals.get(sig_type, {"ups": 0, "downs": 0})
        ups = total_row["ups"]
        downs = total_row["downs"]
        
        if ups + downs > 0:
            # Calculate boost factor: 0.5 (all negative) to 1.5 (all positive)
            ratio = ups / (ups + downs)
            boost = 0.5 + ratio  # Range: 0.5 to 1.5
        else:
            boost = 1.0
        
        results.append(ConfidenceBoostResult(
            signal_type=sig_type,
            pattern=f"Upvoted {sig_type} signals",
            boost_factor=round(boost, 2),
            sample_signals=patterns[:5],  # Top 5 examples
            feedback_count=ups + downs
        ))
    
    return results


@router.get("/feedback/approved-signals")
async def get_approved_signals(
    signal_type: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """
    Get signals that have been upvoted for inclusion in chat context.
    
    This is used by the chat system to provide relevant context from
    user-validated signals.
    """
    supabase = get_supabase_client()
    
    # Get feedback with meeting info via join
    query = supabase.table("signal_feedback").select(
        "signal_type, signal_text, notes, meeting_id"
    ).eq("feedback", "up").eq("include_in_chat", True)
    
    if signal_type:
        query = query.eq("signal_type", signal_type)
    
    result = query.order("created_at", desc=True).limit(limit).execute()
    rows = result.data or []
    
    # Fetch meeting names for the results
    meeting_ids = list(set(r.get("meeting_id") for r in rows if r.get("meeting_id")))
    meeting_info = {}
    if meeting_ids:
        meetings_result = supabase.table("meetings").select(
            "id, meeting_name, meeting_date"
        ).in_("id", meeting_ids).execute()
        for m in meetings_result.data or []:
            meeting_info[m["id"]] = m
    
    # Combine results
    results = []
    for row in rows:
        meeting = meeting_info.get(row.get("meeting_id"), {})
        results.append({
            "signal_type": row.get("signal_type"),
            "signal_text": row.get("signal_text"),
            "notes": row.get("notes"),
            "meeting_id": row.get("meeting_id"),
            "meeting_name": meeting.get("meeting_name"),
            "meeting_date": meeting.get("meeting_date")
        })
    
    return results


@router.delete("/feedback/{feedback_id}", status_code=204)
async def delete_feedback(feedback_id: int):
    """Delete a feedback entry."""
    supabase = get_supabase_client()
    
    existing = supabase.table("signal_feedback").select("id").eq("id", feedback_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    supabase.table("signal_feedback").delete().eq("id", feedback_id).execute()
    
    return None
