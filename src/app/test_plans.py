# src/app/test_plans.py
"""
Test Plan Management - QA tracking and test case management.

This module handles test plan CRUD operations and AI-powered
task generation from acceptance criteria.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
import uuid

from .db import connect
from .llm import ask

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


# ----- List Test Plans -----

@router.get("/test-plans")
def list_test_plans(request: Request, status: str = None):
    """List all test plans with optional status filter."""
    with connect() as conn:
        if status:
            test_plans = conn.execute(
                "SELECT * FROM test_plans WHERE status = ? ORDER BY updated_at DESC",
                (status,)
            ).fetchall()
        else:
            test_plans = conn.execute(
                "SELECT * FROM test_plans ORDER BY updated_at DESC"
            ).fetchall()
        
        # Get sprint info
        sprint = conn.execute("SELECT * FROM sprint_settings WHERE id = 1").fetchone()
    
    return templates.TemplateResponse(
        "list_test_plans.html",
        {
            "request": request,
            "test_plans": test_plans,
            "filter_status": status,
            "sprint": sprint,
        },
    )


# ----- Create Test Plan -----

@router.get("/test-plans/new")
def new_test_plan_page(request: Request):
    """New test plan form."""
    with connect() as conn:
        tickets = conn.execute(
            "SELECT id, ticket_id, title FROM tickets WHERE in_sprint = 1 ORDER BY ticket_id"
        ).fetchall()
    
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
    
    with connect() as conn:
        conn.execute(
            """INSERT INTO test_plans 
               (test_plan_id, title, description, acceptance_criteria, task_decomposition,
                status, priority, in_sprint, linked_ticket_id, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (test_plan_id, title, description, acceptance_criteria, task_decomposition,
             status, priority, in_sprint, linked_ticket_id, tags),
        )
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    return RedirectResponse(url=f"/test-plans/{row_id}?success=created", status_code=303)


# ----- View Test Plan -----

@router.get("/test-plans/{test_plan_pk}")
def view_test_plan(request: Request, test_plan_pk: int):
    """View a test plan."""
    with connect() as conn:
        test_plan = conn.execute(
            "SELECT * FROM test_plans WHERE id = ?", (test_plan_pk,)
        ).fetchone()
        
        # Get linked ticket if any
        linked_ticket = None
        if test_plan and test_plan['linked_ticket_id']:
            linked_ticket = conn.execute(
                "SELECT * FROM tickets WHERE id = ?", (test_plan['linked_ticket_id'],)
            ).fetchone()
    
    if not test_plan:
        return RedirectResponse(url="/test-plans?error=notfound", status_code=303)
    
    return templates.TemplateResponse(
        "view_test_plan.html",
        {"request": request, "test_plan": test_plan, "linked_ticket": linked_ticket},
    )


# ----- Edit Test Plan -----

@router.get("/test-plans/{test_plan_pk}/edit")
def edit_test_plan_page(request: Request, test_plan_pk: int):
    """Edit test plan form."""
    with connect() as conn:
        test_plan = conn.execute(
            "SELECT * FROM test_plans WHERE id = ?", (test_plan_pk,)
        ).fetchone()
        
        tickets = conn.execute(
            "SELECT id, ticket_id, title FROM tickets WHERE in_sprint = 1 ORDER BY ticket_id"
        ).fetchall()
    
    return templates.TemplateResponse(
        "edit_test_plan.html",
        {"request": request, "test_plan": test_plan, "tickets": tickets},
    )


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
    with connect() as conn:
        conn.execute(
            """UPDATE test_plans SET
               test_plan_id = ?, title = ?, description = ?, acceptance_criteria = ?,
               task_decomposition = ?, status = ?, priority = ?, in_sprint = ?,
               linked_ticket_id = ?, tags = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (test_plan_id, title, description, acceptance_criteria, task_decomposition,
             status, priority, in_sprint, linked_ticket_id, tags, test_plan_pk),
        )
    
    return RedirectResponse(url=f"/test-plans/{test_plan_pk}?success=updated", status_code=303)


@router.post("/test-plans/{test_plan_pk}/delete")
def delete_test_plan(test_plan_pk: int):
    """Delete a test plan."""
    with connect() as conn:
        conn.execute("DELETE FROM test_plans WHERE id = ?", (test_plan_pk,))
    return RedirectResponse(url="/test-plans?success=deleted", status_code=303)


# ----- AI Task Generation -----

@router.post("/api/test-plans/{test_plan_pk}/generate-tasks")
async def generate_test_tasks(test_plan_pk: int):
    """
    Generate test tasks from acceptance criteria using AI.
    """
    try:
        with connect() as conn:
            test_plan = conn.execute(
                "SELECT * FROM test_plans WHERE id = ?", (test_plan_pk,)
            ).fetchone()
            
            if not test_plan:
                return JSONResponse({"error": "Test plan not found"}, status_code=404)
            
            acceptance_criteria = test_plan["acceptance_criteria"]
            if not acceptance_criteria or not acceptance_criteria.strip():
                return JSONResponse({"error": "No acceptance criteria found"}, status_code=400)
        
        prompt = f"""Analyze these acceptance criteria/test cases and generate specific test tasks.

Test Plan: {test_plan['test_plan_id']} - {test_plan['title']}

Description:
{test_plan['description'] or 'No description'}

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
        with connect() as conn:
            conn.execute(
                "UPDATE test_plans SET task_decomposition = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(tasks), test_plan_pk)
            )
        
        return JSONResponse({
            "tasks": tasks,
            "source": "acceptance_criteria",
        })
    except Exception as e:
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
        
        with connect() as conn:
            test_plan = conn.execute(
                "SELECT task_decomposition FROM test_plans WHERE id = ?", (test_plan_pk,)
            ).fetchone()
            
            if not test_plan:
                return JSONResponse({"error": "Test plan not found"}, status_code=404)
            
            raw_tasks = test_plan["task_decomposition"]
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
            
            conn.execute(
                "UPDATE test_plans SET task_decomposition = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(tasks), test_plan_pk)
            )
        
        return JSONResponse({"status": "ok", "tasks": tasks})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ----- API for Dashboard -----

@router.get("/api/test-plans/sprint")
async def get_sprint_test_plans():
    """Get test plans for current sprint (for dashboard)."""
    try:
        with connect() as conn:
            test_plans = conn.execute(
                """SELECT id, test_plan_id, title, status, priority, task_decomposition, linked_ticket_id
                   FROM test_plans 
                   WHERE in_sprint = 1 
                   ORDER BY 
                     CASE priority 
                       WHEN 'critical' THEN 1 
                       WHEN 'high' THEN 2 
                       WHEN 'medium' THEN 3 
                       WHEN 'low' THEN 4 
                     END,
                     updated_at DESC"""
            ).fetchall()
        
        result = []
        for tp in test_plans:
            tasks = []
            if tp['task_decomposition']:
                try:
                    tasks = json.loads(tp['task_decomposition'])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            result.append({
                "id": tp['id'],
                "test_plan_id": tp['test_plan_id'],
                "title": tp['title'],
                "status": tp['status'],
                "priority": tp['priority'],
                "linked_ticket_id": tp['linked_ticket_id'],
                "tasks": tasks,
                "task_count": len(tasks),
                "completed_count": sum(1 for t in tasks if isinstance(t, dict) and t.get('status') in ['passed', 'done']),
            })
        
        return JSONResponse({"test_plans": result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
