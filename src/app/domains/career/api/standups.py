# src/app/domains/career/api/standups.py
"""
Standup Updates API Routes

Endpoints for managing daily standup entries.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from ....repositories import get_career_repository
from ..services.standup_service import analyze_standup

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/standups")
async def get_standups(
    request: Request,
    limit: int = Query(10),
    days_back: Optional[int] = Query(None),
):
    """Get standup updates."""
    repo = get_career_repository()
    standups = repo.get_standups(limit=limit, days_back=days_back)
    
    return JSONResponse({
        "standups": [
            {
                "id": s.id,
                "yesterday": s.yesterday,
                "today": s.today,
                "blockers": s.blockers,
                "mood": s.mood,
                "notes": s.notes,
                "ai_analysis": s.ai_analysis,
                "created_at": s.created_at,
            }
            for s in standups
        ],
        "count": len(standups),
    })


@router.get("/standups/{date}")
async def get_standup_by_date(date: str):
    """Get standup for a specific date (YYYY-MM-DD)."""
    repo = get_career_repository()
    standup = repo.get_standup_by_date(date)
    
    if standup:
        return JSONResponse({
            "id": standup.id,
            "yesterday": standup.yesterday,
            "today": standup.today,
            "blockers": standup.blockers,
            "mood": standup.mood,
            "notes": standup.notes,
            "ai_analysis": standup.ai_analysis,
            "created_at": standup.created_at,
        })
    return JSONResponse({"error": "Standup not found"}, status_code=404)


@router.post("/standups")
async def create_standup(request: Request):
    """Create a new standup update with optional AI analysis."""
    data = await request.json()
    
    repo = get_career_repository()
    
    # Optionally generate AI analysis
    if data.get("analyze", False):
        analysis = await analyze_standup(
            yesterday=data.get("yesterday", ""),
            today=data.get("today", ""),
            blockers=data.get("blockers", ""),
        )
        data["ai_analysis"] = analysis
    
    # Remove the analyze flag before saving
    data.pop("analyze", None)
    
    standup = repo.add_standup(data)
    
    if standup:
        return JSONResponse({
            "status": "ok",
            "id": standup.id,
            "ai_analysis": standup.ai_analysis,
        })
    return JSONResponse({"error": "Failed to create standup"}, status_code=500)


@router.delete("/standups/{standup_id}")
async def delete_standup(standup_id: int):
    """Delete a standup update by ID."""
    repo = get_career_repository()
    success = repo.delete_standup(standup_id)
    
    if success:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Failed to delete standup"}, status_code=500)


@router.get("/standups/today")
async def get_today_standup(request: Request):
    """Get today's standup if it exists."""
    from datetime import date
    today_str = date.today().isoformat()
    
    repo = get_career_repository()
    standup = repo.get_standup_by_date(today_str)
    
    if standup:
        return JSONResponse({
            "id": standup.id,
            "yesterday": standup.yesterday,
            "today": standup.today,
            "blockers": standup.blockers,
            "mood": standup.mood,
            "notes": standup.notes,
            "ai_analysis": standup.ai_analysis,
            "created_at": standup.created_at,
        })
    return JSONResponse(None)


@router.post("/standups/suggest")
async def suggest_standup(request: Request):
    """
    Generate a suggested standup based on code locker changes and ticket progress.
    
    Delegates to CareerCoachAgent for AI processing.
    """
    from ....agents.career_coach import suggest_standup_adapter
    from ....infrastructure.supabase_client import get_supabase_client
    from datetime import datetime, timedelta, date
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Get active sprint tickets
    tickets_result = supabase.table("tickets").select(
        "id, ticket_id, title, status, description"
    ).in_("status", ["todo", "in_progress", "in_review", "blocked"]).eq(
        "in_sprint", True
    ).execute()
    tickets = tickets_result.data or []
    
    # Sort by status priority
    status_order = {"in_progress": 1, "blocked": 2, "in_review": 3, "todo": 4}
    tickets.sort(key=lambda t: status_order.get(t.get("status", "todo"), 5))
    
    # Get ticket files for each active ticket
    ticket_files_map = {}
    for t in tickets:
        files_result = supabase.table("ticket_files").select(
            "filename, file_type, description, base_content"
        ).eq("ticket_id", t.get("id")).execute()
        files = files_result.data or []
        if files:
            for f in files:
                version_result = supabase.table("code_locker").select("version").eq(
                    "filename", f.get("filename")
                ).eq("ticket_id", t.get("id")).order("version", desc=True).limit(1).execute()
                f["latest_version"] = version_result.data[0].get("version") if version_result.data else None
            ticket_files_map[t.get("ticket_id")] = files
    
    # Get recent code locker changes (last 48 hours)
    two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()
    code_result = supabase.table("code_locker").select(
        "filename, ticket_id, version, notes, is_initial, created_at"
    ).gte("created_at", two_days_ago).order("created_at", desc=True).limit(20).execute()
    code_changes_list = code_result.data or []
    
    # Enrich with ticket info
    for c in code_changes_list:
        if c.get("ticket_id"):
            ticket_info = supabase.table("tickets").select("ticket_id, title").eq("id", c["ticket_id"]).execute()
            if ticket_info.data:
                c["ticket_code"] = ticket_info.data[0].get("ticket_id")
                c["ticket_title"] = ticket_info.data[0].get("title")
    
    # Get yesterday's standup for continuity
    today_str = date.today().isoformat()
    yesterday_result = supabase.table("standup_updates").select(
        "content, feedback"
    ).lt("standup_date", today_str).order("standup_date", desc=True).limit(1).execute()
    yesterday_standup_dict = yesterday_result.data[0] if yesterday_result.data else None
    
    # Get code locker code context (helper function)
    code_locker_code = _get_code_locker_code_for_tickets(supabase, tickets)
    
    # Delegate to CareerCoachAgent
    try:
        result = await suggest_standup_adapter(
            tickets=tickets,
            ticket_files_map=ticket_files_map,
            code_changes=code_changes_list,
            code_locker_code=code_locker_code,
            yesterday_standup=yesterday_standup_dict,
            db_connection=None,
        )
        
        suggestion = result.get("suggestion", "")
        if result.get("error"):
            suggestion = f"Could not generate suggestion: {result['error']}"
    except Exception as e:
        logger.exception("Error generating standup suggestion")
        suggestion = f"Could not generate suggestion: {str(e)}"
    
    return JSONResponse({
        "status": "ok",
        "suggestion": suggestion,
        "tickets_count": len(tickets),
        "code_changes_count": len(code_changes_list),
        "files_tracked": sum(len(f) for f in ticket_files_map.values())
    })


def _get_code_locker_code_for_tickets(supabase, tickets, max_lines=40, max_chars=2000):
    """Return code locker entries for sprint tickets."""
    code_by_ticket = {}
    for t in tickets:
        tid = t.get('id')
        ticket_code = t.get('ticket_id')
        if not tid or not ticket_code:
            continue
        
        files_result = supabase.table("ticket_files").select("filename").eq("ticket_id", tid).execute()
        files = files_result.data or []
        code_by_ticket[ticket_code] = {}
        
        for f in files:
            fname = f.get('filename')
            if not fname:
                continue
            
            row_result = supabase.table("code_locker").select("content").eq("filename", fname).eq(
                "ticket_id", tid
            ).order("version", desc=True).limit(1).execute()
            rows = row_result.data or []
            
            if rows and rows[0].get('content'):
                code = rows[0]['content']
                lines = code.splitlines()
                if len(lines) > max_lines:
                    code = '\n'.join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} lines total)"
                if len(code) > max_chars:
                    code = code[:max_chars] + f"\n... (truncated, {len(rows[0]['content'])} chars total)"
                code_by_ticket[ticket_code][fname] = code
    
    return code_by_ticket
