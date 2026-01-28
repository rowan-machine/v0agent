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


@router.post("/clear")
async def clear_sprint_tickets():
    """Move all tickets out of the current sprint (to backlog)."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    try:
        supabase = get_supabase_client()
        
        # Get count of tickets in sprint before update
        count_result = supabase.table("tickets").select("id", count="exact").eq("in_sprint", True).execute()
        updated_count = count_result.count or 0
        
        # Update all tickets in sprint to be out of sprint
        supabase.table("tickets").update({
            "in_sprint": False,
            "updated_at": datetime.now().isoformat()
        }).eq("in_sprint", True).execute()
        
        return JSONResponse({"status": "ok", "updated_count": updated_count})
    except Exception as e:
        logger.exception("Error clearing sprint tickets")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/archive-time")
async def archive_sprint_time():
    """Archive all time tracked during the current sprint before starting a new one."""
    from ....infrastructure.supabase_client import get_supabase_client
    from datetime import timedelta
    
    try:
        supabase = get_supabase_client()
        
        # Get current sprint settings
        sprint_result = supabase.table("sprint_settings").select("*").eq("id", 1).single().execute()
        sprint = sprint_result.data
        
        if not sprint:
            return JSONResponse({"error": "No sprint settings found"}, status_code=400)
        
        sprint_name = sprint.get("sprint_name") or "Unnamed Sprint"
        sprint_start = sprint["sprint_start_date"]
        sprint_length = sprint.get("sprint_length_days") or 14
        
        # Calculate sprint end date
        start_date = datetime.strptime(sprint_start, "%Y-%m-%d")
        end_date = start_date + timedelta(days=sprint_length - 1)
        sprint_end = end_date.strftime("%Y-%m-%d")
        
        # Get all completed sessions within the sprint date range
        sessions_result = supabase.table("mode_sessions").select(
            "id, mode, started_at, ended_at, duration_seconds, date, notes"
        ).gte("date", sprint_start).lte("date", sprint_end).neq("ended_at", None).execute()
        sessions = sessions_result.data or []
        
        if not sessions:
            return JSONResponse({
                "status": "ok", 
                "archived_count": 0, 
                "message": "No completed sessions found for this sprint period"
            })
        
        # Archive the sessions
        archived_count = 0
        session_ids = []
        for session in sessions:
            supabase.table("archived_mode_sessions").insert({
                "original_id": session["id"],
                "mode": session["mode"],
                "started_at": session["started_at"],
                "ended_at": session["ended_at"],
                "duration_seconds": session["duration_seconds"],
                "date": session["date"],
                "notes": session.get("notes"),
                "sprint_name": sprint_name,
                "sprint_start_date": sprint_start,
                "sprint_end_date": sprint_end
            }).execute()
            archived_count += 1
            session_ids.append(session["id"])
        
        # Delete the archived sessions from active table
        if session_ids:
            supabase.table("mode_sessions").delete().in_("id", session_ids).execute()
        
        # Calculate total time archived
        total_seconds = sum(s.get("duration_seconds") or 0 for s in sessions)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        return JSONResponse({
            "status": "ok",
            "archived_count": archived_count,
            "sprint_name": sprint_name,
            "total_time": f"{hours}h {minutes}m",
            "message": f"Archived {archived_count} sessions ({hours}h {minutes}m) from {sprint_name}"
        })
        
    except Exception as e:
        logger.exception("Error archiving sprint time")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/archived-time")
async def get_archived_sprint_time(sprint_name: str = None):
    """Get archived time tracking data, optionally filtered by sprint name."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    try:
        supabase = get_supabase_client()
        
        if sprint_name:
            # Get sessions for a specific sprint - need to aggregate manually
            sessions_result = supabase.table("archived_mode_sessions").select(
                "mode, duration_seconds"
            ).eq("sprint_name", sprint_name).execute()
            
            # Aggregate by mode
            mode_stats = {}
            for s in (sessions_result.data or []):
                mode = s["mode"]
                if mode not in mode_stats:
                    mode_stats[mode] = {"mode": mode, "total_seconds": 0, "session_count": 0}
                mode_stats[mode]["total_seconds"] += s.get("duration_seconds") or 0
                mode_stats[mode]["session_count"] += 1
            
            sessions = list(mode_stats.values())
            sprints = [{"sprint_name": sprint_name}]
        else:
            # Get all archived sprints summary - need to aggregate manually
            all_sessions = supabase.table("archived_mode_sessions").select(
                "sprint_name, sprint_start_date, sprint_end_date, duration_seconds"
            ).order("sprint_start_date", desc=True).execute()
            
            # Aggregate by sprint
            sprint_stats = {}
            for s in (all_sessions.data or []):
                name = s["sprint_name"]
                if name not in sprint_stats:
                    sprint_stats[name] = {
                        "sprint_name": name,
                        "sprint_start_date": s["sprint_start_date"],
                        "sprint_end_date": s["sprint_end_date"],
                        "total_seconds": 0,
                        "session_count": 0
                    }
                sprint_stats[name]["total_seconds"] += s.get("duration_seconds") or 0
                sprint_stats[name]["session_count"] += 1
            
            sprints = list(sprint_stats.values())
            sessions = []
        
        return JSONResponse({
            "status": "ok",
            "sprints": sprints,
            "sessions": sessions
        })
        
    except Exception as e:
        logger.exception("Error getting archived sprint time")
        return JSONResponse({"error": str(e)}, status_code=500)
