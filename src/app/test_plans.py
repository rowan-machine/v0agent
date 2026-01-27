# src/app/test_plans.py
"""
Test Plan Management - QA tracking and test case management.

This module handles test plan CRUD operations and AI-powered
task generation from acceptance criteria.

Uses Supabase as primary data store.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
import uuid
import os
import logging

from .llm import ask
from .services import ticket_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


def get_supabase_client():
    """Get Supabase client."""
    from .infrastructure.supabase_client import get_supabase_client as _get_client
    return _get_client()


def get_sprint_info_from_supabase():
    """Get sprint settings from Supabase."""
    try:
        sb = get_supabase_client()
        if not sb:
            return None
        result = sb.table("sprint_settings").select("*").eq("id", 1).single().execute()
        return result.data if result.data else None
    except Exception as e:
        logger.debug(f"Could not get sprint settings: {e}")
        return None


# ----- List Test Plans -----

@router.get("/test-plans")
def list_test_plans(request: Request, status: str = None):
    """List all test plans with optional status filter."""
    try:
        sb = get_supabase_client()
        if not sb:
            return templates.TemplateResponse(
                "list_test_plans.html",
                {"request": request, "test_plans": [], "filter_status": status, "sprint": None, "error": "Database not available"},
            )
        
        query = sb.table("test_plans").select("*")
        if status:
            query = query.eq("status", status)
        query = query.order("updated_at", desc=True)
        
        result = query.execute()
        test_plans = result.data or []
        
        # Get sprint info
        sprint = get_sprint_info_from_supabase()
        
        return templates.TemplateResponse(
            "list_test_plans.html",
            {
                "request": request,
                "test_plans": test_plans,
                "filter_status": status,
                "sprint": sprint,
            },
        )
    except Exception as e:
        logger.error(f"Error listing test plans: {e}")
        return templates.TemplateResponse(
            "list_test_plans.html",
            {"request": request, "test_plans": [], "filter_status": status, "sprint": None, "error": str(e)},
        )


# ----- Create Test Plan -----

@router.get("/test-plans/new")
def new_test_plan_page(request: Request):
    """New test plan form."""
    # Get tickets from Supabase
    tickets = ticket_service.get_sprint_tickets() or []
    
    return templates.TemplateResponse(
        "edit_test_plan.html",
        {"request": request, "test_plan": None, "tickets": tickets},
    )


@router.post("/test-plans/new")
def create_test_plan(
    test_plan_id: str = Form(None),
    title: str = Form(...),
    description: str = Form(None),
    acceptance_criteria: str = Form(None),
    status: str = Form("draft"),
    priority: str = Form("medium"),
    in_sprint: int = Form(1),
    linked_ticket_id: int = Form(None),
    tags: str = Form(None),
    task_decomposition: str = Form(None),
):
    """Create a new test plan."""
    # Auto-generate ID if not provided
    if not test_plan_id:
        test_plan_id = f"TP-{uuid.uuid4().hex[:6].upper()}"
    
    try:
        sb = get_supabase_client()
        if not sb:
            return RedirectResponse(url="/test-plans?error=db_unavailable", status_code=303)
        
        result = sb.table("test_plans").insert({
            "test_plan_id": test_plan_id,
            "title": title,
            "description": description,
            "acceptance_criteria": acceptance_criteria,
            "task_decomposition": task_decomposition,
            "status": status,
            "priority": priority,
            "in_sprint": in_sprint == 1,
            "linked_ticket_id": linked_ticket_id,
            "tags": tags,
        }).execute()
        
        if result.data:
            row_id = result.data[0]["id"]
            return RedirectResponse(url=f"/test-plans/{row_id}?success=created", status_code=303)
        
        return RedirectResponse(url="/test-plans?error=creation_failed", status_code=303)
    except Exception as e:
        logger.error(f"Error creating test plan: {e}")
        return RedirectResponse(url=f"/test-plans?error={str(e)[:50]}", status_code=303)


# ----- View Test Plan -----

@router.get("/test-plans/{test_plan_pk}")
def view_test_plan(request: Request, test_plan_pk: int):
    """View a test plan."""
    try:
        sb = get_supabase_client()
        if not sb:
            return RedirectResponse(url="/test-plans?error=db_unavailable", status_code=303)
        
        result = sb.table("test_plans").select("*").eq("id", test_plan_pk).single().execute()
        test_plan = result.data
        
        if not test_plan:
            return RedirectResponse(url="/test-plans?error=notfound", status_code=303)
        
        # Get linked ticket if any
        linked_ticket = None
        if test_plan.get('linked_ticket_id'):
            linked_ticket = ticket_service.get_ticket_by_id(test_plan['linked_ticket_id'])
        
        return templates.TemplateResponse(
            "view_test_plan.html",
            {"request": request, "test_plan": test_plan, "linked_ticket": linked_ticket},
        )
    except Exception as e:
        logger.error(f"Error viewing test plan {test_plan_pk}: {e}")
        return RedirectResponse(url="/test-plans?error=notfound", status_code=303)


# ----- Edit Test Plan -----

@router.get("/test-plans/{test_plan_pk}/edit")
def edit_test_plan_page(request: Request, test_plan_pk: int):
    """Edit test plan form."""
    try:
        sb = get_supabase_client()
        if not sb:
            return RedirectResponse(url="/test-plans?error=db_unavailable", status_code=303)
        
        result = sb.table("test_plans").select("*").eq("id", test_plan_pk).single().execute()
        test_plan = result.data
        
        # Get tickets from Supabase
        tickets = ticket_service.get_sprint_tickets() or []
        
        return templates.TemplateResponse(
            "edit_test_plan.html",
            {"request": request, "test_plan": test_plan, "tickets": tickets},
        )
    except Exception as e:
        logger.error(f"Error editing test plan {test_plan_pk}: {e}")
        return RedirectResponse(url="/test-plans?error=notfound", status_code=303)


@router.post("/test-plans/{test_plan_pk}/edit")
def update_test_plan(
    test_plan_pk: int,
    test_plan_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    acceptance_criteria: str = Form(None),
    status: str = Form("draft"),
    priority: str = Form("medium"),
    in_sprint: int = Form(1),
    linked_ticket_id: int = Form(None),
    tags: str = Form(None),
    task_decomposition: str = Form(None),
):
    """Update a test plan."""
    try:
        sb = get_supabase_client()
        if not sb:
            return RedirectResponse(url="/test-plans?error=db_unavailable", status_code=303)
        
        sb.table("test_plans").update({
            "test_plan_id": test_plan_id,
            "title": title,
            "description": description,
            "acceptance_criteria": acceptance_criteria,
            "task_decomposition": task_decomposition,
            "status": status,
            "priority": priority,
            "in_sprint": in_sprint == 1,
            "linked_ticket_id": linked_ticket_id,
            "tags": tags,
        }).eq("id", test_plan_pk).execute()
        
        return RedirectResponse(url=f"/test-plans/{test_plan_pk}?success=updated", status_code=303)
    except Exception as e:
        logger.error(f"Error updating test plan {test_plan_pk}: {e}")
        return RedirectResponse(url=f"/test-plans/{test_plan_pk}?error=update_failed", status_code=303)


@router.post("/test-plans/{test_plan_pk}/delete")
def delete_test_plan(test_plan_pk: int):
    """Delete a test plan."""
    try:
        sb = get_supabase_client()
        if not sb:
            return RedirectResponse(url="/test-plans?error=db_unavailable", status_code=303)
        
        sb.table("test_plans").delete().eq("id", test_plan_pk).execute()
        return RedirectResponse(url="/test-plans?success=deleted", status_code=303)
    except Exception as e:
        logger.error(f"Error deleting test plan {test_plan_pk}: {e}")
        return RedirectResponse(url="/test-plans?error=delete_failed", status_code=303)


# ----- AI Task Generation -----

@router.post("/api/test-plans/{test_plan_pk}/generate-tasks")
async def generate_test_tasks(test_plan_pk: int):
    """
    Generate test tasks from acceptance criteria using AI.
    """
    try:
        sb = get_supabase_client()
        if not sb:
            return JSONResponse({"error": "Database not available"}, status_code=503)
        
        result = sb.table("test_plans").select("*").eq("id", test_plan_pk).single().execute()
        test_plan = result.data
        
        if not test_plan:
            return JSONResponse({"error": "Test plan not found"}, status_code=404)
        
        acceptance_criteria = test_plan.get("acceptance_criteria")
        if not acceptance_criteria or not acceptance_criteria.strip():
            return JSONResponse({"error": "No acceptance criteria found"}, status_code=400)
        
        prompt = f"""Analyze these acceptance criteria/test cases and generate specific test tasks.

Test Plan: {test_plan['test_plan_id']} - {test_plan['title']}

Description:
{test_plan.get('description') or 'No description'}

Acceptance Criteria / Test Cases:
{acceptance_criteria}

Generate 4-10 specific, actionable test tasks. Each task should:
1. Be a specific test scenario to execute
2. Include clear pass/fail criteria
3. Be completable in 5-30 minutes

Return as a JSON array of objects with:
- "text": test task description
- "type": "unit" | "integration" | "manual" | "e2e" | "regression"  
- "estimate": time estimate (e.g. "10m", "30m")
- "criteria": what defines pass/fail

Example format:
[
  {{"text": "Verify email validation rejects invalid formats", "type": "unit", "estimate": "10m", "criteria": "test@, @domain.com, plain text all rejected"}},
  {{"text": "Test form submission with valid data saves to DB", "type": "integration", "estimate": "20m", "criteria": "Record appears in database with correct values"}}
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
        
        # Save tasks to test plan
        sb.table("test_plans").update({
            "task_decomposition": json.dumps(tasks)
        }).eq("id", test_plan_pk).execute()
        
        return JSONResponse({
            "tasks": tasks,
            "source": "acceptance_criteria",
        })
    except Exception as e:
        logger.error(f"Error generating test tasks: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/test-plans/{test_plan_pk}/task-status")
async def update_test_task_status(test_plan_pk: int, request: Request):
    """Update the status of a specific test task."""
    try:
        data = await request.json()
        task_index = data.get("task_index")
        status = data.get("status", "pending")  # pending, passed, failed, skipped
        
        if task_index is None:
            return JSONResponse({"error": "task_index required"}, status_code=400)
        
        sb = get_supabase_client()
        if not sb:
            return JSONResponse({"error": "Database not available"}, status_code=503)
        
        result = sb.table("test_plans").select("task_decomposition").eq("id", test_plan_pk).single().execute()
        test_plan = result.data
        
        if not test_plan:
            return JSONResponse({"error": "Test plan not found"}, status_code=404)
        
        raw_tasks = test_plan.get("task_decomposition")
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
        
        sb.table("test_plans").update({
            "task_decomposition": json.dumps(tasks)
        }).eq("id", test_plan_pk).execute()
        
        return JSONResponse({"status": "ok", "tasks": tasks})
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ----- API for Dashboard -----

@router.get("/api/test-plans/sprint")
async def get_sprint_test_plans():
    """Get test plans for current sprint (for dashboard)."""
    try:
        sb = get_supabase_client()
        if not sb:
            return JSONResponse({"error": "Database not available"}, status_code=503)
        
        result = sb.table("test_plans").select(
            "id, test_plan_id, title, status, priority, task_decomposition, linked_ticket_id"
        ).eq("in_sprint", True).order("updated_at", desc=True).execute()
        
        test_plans = result.data or []
        
        output = []
        for tp in test_plans:
            tasks = []
            if tp.get('task_decomposition'):
                try:
                    raw = tp['task_decomposition']
                    tasks = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    pass
            
            output.append({
                "id": tp['id'],
                "test_plan_id": tp['test_plan_id'],
                "title": tp['title'],
                "status": tp['status'],
                "priority": tp['priority'],
                "linked_ticket_id": tp.get('linked_ticket_id'),
                "tasks": tasks,
                "task_count": len(tasks) if isinstance(tasks, list) else 0,
                "completed_count": sum(1 for t in tasks if isinstance(t, dict) and t.get('status') in ['passed', 'done']) if isinstance(tasks, list) else 0,
            })
        
        return JSONResponse({"test_plans": output})
    except Exception as e:
        logger.error(f"Error getting sprint test plans: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
