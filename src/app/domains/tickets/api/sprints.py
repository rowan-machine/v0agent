# src/app/domains/tickets/api/sprints.py
"""
Sprint Management API Routes

Sprint creation, management, and analytics.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

from ....repositories import get_ticket_repository
from ..constants import DEFAULT_SPRINT_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sprints")


@router.get("")
async def list_sprints(
    limit: int = Query(DEFAULT_SPRINT_LIMIT, le=50),
    status: str = Query(None, description="Filter by status: active, completed, planned")
):
    """List all sprints."""
    repo = get_ticket_repository()
    
    # Get sprints (assuming repo has this method or we query tickets grouped by sprint)
    sprints = []
    if hasattr(repo, 'list_sprints'):
        sprints = repo.list_sprints(limit=limit, status=status)
    
    return JSONResponse({
        "status": "ok",
        "sprints": sprints,
        "count": len(sprints)
    })


@router.get("/current")
async def get_current_sprint():
    """Get the current active sprint."""
    repo = get_ticket_repository()
    
    if hasattr(repo, 'get_current_sprint'):
        sprint = repo.get_current_sprint()
        if sprint:
            return JSONResponse({"status": "ok", "sprint": sprint})
    
    return JSONResponse({
        "status": "ok",
        "sprint": None,
        "message": "No active sprint"
    })


@router.get("/{sprint_id}")
async def get_sprint(sprint_id: str):
    """Get a specific sprint with its tickets."""
    repo = get_ticket_repository()
    
    # Get tickets for this sprint
    tickets = repo.list(limit=200)
    sprint_tickets = [
        t if isinstance(t, dict) else t.__dict__ 
        for t in tickets 
        if (t.get("sprint_id") if isinstance(t, dict) else getattr(t, "sprint_id", None)) == sprint_id
    ]
    
    # Calculate stats
    total = len(sprint_tickets)
    done = len([t for t in sprint_tickets if t.get("status") == "done"])
    in_progress = len([t for t in sprint_tickets if t.get("status") == "in_progress"])
    
    return JSONResponse({
        "status": "ok",
        "sprint_id": sprint_id,
        "tickets": sprint_tickets,
        "stats": {
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "remaining": total - done,
            "completion_rate": round(done / total * 100, 1) if total > 0 else 0
        }
    })


@router.post("")
async def create_sprint(request: Request):
    """Create a new sprint."""
    data = await request.json()
    
    # Validate required fields
    if not data.get("name"):
        return JSONResponse({"error": "name is required"}, status_code=400)
    
    repo = get_ticket_repository()
    
    if hasattr(repo, 'create_sprint'):
        sprint = repo.create_sprint(data)
        return JSONResponse({"status": "ok", "sprint": sprint}, status_code=201)
    
    return JSONResponse({"error": "Sprint creation not supported"}, status_code=501)


@router.put("/{sprint_id}/complete")
async def complete_sprint(sprint_id: str):
    """Mark a sprint as complete."""
    repo = get_ticket_repository()
    
    if hasattr(repo, 'complete_sprint'):
        success = repo.complete_sprint(sprint_id)
        if success:
            return JSONResponse({"status": "ok", "message": "Sprint completed"})
    
    return JSONResponse({"error": "Failed to complete sprint"}, status_code=500)


@router.get("/{sprint_id}/burndown")
async def get_sprint_burndown(sprint_id: str):
    """Get burndown chart data for a sprint."""
    repo = get_ticket_repository()
    
    # Get tickets for this sprint
    tickets = repo.list(limit=200)
    sprint_tickets = [
        t if isinstance(t, dict) else t.__dict__ 
        for t in tickets 
        if (t.get("sprint_id") if isinstance(t, dict) else getattr(t, "sprint_id", None)) == sprint_id
    ]
    
    total_points = sum(t.get("story_points", 0) or 0 for t in sprint_tickets)
    completed_points = sum(
        t.get("story_points", 0) or 0 
        for t in sprint_tickets 
        if t.get("status") == "done"
    )
    
    return JSONResponse({
        "status": "ok",
        "sprint_id": sprint_id,
        "burndown": {
            "total_points": total_points,
            "completed_points": completed_points,
            "remaining_points": total_points - completed_points,
            "percent_complete": round(completed_points / total_points * 100, 1) if total_points > 0 else 0
        }
    })
