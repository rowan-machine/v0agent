# src/app/tickets.py
"""
Ticket Management - Sprint planning and tracking.

This module handles ticket CRUD operations and delegates to TicketAgent
(Checkpoint 2.7) for AI-powered features like summary generation,
implementation planning, and task decomposition.

Migration Status:
- TicketAgent: src/app/agents/ticket_agent.py (new agent implementation)
- This file: FastAPI routes + adapters (backward compatible)

AI Features (delegated to TicketAgent):
- generate-summary: Tag-aware ticket summaries
- generate-plan: Claude Opus implementation planning  
- generate-decomposition: Atomic task breakdown with estimates
"""

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import json
import os
import uuid

from .db import connect
from .llm import ask
from .memory.embed import embed_text, EMBED_MODEL
from .memory.vector_store import upsert_embedding

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ----- Sprint Settings -----

def get_sprint_settings():
    """Get current sprint settings."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM sprint_settings WHERE id = 1").fetchone()
    return dict(row) if row else None


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
    with connect() as conn:
        conn.execute(
            """INSERT INTO sprint_settings (id, sprint_start_date, sprint_length_days, sprint_name, updated_at)
               VALUES (1, ?, ?, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET
               sprint_start_date = excluded.sprint_start_date,
               sprint_length_days = excluded.sprint_length_days,
               sprint_name = excluded.sprint_name,
               updated_at = datetime('now')""",
            (sprint_start_date, sprint_length_days, sprint_name),
        )
    return RedirectResponse(url="/settings/sprint?success=saved", status_code=303)


# ----- Tickets -----

@router.get("/tickets")
def list_tickets(request: Request, status: str = None):
    """List all tickets."""
    with connect() as conn:
        if status:
            tickets = conn.execute(
                "SELECT * FROM tickets WHERE status = ? ORDER BY created_at DESC",
                (status,)
            ).fetchall()
        else:
            tickets = conn.execute(
                "SELECT * FROM tickets ORDER BY CASE status WHEN 'in_progress' THEN 1 WHEN 'todo' THEN 2 ELSE 3 END, created_at DESC"
            ).fetchall()
    
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
    tags: str = Form(None),
    pending_code_files: str = Form(None),
):
    """Create a new ticket."""
    import json
    
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO tickets (ticket_id, title, description, status, priority, sprint_points, in_sprint, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id.strip(), title, description, status, priority, sprint_points, in_sprint, tags),
        )
        new_id = cursor.lastrowid
        
        # Handle pending code files
        if pending_code_files:
            try:
                files_data = json.loads(pending_code_files)
                for file in files_data:
                    filename = file.get("filename", "").strip()
                    file_type = file.get("file_type", "update")
                    base_content = file.get("base_content", "")
                    file_description = file.get("description", "")
                    
                    if filename:
                        conn.execute("""
                            INSERT INTO ticket_files (ticket_id, filename, file_type, base_content, description)
                            VALUES (?, ?, ?, ?, ?)
                        """, (new_id, filename, file_type, base_content, file_description))
                        
                        # If update file with base content, also add to code locker
                        if file_type == 'update' and base_content:
                            conn.execute("""
                                INSERT INTO code_locker (ticket_id, filename, content, version, notes, is_initial)
                                VALUES (?, ?, ?, 1, 'Initial/baseline version from ticket', 1)
                            """, (new_id, filename, base_content))
            except json.JSONDecodeError:
                pass  # Invalid JSON, ignore
    
    # Create embedding
    text_for_embedding = f"{ticket_id} {title}\n{description or ''}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("ticket", new_id, EMBED_MODEL, vector)
    
    return RedirectResponse(url=f"/tickets/{new_id}", status_code=303)


@router.get("/tickets/{ticket_pk}")
def view_ticket(request: Request, ticket_pk: int):
    """View a ticket."""
    with connect() as conn:
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_pk,)
        ).fetchone()
        
        # Get attachments
        attachments = conn.execute(
            "SELECT * FROM attachments WHERE ref_type = 'ticket' AND ref_id = ?",
            (ticket_pk,)
        ).fetchall()
    
    if not ticket:
        return RedirectResponse(url="/tickets", status_code=303)
    
    return templates.TemplateResponse(
        "view_ticket.html",
        {"request": request, "ticket": ticket, "attachments": attachments},
    )


@router.get("/tickets/{ticket_pk}/edit")
def edit_ticket_page(request: Request, ticket_pk: int):
    """Edit ticket form."""
    with connect() as conn:
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_pk,)
        ).fetchone()
        
        attachments = conn.execute(
            "SELECT * FROM attachments WHERE ref_type = 'ticket' AND ref_id = ?",
            (ticket_pk,)
        ).fetchall()
    
    return templates.TemplateResponse(
        "edit_ticket.html",
        {"request": request, "ticket": ticket, "attachments": attachments},
    )


@router.post("/tickets/{ticket_pk}/edit")
def update_ticket(
    ticket_pk: int,
    ticket_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    status: str = Form("todo"),
    priority: str = Form(None),
    sprint_points: int = Form(0),
    in_sprint: int = Form(1),
    tags: str = Form(None),
    ai_summary: str = Form(None),
    implementation_plan: str = Form(None),
    task_decomposition: str = Form(None),
):
    """Update a ticket."""
    with connect() as conn:
        conn.execute(
            """UPDATE tickets SET
               ticket_id = ?, title = ?, description = ?, status = ?,
               priority = ?, sprint_points = ?, in_sprint = ?, tags = ?, ai_summary = ?, implementation_plan = ?,
               task_decomposition = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (ticket_id, title, description, status, priority, sprint_points, in_sprint, tags, 
             ai_summary, implementation_plan, task_decomposition, ticket_pk),
        )
    
    # Update embedding
    text_for_embedding = f"{ticket_id} {title}\n{description or ''}\n{ai_summary or ''}\n{implementation_plan or ''}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("ticket", ticket_pk, EMBED_MODEL, vector)
    
    return RedirectResponse(url=f"/tickets/{ticket_pk}?success=updated", status_code=303)


@router.post("/tickets/{ticket_pk}/delete")
def delete_ticket(ticket_pk: int):
    """Delete a ticket."""
    with connect() as conn:
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_pk,))
        conn.execute(
            "DELETE FROM embeddings WHERE ref_type = 'ticket' AND ref_id = ?",
            (ticket_pk,)
        )
        conn.execute(
            "DELETE FROM attachments WHERE ref_type = 'ticket' AND ref_id = ?",
            (ticket_pk,)
        )
    return RedirectResponse(url="/tickets?success=deleted", status_code=303)


# ----- AI Summary Generation -----

@router.post("/api/tickets/{ticket_pk}/generate-summary")
async def generate_ticket_summary(ticket_pk: int, request: Request):
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
async def generate_implementation_plan(ticket_pk: int):
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
async def save_ticket_summary(request: Request, ticket_pk: int):
    """Save AI summary to ticket."""
    data = await request.json()
    summary = data.get("summary", "")
    
    with connect() as conn:
        conn.execute(
            "UPDATE tickets SET ai_summary = ?, updated_at = datetime('now') WHERE id = ?",
            (summary, ticket_pk)
        )
    
    return JSONResponse({"status": "ok"})


@router.post("/api/tickets/{ticket_pk}/save-plan")
async def save_implementation_plan(request: Request, ticket_pk: int):
    """Save implementation plan to ticket."""
    data = await request.json()
    plan = data.get("plan", "")
    
    with connect() as conn:
        conn.execute(
            "UPDATE tickets SET implementation_plan = ?, updated_at = datetime('now') WHERE id = ?",
            (plan, ticket_pk)
        )
    
    return JSONResponse({"status": "ok"})


@router.post("/api/tickets/{ticket_pk}/generate-decomposition")
async def generate_task_decomposition(ticket_pk: int):
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


@router.post("/api/tickets/{ticket_pk}/task-status")
async def update_task_status(ticket_pk: int, request: Request):
    """Update the status of a specific task in the ticket's task decomposition."""
    try:
        data = await request.json()
        task_index = data.get("task_index")
        status = data.get("status", "pending")
        
        if task_index is None:
            return JSONResponse({"error": "task_index required"}, status_code=400)
        
        with connect() as conn:
            ticket = conn.execute(
                "SELECT task_decomposition FROM tickets WHERE id = ?", (ticket_pk,)
            ).fetchone()
            
            if not ticket:
                return JSONResponse({"error": "Ticket not found"}, status_code=404)
            
            raw_tasks = ticket["task_decomposition"]
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
            
            # Save back to database
            conn.execute(
                "UPDATE tickets SET task_decomposition = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(tasks), ticket_pk)
            )
        
        return JSONResponse({"status": "ok", "task_index": task_index, "new_status": status})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tickets/clear-sprint")
async def clear_sprint_tickets():
    """Move all tickets out of the current sprint (to backlog)."""
    try:
        with connect() as conn:
            result = conn.execute(
                "UPDATE tickets SET in_sprint = 0, updated_at = datetime('now') WHERE in_sprint = 1"
            )
            updated_count = result.rowcount
        
        return JSONResponse({"status": "ok", "updated_count": updated_count})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/sprint/archive-time")
async def archive_sprint_time():
    """Archive all time tracked during the current sprint before starting a new one."""
    try:
        with connect() as conn:
            # Get current sprint settings
            sprint = conn.execute("SELECT * FROM sprint_settings WHERE id = 1").fetchone()
            
            if not sprint:
                return JSONResponse({"error": "No sprint settings found"}, status_code=400)
            
            sprint_name = sprint["sprint_name"] or "Unnamed Sprint"
            sprint_start = sprint["sprint_start_date"]
            sprint_length = sprint["sprint_length_days"] or 14
            
            # Calculate sprint end date
            from datetime import datetime, timedelta
            start_date = datetime.strptime(sprint_start, "%Y-%m-%d")
            end_date = start_date + timedelta(days=sprint_length - 1)
            sprint_end = end_date.strftime("%Y-%m-%d")
            
            # Get all completed sessions within the sprint date range
            sessions = conn.execute(
                """SELECT id, mode, started_at, ended_at, duration_seconds, date, notes
                   FROM mode_sessions 
                   WHERE date >= ? AND date <= ? AND ended_at IS NOT NULL""",
                (sprint_start, sprint_end)
            ).fetchall()
            
            if not sessions:
                return JSONResponse({
                    "status": "ok", 
                    "archived_count": 0, 
                    "message": "No completed sessions found for this sprint period"
                })
            
            # Archive the sessions
            archived_count = 0
            for session in sessions:
                conn.execute(
                    """INSERT INTO archived_mode_sessions 
                       (original_id, mode, started_at, ended_at, duration_seconds, date, notes, 
                        sprint_name, sprint_start_date, sprint_end_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session["id"], session["mode"], session["started_at"], session["ended_at"],
                     session["duration_seconds"], session["date"], session["notes"],
                     sprint_name, sprint_start, sprint_end)
                )
                archived_count += 1
            
            # Delete the archived sessions from active table
            conn.execute(
                """DELETE FROM mode_sessions 
                   WHERE date >= ? AND date <= ? AND ended_at IS NOT NULL""",
                (sprint_start, sprint_end)
            )
            
            # Calculate total time archived
            total_seconds = sum(s["duration_seconds"] or 0 for s in sessions)
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
        with connect() as conn:
            if sprint_name:
                # Get sessions for a specific sprint
                sessions = conn.execute(
                    """SELECT mode, SUM(duration_seconds) as total_seconds, COUNT(*) as session_count
                       FROM archived_mode_sessions 
                       WHERE sprint_name = ?
                       GROUP BY mode""",
                    (sprint_name,)
                ).fetchall()
                
                sprints = [{"sprint_name": sprint_name}]
            else:
                # Get all archived sprints summary
                sprints = conn.execute(
                    """SELECT DISTINCT sprint_name, sprint_start_date, sprint_end_date,
                              SUM(duration_seconds) as total_seconds,
                              COUNT(*) as session_count
                       FROM archived_mode_sessions
                       GROUP BY sprint_name
                       ORDER BY sprint_start_date DESC"""
                ).fetchall()
                sessions = []
            
            return JSONResponse({
                "status": "ok",
                "sprints": [dict(s) for s in sprints],
                "sessions": [dict(s) for s in sessions] if sessions else []
            })
            
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ----- File Uploads -----

@router.post("/api/upload/{ref_type}/{ref_id}")
async def upload_files(
    ref_type: str,
    ref_id: int,
    files: list[UploadFile] = File(...),
):
    """Upload multiple files (screenshots, etc.) for a meeting, doc, or ticket."""
    if ref_type not in ["meeting", "doc", "ticket"]:
        return JSONResponse({"error": "Invalid ref_type"}, status_code=400)
    
    uploaded = []
    
    for file in files:
        # Generate unique filename
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{ref_type}_{ref_id}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Generate AI description for images
        ai_description = None
        if file.content_type and file.content_type.startswith("image/"):
            ai_description = f"Screenshot uploaded for {ref_type} {ref_id}: {file.filename}"
        
        # Save to database
        with connect() as conn:
            cursor = conn.execute(
                """INSERT INTO attachments (ref_type, ref_id, filename, file_path, mime_type, file_size, ai_description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ref_type, ref_id, file.filename, file_path, file.content_type, len(content), ai_description)
            )
            attach_id = cursor.lastrowid
        
        # Create embedding for the attachment
        embed_text_content = f"Attachment: {file.filename} for {ref_type}. {ai_description or ''}"
        vector = embed_text(embed_text_content)
        upsert_embedding("attachment", attach_id, EMBED_MODEL, vector)
        
        uploaded.append({
            "id": attach_id,
            "filename": file.filename,
            "path": file_path,
        })
    
    return JSONResponse({"uploaded": uploaded, "count": len(uploaded)})


@router.delete("/api/attachments/{attachment_id}")
async def delete_attachment(attachment_id: int):
    """Delete an attachment."""
    with connect() as conn:
        # Get file path first
        attach = conn.execute(
            "SELECT file_path FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        
        if attach and os.path.exists(attach["file_path"]):
            os.remove(attach["file_path"])
        
        conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        conn.execute(
            "DELETE FROM embeddings WHERE ref_type = 'attachment' AND ref_id = ?",
            (attachment_id,)
        )
    
    return JSONResponse({"status": "ok"})


@router.get("/api/attachments/{ref_type}/{ref_id}")
async def list_attachments(ref_type: str, ref_id: int):
    """List attachments for a reference."""
    with connect() as conn:
        attachments = conn.execute(
            "SELECT * FROM attachments WHERE ref_type = ? AND ref_id = ?",
            (ref_type, ref_id)
        ).fetchall()
    
    return JSONResponse({
        "attachments": [dict(a) for a in attachments]
    })
