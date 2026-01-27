# src/app/domains/signals/api/learning.py
"""
Signal Learning API Routes

Endpoints for signal feedback learning and quality improvement.
Part of the PC-1 implementation: Signal feedback → AI learning loop.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/feedback-learn")
async def learn_from_feedback():
    """
    Analyze signal feedback patterns and return learning summary.
    
    PC-1 Implementation: Signal feedback → AI learning loop
    
    Returns:
        - Feedback summary by signal type
        - Acceptance rates
        - Patterns identified from rejections/approvals
        - Learning context used for signal extraction
    """
    from ....services.signal_learning import get_signal_learning_service
    
    service = get_signal_learning_service()
    summary = service.get_feedback_summary()
    learning_context = service.generate_learning_context()
    
    return JSONResponse({
        "status": "ok",
        "feedback_summary": summary,
        "learning_context": learning_context,
        "has_sufficient_data": summary.get("total_feedback", 0) >= 5,
    })


@router.post("/refresh-learnings")
async def refresh_signal_learnings_endpoint():
    """
    Refresh signal learnings and store in ai_memory for context retrieval.
    
    Call this periodically or after significant feedback to update the
    learning patterns used by MeetingAnalyzerAgent.
    """
    from ....services.signal_learning import refresh_signal_learnings
    
    success = refresh_signal_learnings()
    
    return JSONResponse({
        "status": "ok" if success else "no_data",
        "message": "Signal learnings refreshed" if success else "Not enough feedback data to generate learnings"
    })


@router.get("/quality-hints/{signal_type}")
async def get_signal_quality_hints(signal_type: str):
    """
    Get quality hints for a specific signal type based on user feedback.
    
    Args:
        signal_type: One of decision, action_item, blocker, risk, idea
    
    Returns:
        Quality hints including acceptance rate and patterns
    """
    from ....services.signal_learning import get_signal_learning_service
    
    service = get_signal_learning_service()
    hints = service.get_signal_quality_hints(signal_type)
    
    return JSONResponse(hints)
