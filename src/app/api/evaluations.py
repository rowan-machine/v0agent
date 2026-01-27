"""
LangSmith Evaluation API Routes

Provides endpoints for agent quality tracking and improvement feedback
through LangSmith integration.

Routes:
- /api/evaluations/feedback - Submit detailed feedback for a trace
- /api/evaluations/thumbs - Submit thumbs up/down feedback
- /api/evaluations/evaluate-signal - Evaluate signal quality
- /api/evaluations/evaluate-dikw - Evaluate DIKW promotion quality
- /api/evaluations/summary - Get aggregated feedback summary
- /api/evaluations/dashboard - Get comprehensive evaluation dashboard
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluations"])


# =============================================================================
# Feedback Submission
# =============================================================================

@router.post("/api/evaluations/feedback")
async def submit_evaluation_feedback(request: Request):
    """
    Submit feedback for a LangSmith trace.
    
    Used to provide human feedback on agent outputs for improvement.
    
    Body:
        run_id: The LangSmith run ID
        key: Feedback dimension (helpfulness, accuracy, relevance)
        score: 0.0 to 1.0 (optional)
        value: Categorical value (optional)
        comment: Freeform comment
        correction: What the correct output should have been
    """
    from ..services.evaluations import submit_feedback
    
    data = await request.json()
    run_id = data.get("run_id")
    
    if not run_id:
        return JSONResponse({"error": "run_id is required"}, status_code=400)
    
    feedback_id = submit_feedback(
        run_id=run_id,
        key=data.get("key", "user_feedback"),
        score=data.get("score"),
        value=data.get("value"),
        comment=data.get("comment"),
        correction=data.get("correction"),
        source_info={"type": "api", "user_id": data.get("user_id")},
    )
    
    return JSONResponse({
        "status": "ok" if feedback_id else "disabled",
        "feedback_id": feedback_id,
    })


@router.post("/api/evaluations/thumbs")
async def submit_thumbs_feedback(request: Request):
    """
    Submit simple thumbs up/down feedback.
    
    Body:
        run_id: The LangSmith run ID
        is_positive: true for thumbs up, false for thumbs down (or score: 1/0)
        comment: Optional explanation
    """
    from ..services.evaluations import submit_thumbs_feedback as submit_thumbs
    
    data = await request.json()
    run_id = data.get("run_id")
    
    if not run_id:
        return JSONResponse({"error": "run_id is required"}, status_code=400)
    
    # Accept both is_positive (bool) and score (0/1) formats
    is_positive = data.get("is_positive")
    if is_positive is None:
        score = data.get("score")
        is_positive = bool(score) if score is not None else True
    
    feedback_id = submit_thumbs(
        run_id=run_id,
        is_positive=is_positive,
        comment=data.get("comment"),
        user_id=data.get("user_id"),
    )
    
    return JSONResponse({
        "status": "ok" if feedback_id else "disabled",
        "feedback_id": str(feedback_id) if feedback_id else None,
    })


# =============================================================================
# Automated Evaluations
# =============================================================================

@router.post("/api/evaluations/evaluate-signal")
async def evaluate_signal_endpoint(request: Request):
    """
    Evaluate the quality of an extracted signal.
    
    Body:
        signal_text: The signal text to evaluate
        signal_type: Type (action_item, decision, blocker, risk, idea)
        source_context: The meeting transcript context
        run_id: Optional LangSmith run ID to attach feedback
    """
    from ..services.evaluations import evaluate_signal_quality, submit_feedback
    
    data = await request.json()
    
    if not data.get("signal_text") or not data.get("signal_type"):
        return JSONResponse({"error": "signal_text and signal_type required"}, status_code=400)
    
    result = evaluate_signal_quality(
        signal_text=data["signal_text"],
        signal_type=data["signal_type"],
        source_context=data.get("source_context", ""),
    )
    
    # Submit to LangSmith if run_id provided
    if data.get("run_id") and result.score is not None:
        submit_feedback(
            run_id=data["run_id"],
            key="signal_quality",
            score=result.score,
            comment=result.reasoning,
            source_info={"type": "auto_evaluator", "signal_type": data["signal_type"]},
        )
    
    return JSONResponse({
        "key": result.key,
        "score": result.score,
        "reasoning": result.reasoning,
        "metadata": result.metadata,
    })


@router.post("/api/evaluations/evaluate-dikw")
async def evaluate_dikw_promotion_endpoint(request: Request):
    """
    Evaluate the quality of a DIKW promotion.
    
    Body:
        original_item: The original DIKW item text
        original_level: data/information/knowledge/wisdom
        promoted_item: The promoted item text  
        promoted_level: The new level
        run_id: Optional LangSmith run ID
    """
    from ..services.evaluations import evaluate_dikw_promotion, submit_feedback
    
    data = await request.json()
    
    required = ["original_item", "original_level", "promoted_item", "promoted_level"]
    if not all(data.get(k) for k in required):
        return JSONResponse({"error": f"Required fields: {required}"}, status_code=400)
    
    result = evaluate_dikw_promotion(
        original_item=data["original_item"],
        original_level=data["original_level"],
        promoted_item=data["promoted_item"],
        promoted_level=data["promoted_level"],
    )
    
    # Submit to LangSmith if run_id provided
    if data.get("run_id") and result.score is not None:
        submit_feedback(
            run_id=data["run_id"],
            key="dikw_promotion_quality",
            score=result.score,
            comment=result.reasoning,
            source_info={"type": "auto_evaluator"},
        )
    
    return JSONResponse({
        "key": result.key,
        "score": result.score,
        "reasoning": result.reasoning,
        "metadata": result.metadata,
    })


# =============================================================================
# Feedback Summary
# =============================================================================

@router.get("/api/evaluations/summary")
async def get_evaluation_summary(agent_name: Optional[str] = None, days: int = 7):
    """
    Get aggregated feedback summary from LangSmith.
    
    Query params:
        agent_name: Filter by agent (optional)
        days: Number of days to look back (default 7)
    """
    from ..services.evaluations import get_feedback_summary
    
    summary = get_feedback_summary(agent_name=agent_name, days=days)
    return JSONResponse(summary)


# =============================================================================
# Evaluation Dashboard
# =============================================================================

@router.get("/api/evaluations/dashboard")
async def get_evaluation_dashboard():
    """
    Get a comprehensive evaluation dashboard with actionable insights.
    
    Returns:
        - Overall quality scores
        - Improvement suggestions based on low scores
        - Recent traces with issues
        - Recommended actions
    """
    from ..services.evaluations import is_evaluation_enabled
    
    if not is_evaluation_enabled():
        return JSONResponse({
            "enabled": False,
            "message": "LangSmith evaluation not configured. Set LANGSMITH_API_KEY to enable."
        })
    
    try:
        from langsmith import Client
        
        client = Client()
        project_name = os.environ.get("LANGSMITH_PROJECT", "signalflow")
        
        # Get recent runs with low scores
        start_time = datetime.now() - timedelta(days=7)
        
        runs = list(client.list_runs(
            project_name=project_name,
            start_time=start_time,
            limit=100,
        ))
        
        # Analyze runs
        total_runs = len(runs)
        runs_with_feedback = 0
        low_score_runs = []
        score_breakdown = {}
        
        for run in runs:
            if run.feedback_stats:
                runs_with_feedback += 1
                for key, stats in run.feedback_stats.items():
                    if key not in score_breakdown:
                        score_breakdown[key] = {"scores": [], "count": 0}
                    score_breakdown[key]["count"] += stats.get('n', 0)
                    if stats.get('avg') is not None:
                        score_breakdown[key]["scores"].append(stats['avg'])
                        # Track low-scoring runs
                        if stats['avg'] < 0.6:
                            low_score_runs.append({
                                "run_id": str(run.id),
                                "name": run.name,
                                "metric": key,
                                "score": stats['avg'],
                                "created_at": run.start_time.isoformat() if run.start_time else None,
                            })
        
        # Calculate averages and generate insights
        insights = []
        for key, data in score_breakdown.items():
            avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else None
            score_breakdown[key]["average"] = round(avg, 3) if avg else None
            
            if avg and avg < 0.6:
                if key == "helpfulness":
                    insights.append({
                        "metric": key,
                        "score": round(avg, 3),
                        "severity": "high" if avg < 0.4 else "medium",
                        "recommendation": "Responses may not be addressing user needs. Review prompts to ensure they focus on actionable, relevant answers.",
                        "action": "Review system prompts for clarity and user focus",
                    })
                elif key == "relevance":
                    insights.append({
                        "metric": key,
                        "score": round(avg, 3),
                        "severity": "high" if avg < 0.4 else "medium",
                        "recommendation": "Responses may be off-topic. Ensure context is properly passed to agents.",
                        "action": "Check context retrieval and prompt engineering",
                    })
                elif key == "accuracy":
                    insights.append({
                        "metric": key,
                        "score": round(avg, 3),
                        "severity": "high" if avg < 0.4 else "medium",
                        "recommendation": "Factual accuracy issues detected. Consider adding RAG or fact-checking.",
                        "action": "Add source verification or ground truth checks",
                    })
        
        return JSONResponse({
            "enabled": True,
            "project": project_name,
            "period_days": 7,
            "stats": {
                "total_runs": total_runs,
                "runs_with_feedback": runs_with_feedback,
                "evaluation_coverage": f"{(runs_with_feedback/total_runs*100):.1f}%" if total_runs else "0%",
            },
            "scores": {k: {"average": v["average"], "count": v["count"]} for k, v in score_breakdown.items()},
            "insights": insights,
            "low_score_runs": low_score_runs[:10],  # Top 10 issues
            "recommended_actions": [
                "Add thumbs up/down buttons to UI for user feedback",
                "Review low-scoring traces in LangSmith",
                "Update prompts based on feedback patterns",
            ] if insights else [
                "Quality looks good! Consider adding more evaluation dimensions.",
            ],
        })
        
    except Exception as e:
        return JSONResponse({
            "enabled": True,
            "error": str(e),
        })
