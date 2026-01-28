# src/app/tickets.py
"""
Ticket Management - Sprint planning and tracking.

⚠️  DEPRECATED: This file is being replaced by the domain-driven structure.
New location: src/app/domains/tickets/api/

The domain provides:
- /api/domains/tickets/items/* - CRUD operations
- /api/domains/tickets/sprints/* - Sprint management  
- /api/domains/tickets/ai/* - AI features (summary, plan, decomposition)
- /api/domains/tickets/deployment/* - Deployment tracking
- /api/domains/tickets/attachments/* - File attachments

This file remains for backward compatibility with existing UI templates.
"""

import warnings

warnings.warn(
    "tickets.py is deprecated. Use domains/tickets/api instead. "
    "Template routes will be migrated in a future update.",
    DeprecationWarning,
    stacklevel=2,
)

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import json
import os
import uuid

from .infrastructure.supabase_client import get_supabase_client
from .services import ticket_service  # Supabase service
# llm.ask removed - AI features now use TicketAgent adapters (Checkpoint 2.7)
from .memory.embed import embed_text, EMBED_MODEL
from .memory.vector_store import upsert_embedding

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

# NOTE: Local UPLOAD_DIR removed - using Supabase Storage
# See services/storage_supabase.py for file operations


# ----- Sprint Settings -----

def get_sprint_settings():
    """Get current sprint settings from Supabase."""
    import logging
    
    try:
        supabase = get_supabase_client()
        if supabase:
            result = supabase.table("sprint_settings").select("*").eq("id", 1).single().execute()
            if result.data:
                return result.data
    except Exception as e:
        logging.getLogger(__name__).debug(f"Supabase sprint settings failed: {e}")
    
    return None


def get_sprint_day():
    """Calculate current day of sprint."""
    settings = get_sprint_settings()
    if not settings:
        return None, None, None
    
    start = datetime.strptime(settings["sprint_start_date"], "%Y-%m-%d")
    today = datetime.now()
    delta = (today - start).days + 1  # Day 1 is the first day
    
    sprint_length = settings.get("sprint_length_days", 14)
    if delta < 1:
        sprint_day = 0
    elif delta > sprint_length:
        sprint_day = sprint_length
    else:
        sprint_day = delta
    
    # Calculate working days remaining (exclude weekends)
    remaining_total = max(0, sprint_length - sprint_day)
    working_days_remaining = 0
    
    for i in range(1, remaining_total + 1):
        future_date = today + timedelta(days=i)
        if future_date.weekday() < 5:  # Mon-Fri
            working_days_remaining += 1
    
    return sprint_day, sprint_length, working_days_remaining


@router.get("/settings/sprint")
def sprint_settings_page(request: Request):
    """Sprint settings page."""
    settings = get_sprint_settings()
    sprint_day, sprint_length, working_days_remaining = get_sprint_day() if settings else (None, None, None)
    
    return templates.TemplateResponse(
        "sprint_settings.html",
        {
            "request": request,
            "settings": settings,
            "sprint_day": sprint_day,
            "sprint_length": sprint_length,
            "working_days_remaining": working_days_remaining,
        },
    )


@router.post("/settings/sprint")
def save_sprint_settings(
    sprint_start_date: str = Form(...),
    sprint_length_days: int = Form(14),
    sprint_name: str = Form(None),
):
    """Save sprint settings."""
    supabase = get_supabase_client()
    supabase.table("sprint_settings").upsert({
        "id": 1,
        "sprint_start_date": sprint_start_date,
        "sprint_length_days": sprint_length_days,
        "sprint_name": sprint_name,
        "updated_at": datetime.now().isoformat()
    }).execute()
    return RedirectResponse(url="/settings/sprint?success=saved", status_code=303)


# ----- Tickets -----

@router.get("/tickets")
def list_tickets(request: Request, status: str = None):
    """List all tickets from Supabase."""
    if status:
        tickets = ticket_service.get_tickets_by_status(status, limit=100)
    else:
        tickets = ticket_service.get_all_tickets(limit=100)
    
    sprint_day, sprint_length, _ = get_sprint_day()
    
    return templates.TemplateResponse(
        "list_tickets.html",
        {
            "request": request,
            "tickets": tickets,
            "sprint_day": sprint_day,
            "sprint_length": sprint_length,
            "filter_status": status,
        },
    )


@router.get("/tickets/new")
def new_ticket_page(request: Request):
    """New ticket form."""
    return templates.TemplateResponse(
        "edit_ticket.html",
        {"request": request, "ticket": None},
    )


@router.post("/tickets/new")
def create_ticket(
    ticket_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    status: str = Form("backlog"),
    priority: str = Form(None),
    sprint_points: int = Form(0),
    in_sprint: int = Form(1),
    requires_deployment: int = Form(0),
    tags: str = Form(None),
    pending_code_files: str = Form(None),
):
    """Create a new ticket."""
    import json
    
    supabase = get_supabase_client()
    
    insert_result = supabase.table("tickets").insert({
        "ticket_id": ticket_id.strip(),
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "sprint_points": sprint_points,
        "in_sprint": bool(in_sprint),
        "requires_deployment": bool(requires_deployment),
        "tags": tags
    }).execute()
    
    new_id = insert_result.data[0]["id"] if insert_result.data else None
    
    # Handle pending code files
    if pending_code_files and new_id:
        try:
            files_data = json.loads(pending_code_files)
            for file in files_data:
                filename = file.get("filename", "").strip()
                file_type = file.get("file_type", "update")
                base_content = file.get("base_content", "")
                file_description = file.get("description", "")
                
                if filename:
                    supabase.table("ticket_files").insert({
                        "ticket_id": new_id,
                        "filename": filename,
                        "file_type": file_type,
                        "base_content": base_content,
                        "description": file_description
                    }).execute()
                    
                    # If update file with base content, also add to code locker
                    if file_type == 'update' and base_content:
                        supabase.table("code_locker").insert({
                            "ticket_id": new_id,
                            "filename": filename,
                            "content": base_content,
                            "version": 1,
                            "notes": "Initial/baseline version from ticket",
                            "is_initial": True
                        }).execute()
        except json.JSONDecodeError:
            pass  # Invalid JSON, ignore
    
    # Create embedding
    text_for_embedding = f"{ticket_id} {title}\n{description or ''}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("ticket", new_id, EMBED_MODEL, vector)
    
    return RedirectResponse(url=f"/tickets/{new_id}", status_code=303)


@router.get("/tickets/{ticket_pk}")
def view_ticket(request: Request, ticket_pk: str):
    """View a ticket."""
    # Read from Supabase
    ticket = ticket_service.get_ticket_by_id(ticket_pk)
    
    if not ticket:
        return RedirectResponse(url="/tickets", status_code=303)
    
    # Get attachments from Supabase
    attachments = []
    try:
        supabase = get_supabase_client()
        attach_result = supabase.table("attachments").select("*").eq("ref_type", "ticket").eq("ref_id", ticket_pk).execute()
        attachments = attach_result.data or []
    except Exception:
        pass
    
    return templates.TemplateResponse(
        "view_ticket.html",
        {"request": request, "ticket": ticket, "attachments": attachments},
    )


@router.get("/tickets/{ticket_pk}/edit")
def edit_ticket_page(request: Request, ticket_pk: str):
    """Edit ticket form."""
    # Read from Supabase
    ticket = ticket_service.get_ticket_by_id(ticket_pk)
    
    # Get attachments from Supabase
    attachments = []
    try:
        supabase = get_supabase_client()
        attach_result = supabase.table("attachments").select("*").eq("ref_type", "ticket").eq("ref_id", ticket_pk).execute()
        attachments = attach_result.data or []
    except Exception:
        pass
    
    return templates.TemplateResponse(
        "edit_ticket.html",
        {"request": request, "ticket": ticket, "attachments": attachments},
    )


@router.post("/tickets/{ticket_pk}/edit")
def update_ticket(
    ticket_pk: str,
    ticket_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    status: str = Form("todo"),
    priority: str = Form(None),
    sprint_points: int = Form(0),
    in_sprint: int = Form(1),
    requires_deployment: int = Form(0),
    tags: str = Form(None),
    ai_summary: str = Form(None),
    implementation_plan: str = Form(None),
    task_decomposition: str = Form(None),
    test_plan: str = Form(None),
):
    """Update a ticket."""
    # Update in Supabase
    ticket_service.update_ticket(ticket_pk, {
        "ticket_id": ticket_id,
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "sprint_points": sprint_points,
        "in_sprint": bool(in_sprint),
        "requires_deployment": bool(requires_deployment),
        "tags": tags,
        "ai_summary": ai_summary,
        "implementation_plan": implementation_plan,
        "task_decomposition": task_decomposition,
        "test_plan": test_plan,
        "updated_at": datetime.now().isoformat()
    })
    
    # Update embedding
    text_for_embedding = f"{ticket_id} {title}\n{description or ''}\n{ai_summary or ''}\n{implementation_plan or ''}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("ticket", ticket_pk, EMBED_MODEL, vector)
    
    return RedirectResponse(url=f"/tickets/{ticket_pk}?success=updated", status_code=303)


@router.post("/tickets/{ticket_pk}/delete")
def delete_ticket(ticket_pk: str):
    """Delete a ticket."""
    supabase = get_supabase_client()
    
    # Delete from Supabase (source of truth)
    ticket_service.delete_ticket(ticket_pk)
    
    # Also clean up related records in Supabase
    supabase.table("embeddings").delete().eq("ref_type", "ticket").eq("ref_id", ticket_pk).execute()
    supabase.table("attachments").delete().eq("ref_type", "ticket").eq("ref_id", ticket_pk).execute()
    
    return RedirectResponse(url="/tickets?success=deleted", status_code=303)


# ----- AI Summary Generation -----

@router.post("/api/tickets/{ticket_pk}/generate-summary")
async def generate_ticket_summary(ticket_pk: str, request: Request):
    """
    Generate AI summary for a ticket.
    
    Accepts optional JSON body with:
    - format_hint: Custom formatting instructions
    
    Delegates to TicketAgent.summarize() for AI processing (Checkpoint 2.7).
    """
    from .agents.ticket_agent import summarize_ticket_adapter
    
    # Parse optional format hints from request body
    format_hint = ""
    try:
        body = await request.json()
        format_hint = body.get("format_hint", "")
    except:
        pass
    
    try:
        result = await summarize_ticket_adapter(ticket_pk, format_hint)
        
        if not result.get("success"):
            return JSONResponse({"error": result.get("error", "Summary generation failed")}, status_code=404 if "not found" in result.get("error", "").lower() else 500)
        
        return JSONResponse({
            "summary": result["summary"],
            "saved": result.get("saved", False),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tickets/{ticket_pk}/generate-plan")
async def generate_implementation_plan(ticket_pk: str):
    """
    Generate AI implementation plan for a ticket.
    
    Uses Claude Opus 4 for premium quality planning.
    Delegates to TicketAgent.generate_plan() (Checkpoint 2.7).
    """
    from .agents.ticket_agent import generate_plan_adapter
    
    try:
        result = await generate_plan_adapter(ticket_pk)
        
        if not result.get("success"):
            return JSONResponse({"error": result.get("error", "Plan generation failed")}, status_code=404 if "not found" in result.get("error", "").lower() else 500)
        
        return JSONResponse({"plan": result["plan"]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tickets/{ticket_pk}/save-summary")
async def save_ticket_summary(request: Request, ticket_pk: str):
    """Save AI summary to ticket."""
    data = await request.json()
    summary = data.get("summary", "")
    
    supabase = get_supabase_client()
    supabase.table("tickets").update({
        "ai_summary": summary,
        "updated_at": datetime.now().isoformat()
    }).eq("id", ticket_pk).execute()
    
    return JSONResponse({"status": "ok"})


@router.post("/api/tickets/{ticket_pk}/save-plan")
async def save_implementation_plan(request: Request, ticket_pk: str):
    """Save implementation plan to ticket."""
    data = await request.json()
    plan = data.get("plan", "")
    
    supabase = get_supabase_client()
    supabase.table("tickets").update({
        "implementation_plan": plan,
        "updated_at": datetime.now().isoformat()
    }).eq("id", ticket_pk).execute()
    
    return JSONResponse({"status": "ok"})


@router.post("/api/tickets/{ticket_pk}/generate-decomposition")
async def generate_task_decomposition(ticket_pk: str):
    """
    Generate AI task breakdown for a ticket.
    
    Returns 4-8 atomic subtasks with time estimates.
    Delegates to TicketAgent.decompose() (Checkpoint 2.7).
    """
    from .agents.ticket_agent import decompose_ticket_adapter
    
    try:
        result = await decompose_ticket_adapter(ticket_pk)
        
        if not result.get("success"):
            return JSONResponse({"error": result.get("error", "Decomposition failed")}, status_code=404 if "not found" in result.get("error", "").lower() else 500)
        
        return JSONResponse({
            "tasks": result["tasks"],
            "ai_response": result.get("ai_response", ""),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tickets/{ticket_pk}/generate-tasks-from-testplan")
async def generate_tasks_from_test_plan(ticket_pk: str):
    """
    Generate tasks from the test plan using AI.
    
    Analyzes the test plan/acceptance criteria and generates
    corresponding implementation tasks.
    """
    from .llm import ask
    
    try:
        # Read ticket from Supabase
        ticket = ticket_service.get_ticket_by_id(ticket_pk)
        
        if not ticket:
            return JSONResponse({"error": "Ticket not found"}, status_code=404)
        
        test_plan = ticket.get("test_plan")
        if not test_plan or not test_plan.strip():
            return JSONResponse({"error": "No test plan found. Please add a test plan first."}, status_code=400)
        
        prompt = f"""Analyze this test plan/acceptance criteria and generate implementation tasks.

Ticket: {ticket['ticket_id']} - {ticket['title']}

Description:
{ticket['description'] or 'No description'}

Test Plan / Acceptance Criteria:
{test_plan}

Generate 4-8 specific, actionable implementation tasks that would satisfy all the test criteria.
Each task should:
1. Be directly tied to one or more acceptance criteria
2. Be completable in 1-4 hours
3. Include the specific test case it addresses

Return as a JSON array of objects with:
- "text": task description (include which test case it addresses)
- "estimate": time estimate (e.g. "1h", "2h", "30m")
- "test_case": the acceptance criteria this task satisfies

Example format:
[
  {{"text": "Implement input validation for email field (AC: Email format validation)", "estimate": "1h", "test_case": "Email must be valid format"}},
  {{"text": "Add error message display component (AC: Show validation errors)", "estimate": "30m", "test_case": "User sees clear error messages"}}
]

Return ONLY the JSON array, no other text."""

        response = ask(prompt, model="gpt-4o")
        
        # Parse JSON from response
        import re
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            tasks = json.loads(json_match.group())
        else:
            return JSONResponse({"error": "Could not parse AI response"}, status_code=500)
        
        # Save tasks to ticket
        supabase = get_supabase_client()
        supabase.table("tickets").update({
            "task_decomposition": json.dumps(tasks),
            "updated_at": datetime.now().isoformat()
        }).eq("id", ticket_pk).execute()
        
        return JSONResponse({
            "tasks": tasks,
            "source": "test_plan",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tickets/{ticket_pk}/task-status")
async def update_task_status(ticket_pk: str, request: Request):
    """Update the status of a specific task in the ticket's task decomposition."""
    try:
        data = await request.json()
        task_index = data.get("task_index")
        status = data.get("status", "pending")
        
        if task_index is None:
            return JSONResponse({"error": "task_index required"}, status_code=400)
        
        # Read from Supabase
        ticket = ticket_service.get_ticket_by_id(ticket_pk)
        
        if not ticket:
            return JSONResponse({"error": "Ticket not found"}, status_code=404)
        
        raw_tasks = ticket.get("task_decomposition")
        if not raw_tasks:
            return JSONResponse({"error": "No tasks found"}, status_code=404)
        
        tasks = json.loads(raw_tasks) if isinstance(raw_tasks, str) else raw_tasks
        
        if not isinstance(tasks, list) or task_index >= len(tasks):
            return JSONResponse({"error": "Invalid task index"}, status_code=400)
        
        # Update the task status
        if isinstance(tasks[task_index], dict):
            tasks[task_index]["status"] = status
        else:
            tasks[task_index] = {"text": str(tasks[task_index]), "status": status}
        
        # Save to Supabase
        ticket_service.update_ticket(ticket_pk, {
            "task_decomposition": json.dumps(tasks),
            "updated_at": datetime.now().isoformat()
        })
        
        return JSONResponse({"status": "ok", "task_index": task_index, "new_status": status})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/api/tickets/deployable")
async def get_deployable_tickets():
    """Get all tickets in the current sprint that require deployment (for Mode F)."""
    try:
        # Get deployment tickets from Supabase
        all_sprint_tickets = ticket_service.get_sprint_tickets()
        tickets = [t for t in all_sprint_tickets if t.get("in_sprint")]
        
        result = []
        for t in tickets:
            # Parse deployment checklist from task_decomposition or create default
            deployment_status = {
                "pushed": False,
                "pr_created": False,
                "pr_reviewed": False,
                "merged": False,
                "deployed": False
            }
            
            # Check if there's a deployment_status stored in task_decomposition
            if t.get('task_decomposition'):
                try:
                    decomp = json.loads(t['task_decomposition']) if isinstance(t['task_decomposition'], str) else t['task_decomposition']
                    if isinstance(decomp, dict) and 'deployment_status' in decomp:
                        deployment_status = decomp['deployment_status']
                except (json.JSONDecodeError, TypeError):
                    pass
            
            result.append({
                "id": t['id'],
                "ticket_id": t.get('ticket_id'),
                "title": t.get('title'),
                "status": t.get('status'),
                "priority": t.get('priority'),
                "sprint_points": t.get('sprint_points'),
                "deployment_status": deployment_status
            })
        
        return JSONResponse({"tickets": result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tickets/{ticket_pk}/deployment-status")
async def update_deployment_status(ticket_pk: str, request: Request):
    """Update deployment checklist status for a ticket."""
    try:
        data = await request.json()
        step = data.get("step")  # pushed, pr_created, pr_reviewed, merged, deployed
        status = data.get("status", False)
        
        # Read from Supabase
        ticket = ticket_service.get_ticket_by_id(ticket_pk)
        
        if not ticket:
            return JSONResponse({"error": "Ticket not found"}, status_code=404)
        
        # Parse or create deployment status structure
        decomp = {}
        if ticket.get('task_decomposition'):
            try:
                decomp = json.loads(ticket['task_decomposition']) if isinstance(ticket['task_decomposition'], str) else ticket['task_decomposition']
                if not isinstance(decomp, dict):
                    decomp = {"tasks": decomp}  # Preserve existing tasks array
            except (json.JSONDecodeError, TypeError):
                decomp = {}
        
        # Ensure deployment_status exists
        if 'deployment_status' not in decomp:
            decomp['deployment_status'] = {
                "pushed": False,
                "pr_created": False,
                "pr_reviewed": False,
                "merged": False,
                "deployed": False
            }
        
        # Update the specific step
        decomp['deployment_status'][step] = status
        
        # Save to Supabase
        ticket_service.update_ticket(ticket_pk, {
            "task_decomposition": json.dumps(decomp),
            "updated_at": datetime.now().isoformat()
        })
        
        return JSONResponse({"status": "ok", "step": step, "new_status": status})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tickets/clear-sprint")
async def clear_sprint_tickets():
    """Move all tickets out of the current sprint (to backlog)."""
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
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/sprint/archive-time")
async def archive_sprint_time():
    """Archive all time tracked during the current sprint before starting a new one."""
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
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/sprint/archived-time")
async def get_archived_sprint_time(sprint_name: str = None):
    """Get archived time tracking data, optionally filtered by sprint name."""
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
        return JSONResponse({"error": str(e)}, status_code=500)


# ----- File Uploads (Supabase Storage) -----

@router.post("/api/upload/{ref_type}/{ref_id}")
async def upload_files(
    ref_type: str,
    ref_id: int,
    files: list[UploadFile] = File(...),
):
    """Upload multiple files (screenshots, etc.) for a meeting, doc, or ticket.
    
    Files are uploaded to Supabase Storage and metadata saved to attachments table.
    """
    from .services.storage_supabase import upload_file_to_supabase
    
    if ref_type not in ["meeting", "doc", "ticket"]:
        return JSONResponse({"error": "Invalid ref_type"}, status_code=400)
    
    uploaded = []
    
    for file in files:
        content = await file.read()
        
        # Upload to Supabase Storage
        public_url, storage_path = await upload_file_to_supabase(
            content=content,
            filename=file.filename,
            meeting_id=str(ref_id),  # Use ref_id as folder
            content_type=file.content_type or "application/octet-stream"
        )
        
        if not public_url:
            # Log warning but continue - storage may not be configured
            import logging
            logging.warning(f"Failed to upload {file.filename} to Supabase Storage")
            continue
        
        # Generate AI description for images
        ai_description = None
        if file.content_type and file.content_type.startswith("image/"):
            ai_description = f"Screenshot uploaded for {ref_type} {ref_id}: {file.filename}"
        
        # Save to database
        supabase = get_supabase_client()
        insert_result = supabase.table("attachments").insert({
            "ref_type": ref_type,
            "ref_id": ref_id,
            "filename": file.filename,
            "file_path": storage_path,  # Store Supabase path
            "file_url": public_url,     # Store public URL
            "mime_type": file.content_type,
            "file_size": len(content),
            "ai_description": ai_description
        }).execute()
        attach_id = insert_result.data[0]["id"] if insert_result.data else None
        
        # Create embedding for the attachment
        embed_text_content = f"Attachment: {file.filename} for {ref_type}. {ai_description or ''}"
        vector = embed_text(embed_text_content)
        upsert_embedding("attachment", attach_id, EMBED_MODEL, vector)
        
        uploaded.append({
            "id": attach_id,
            "filename": file.filename,
            "url": public_url,
        })
    
    return JSONResponse({"uploaded": uploaded, "count": len(uploaded)})


@router.delete("/api/attachments/{attachment_id}")
async def delete_attachment(attachment_id: int):
    """Delete an attachment from Supabase Storage and database."""
    from .services.storage_supabase import delete_file_from_supabase
    
    supabase = get_supabase_client()
    
    # Get file path first
    attach_result = supabase.table("attachments").select("file_path").eq("id", attachment_id).single().execute()
    attach = attach_result.data
    
    # Delete from Supabase Storage if path exists
    if attach and attach.get("file_path"):
        await delete_file_from_supabase(attach["file_path"])
    
    supabase.table("attachments").delete().eq("id", attachment_id).execute()
    supabase.table("embeddings").delete().eq("ref_type", "attachment").eq("ref_id", attachment_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/api/attachments/{ref_type}/{ref_id}")
async def list_attachments(ref_type: str, ref_id: int):
    """List attachments for a reference."""
    supabase = get_supabase_client()
    result = supabase.table("attachments").select("*").eq("ref_type", ref_type).eq("ref_id", ref_id).execute()
    
    return JSONResponse({
        "attachments": result.data or []
    })
