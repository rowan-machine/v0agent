# src/app/domains/tickets/api/ai_features.py
"""
Ticket AI Features API Routes

AI-powered features for tickets:
- Summary generation
- Implementation plan generation
- Task decomposition
- Tasks from test plan
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import json
import re
import logging

from ....services import ticket_service
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai")


@router.post("/{ticket_id}/generate-summary")
async def generate_ticket_summary(ticket_id: str, request: Request):
    """
    Generate AI summary for a ticket.
    
    Accepts optional JSON body with:
    - format_hint: Custom formatting instructions
    
    Delegates to TicketAgent.summarize() for AI processing.
    """
    from ....agents.ticket_agent import summarize_ticket_adapter
    
    # Parse optional format hints from request body
    format_hint = ""
    try:
        body = await request.json()
        format_hint = body.get("format_hint", "")
    except:
        pass
    
    try:
        result = await summarize_ticket_adapter(ticket_id, format_hint)
        
        if not result.get("success"):
            error = result.get("error", "Summary generation failed")
            status_code = 404 if "not found" in error.lower() else 500
            return JSONResponse({"error": error}, status_code=status_code)
        
        return JSONResponse({
            "summary": result["summary"],
            "saved": result.get("saved", False),
        })
    except Exception as e:
        logger.exception(f"Error generating summary for ticket {ticket_id}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/{ticket_id}/generate-plan")
async def generate_implementation_plan(ticket_id: str):
    """
    Generate AI implementation plan for a ticket.
    
    Uses Claude Opus 4 for premium quality planning.
    Delegates to TicketAgent.generate_plan().
    """
    from ....agents.ticket_agent import generate_plan_adapter
    
    try:
        result = await generate_plan_adapter(ticket_id)
        
        if not result.get("success"):
            error = result.get("error", "Plan generation failed")
            status_code = 404 if "not found" in error.lower() else 500
            return JSONResponse({"error": error}, status_code=status_code)
        
        return JSONResponse({"plan": result["plan"]})
    except Exception as e:
        logger.exception(f"Error generating plan for ticket {ticket_id}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/{ticket_id}/save-summary")
async def save_ticket_summary(request: Request, ticket_id: str):
    """Save AI summary to ticket."""
    data = await request.json()
    summary = data.get("summary", "")
    
    supabase = get_supabase_client()
    supabase.table("tickets").update({
        "ai_summary": summary,
        "updated_at": datetime.now().isoformat()
    }).eq("id", ticket_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.post("/{ticket_id}/save-plan")
async def save_implementation_plan(request: Request, ticket_id: str):
    """Save implementation plan to ticket."""
    data = await request.json()
    plan = data.get("plan", "")
    
    supabase = get_supabase_client()
    supabase.table("tickets").update({
        "implementation_plan": plan,
        "updated_at": datetime.now().isoformat()
    }).eq("id", ticket_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.post("/{ticket_id}/generate-decomposition")
async def generate_task_decomposition(ticket_id: str):
    """
    Generate AI task breakdown for a ticket.
    
    Returns 4-8 atomic subtasks with time estimates.
    Delegates to TicketAgent.decompose().
    """
    from ....agents.ticket_agent import decompose_ticket_adapter
    
    try:
        result = await decompose_ticket_adapter(ticket_id)
        
        if not result.get("success"):
            error = result.get("error", "Decomposition failed")
            status_code = 404 if "not found" in error.lower() else 500
            return JSONResponse({"error": error}, status_code=status_code)
        
        return JSONResponse({
            "tasks": result["tasks"],
            "ai_response": result.get("ai_response", ""),
        })
    except Exception as e:
        logger.exception(f"Error decomposing ticket {ticket_id}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/{ticket_id}/generate-tasks-from-testplan")
async def generate_tasks_from_test_plan(ticket_id: str):
    """
    Generate tasks from the test plan using AI.
    
    Analyzes the test plan/acceptance criteria and generates
    corresponding implementation tasks.
    """
    from ....llm import ask
    
    try:
        ticket = ticket_service.get_ticket_by_id(ticket_id)
        
        if not ticket:
            return JSONResponse({"error": "Ticket not found"}, status_code=404)
        
        test_plan = ticket.get("test_plan")
        if not test_plan or not test_plan.strip():
            return JSONResponse({"error": "No test plan found. Please add a test plan first."}, status_code=400)
        
        prompt = f"""Analyze this test plan/acceptance criteria and generate implementation tasks.

Ticket: {ticket.get('ticket_id', ticket_id)} - {ticket.get('title', '')}

Description:
{ticket.get('description') or 'No description'}

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

Return ONLY the JSON array, no other text."""

        response = ask(prompt, model="gpt-4o")
        
        # Parse JSON from response
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
        }).eq("id", ticket_id).execute()
        
        return JSONResponse({
            "tasks": tasks,
            "source": "test_plan",
        })
    except Exception as e:
        logger.exception(f"Error generating tasks from test plan for ticket {ticket_id}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/{ticket_id}/task-status")
async def update_task_status(ticket_id: str, request: Request):
    """Update the status of a specific task in the ticket's task decomposition."""
    try:
        data = await request.json()
        task_index = data.get("task_index")
        status = data.get("status", "pending")
        
        if task_index is None:
            return JSONResponse({"error": "task_index required"}, status_code=400)
        
        ticket = ticket_service.get_ticket_by_id(ticket_id)
        
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
        ticket_service.update_ticket(ticket_id, {
            "task_decomposition": json.dumps(tasks),
            "updated_at": datetime.now().isoformat()
        })
        
        return JSONResponse({"status": "ok", "task_index": task_index, "new_status": status})
    except Exception as e:
        logger.exception(f"Error updating task status for ticket {ticket_id}")
        return JSONResponse({"error": str(e)}, status_code=500)
