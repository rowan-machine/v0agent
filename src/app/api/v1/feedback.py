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

from ...db import connect

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
    with connect() as conn:
        # Check if feedback already exists (upsert pattern)
        existing = conn.execute(
            """
            SELECT id FROM signal_feedback 
            WHERE meeting_id = ? AND signal_type = ? AND signal_text = ?
            """,
            (feedback.meeting_id, feedback.signal_type, feedback.signal_text)
        ).fetchone()
        
        if existing:
            # Update existing feedback
            conn.execute(
                """
                UPDATE signal_feedback 
                SET feedback = ?, include_in_chat = ?, notes = ?
                WHERE id = ?
                """,
                (feedback.feedback, feedback.include_in_chat, feedback.notes, existing["id"])
            )
            feedback_id = existing["id"]
        else:
            # Insert new feedback
            cursor = conn.execute(
                """
                INSERT INTO signal_feedback 
                (meeting_id, signal_type, signal_text, feedback, include_in_chat, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (feedback.meeting_id, feedback.signal_type, feedback.signal_text,
                 feedback.feedback, feedback.include_in_chat, feedback.notes)
            )
            feedback_id = cursor.lastrowid
        
        # Update DIKW item confidence if this signal was promoted
        _update_dikw_confidence(conn, feedback.signal_type, feedback.signal_text, feedback.feedback)
        
        # Fetch the created/updated record
        row = conn.execute(
            "SELECT * FROM signal_feedback WHERE id = ?",
            (feedback_id,)
        ).fetchone()
    
    return FeedbackResponse(**dict(row))


def _update_dikw_confidence(conn, signal_type: str, signal_text: str, feedback: str):
    """
    Update confidence score for DIKW items based on feedback.
    
    Upvote: Increase confidence by 10% (max 1.0)
    Downvote: Decrease confidence by 10% (min 0.1)
    """
    # Find matching DIKW item
    dikw_item = conn.execute(
        """
        SELECT id, confidence, validation_count FROM dikw_items
        WHERE content LIKE ? AND original_signal_type = ?
        """,
        (f"%{signal_text}%", signal_type)
    ).fetchone()
    
    if dikw_item:
        current_confidence = dikw_item["confidence"] or 0.5
        current_validations = dikw_item["validation_count"] or 0
        
        if feedback == "up":
            new_confidence = min(1.0, current_confidence + 0.1)
            new_validations = current_validations + 1
        else:
            new_confidence = max(0.1, current_confidence - 0.1)
            new_validations = current_validations  # Don't count downvotes as validations
        
        conn.execute(
            """
            UPDATE dikw_items 
            SET confidence = ?, validation_count = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (new_confidence, new_validations, dikw_item["id"])
        )


@router.get("/feedback", response_model=List[FeedbackResponse])
async def list_feedback(
    meeting_id: Optional[int] = Query(None, description="Filter by meeting"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    feedback_type: Optional[Literal["up", "down"]] = Query(None, description="Filter by feedback type"),
    limit: int = Query(100, ge=1, le=500),
):
    """List all feedback with optional filtering."""
    with connect() as conn:
        query = "SELECT * FROM signal_feedback WHERE 1=1"
        params = []
        
        if meeting_id:
            query += " AND meeting_id = ?"
            params.append(meeting_id)
        if signal_type:
            query += " AND signal_type = ?"
            params.append(signal_type)
        if feedback_type:
            query += " AND feedback = ?"
            params.append(feedback_type)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, tuple(params)).fetchall()
    
    return [FeedbackResponse(**dict(row)) for row in rows]


@router.get("/feedback/stats", response_model=FeedbackStats)
async def get_feedback_stats():
    """Get aggregated statistics about all signal feedback."""
    with connect() as conn:
        # Total counts
        totals = conn.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback = 'up' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN feedback = 'down' THEN 1 ELSE 0 END) as downvotes
            FROM signal_feedback
            """
        ).fetchone()
        
        # By signal type
        by_type = conn.execute(
            """
            SELECT signal_type, feedback, COUNT(*) as count
            FROM signal_feedback
            GROUP BY signal_type, feedback
            """
        ).fetchall()
    
    type_stats = {}
    for row in by_type:
        sig_type = row["signal_type"]
        if sig_type not in type_stats:
            type_stats[sig_type] = {"up": 0, "down": 0}
        type_stats[sig_type][row["feedback"]] = row["count"]
    
    return FeedbackStats(
        total_feedback=totals["total"] or 0,
        upvotes=totals["upvotes"] or 0,
        downvotes=totals["downvotes"] or 0,
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
    with connect() as conn:
        # Get upvoted signals with their text patterns
        upvoted = conn.execute(
            """
            SELECT signal_type, signal_text, COUNT(*) as count
            FROM signal_feedback
            WHERE feedback = 'up'
            GROUP BY signal_type, signal_text
            ORDER BY count DESC
            """
        ).fetchall()
        
        # Get total feedback by type for ratio calculation
        totals = conn.execute(
            """
            SELECT signal_type, 
                   SUM(CASE WHEN feedback = 'up' THEN 1 ELSE 0 END) as ups,
                   SUM(CASE WHEN feedback = 'down' THEN 1 ELSE 0 END) as downs
            FROM signal_feedback
            GROUP BY signal_type
            """
        ).fetchall()
    
    results = []
    type_totals = {row["signal_type"]: row for row in totals}
    
    # Group by signal type
    type_patterns = {}
    for row in upvoted:
        sig_type = row["signal_type"]
        if sig_type not in type_patterns:
            type_patterns[sig_type] = []
        type_patterns[sig_type].append(row["signal_text"])
    
    for sig_type, patterns in type_patterns.items():
        total_row = type_totals.get(sig_type, {"ups": 0, "downs": 0})
        ups = total_row["ups"] or 0
        downs = total_row["downs"] or 0
        
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
    with connect() as conn:
        query = """
            SELECT sf.signal_type, sf.signal_text, sf.notes, sf.meeting_id,
                   ms.meeting_name, ms.meeting_date
            FROM signal_feedback sf
            LEFT JOIN meeting_summaries ms ON sf.meeting_id = ms.id
            WHERE sf.feedback = 'up' AND sf.include_in_chat = 1
        """
        params = []
        
        if signal_type:
            query += " AND sf.signal_type = ?"
            params.append(signal_type)
        
        query += " ORDER BY sf.created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, tuple(params)).fetchall()
    
    return [dict(row) for row in rows]


@router.delete("/feedback/{feedback_id}", status_code=204)
async def delete_feedback(feedback_id: int):
    """Delete a feedback entry."""
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM signal_feedback WHERE id = ?",
            (feedback_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Feedback not found")
        
        conn.execute("DELETE FROM signal_feedback WHERE id = ?", (feedback_id,))
    
    return None
