# src/app/domains/dashboard/api/quick_ask.py
"""
Dashboard Quick Ask API

AI-powered quick questions from the dashboard.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/quick-ask")
async def dashboard_quick_ask(request: Request):
    """
    Handle quick AI questions from dashboard.
    
    Delegates to ArjunaAgent.quick_ask() for centralized AI handling.
    Returns run_id for user feedback.
    """
    from ....agents.arjuna import quick_ask
    
    data = await request.json()
    topic = data.get("topic")
    query = data.get("query")
    
    try:
        result = await quick_ask(topic=topic, query=query)
        
        if result.get("success"):
            return JSONResponse({
                "response": result.get("response", ""),
                "run_id": result.get("run_id")  # From agent.last_run_id
            })
        else:
            return JSONResponse({"error": result.get("response", "AI Error")}, status_code=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"AI Error: {str(e)}"}, status_code=500)


__all__ = ["router"]
