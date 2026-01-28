# src/app/api/assistant.py
"""
Smart assistant chatbot that can update the knowledge base and help users navigate.

This module now delegates to the ArjunaAgent (Checkpoint 2.2) for core functionality,
maintaining backward compatibility through adapter functions.

Migration Status:
- ArjunaAgent: src/app/agents/arjuna.py (new agent implementation)
- This file: FastAPI routes + backward compatibility constants (~150 lines)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime, date, timedelta
import json
from ..infrastructure.supabase_client import get_supabase_client

# Import from ArjunaAgent (Checkpoint 2.2)
# Use async versions for FastAPI routes
from ..agents.arjuna import (
    ArjunaAgent,
    get_arjuna_agent,
    AVAILABLE_MODELS,
    SYSTEM_PAGES as ARJUNA_SYSTEM_PAGES,
    MODEL_ALIASES,
    FOCUS_KEYWORDS,
    # Async adapters for FastAPI routes
    parse_assistant_intent_async,
    execute_intent_async,
    # Sync adapters for backward compatibility
    get_follow_up_suggestions,
    get_focus_recommendations,
    get_system_context,
    parse_assistant_intent,
    execute_intent,
)

router = APIRouter()

# ===== BACKWARD COMPATIBILITY - Re-export from ArjunaAgent =====
# These constants are now defined in agents/arjuna.py but re-exported here
# for backward compatibility with any code importing from api/assistant.py

# AVAILABLE_MODELS - imported from arjuna

# ===== SYSTEM KNOWLEDGE =====
# Use ARJUNA_SYSTEM_PAGES for the rich format, keep legacy format for compatibility
SYSTEM_PAGES = {
    "dashboard": {"path": "/", "desc": "Main dashboard with sprint overview, workflow modes, DIKW pyramid, and quick actions"},
    "tickets": {"path": "/tickets", "desc": "View and manage all tickets/tasks in the current sprint"},
    "signals": {"path": "/signals", "desc": "Browse extracted signals from meetings - decisions, actions, blockers, risks, ideas"},
    "meetings": {"path": "/meetings", "desc": "List of all meeting summaries with extracted signals"},
    "meetings_new": {"path": "/meetings/new", "desc": "Create a new meeting summary from notes or transcript"},
    "documents": {"path": "/documents", "desc": "Document library for storing and searching documents"},
    "documents_new": {"path": "/documents/new", "desc": "Create a new document"},
    "career": {"path": "/career", "desc": "Career development dashboard with profile, skills, and insights"},
    "standups": {"path": "/career/standups", "desc": "Daily standup logs and career journal chat"},
    "settings": {"path": "/settings", "desc": "App settings, sprint configuration, and workflow modes"},
    "sprint_settings": {"path": "/settings#sprint", "desc": "Configure sprint name, dates, and length"},
    "search": {"path": "/search", "desc": "Search across all content - meetings, documents, tickets"},
    "query": {"path": "/query", "desc": "AI-powered natural language query interface"},
    "dikw": {"path": "/dikw", "desc": "DIKW Pyramid knowledge visualization - Data, Information, Knowledge, Wisdom"},
}

APP_KNOWLEDGE = """
=== SIGNALFLOW APP KNOWLEDGE ===

SignalFlow is a personal knowledge management and sprint tracking system built for developers.

CORE CONCEPTS:

1. SIGNALS - Extracted insights from meetings:
   - Decisions: Key choices made
   - Action Items: Tasks assigned to people
   - Blockers: Things preventing progress
   - Risks: Potential issues identified
   - Ideas: Creative suggestions and proposals
   - Context: Background information

2. DIKW PYRAMID - Knowledge hierarchy:
   - Data (📦): Raw facts and observations
   - Information (📊): Organized, meaningful data
   - Knowledge (📚): Applied information with context
   - Wisdom (🪷): Deep understanding and principles
   Items can be promoted up the pyramid as they mature.

3. WORKFLOW MODES - Sprint execution phases:
   - Mode A: Context Distillation - Select and freeze files for sprint
   - Mode B: Implementation Planning - Define scope and create plan
   - Mode C: Code Sprint - Active development work
   - Mode D: Testing & QA - Verify implementation
   - Mode E: Documentation - Update docs and knowledge base
   - Mode F: Review & Retrospective - Reflect on sprint
   - Mode G: Knowledge Transfer - Share learnings

4. SPRINT SYSTEM:
   - Configurable sprint length (default 14 days)
   - Sprint name and goals tracking
   - Point allocation for tickets
   - Burndown tracking

5. CAREER DEVELOPMENT:
   - Profile with current role, target role, strengths, weaknesses
   - Skills tracker with proficiency levels
   - Daily standups and reflections
   - AI-generated career insights
   - Code locker for saving important snippets

6. ACCOUNTABILITY:
   - "Waiting-for" items to track dependencies on others
   - Source tracking (from meetings, manual entry, etc.)

SETTINGS YOU CAN CHANGE:
- AI Model: Switch between GPT-4, GPT-4o, Claude models
- Sprint configuration: Name, start date, length
- Workflow progress: Reset for new sprint
- Theme: Light/dark mode (in UI)
"""

CAPABILITIES = f"""
I am Arjuna - your intelligent assistant for SignalFlow.

{APP_KNOWLEDGE}

=== MY CAPABILITIES ===

1. TASK MANAGEMENT:
   - Create tickets with title, description, priority, status
   - Update ticket status (todo → in_progress → blocked → done)
   - List and filter tickets
   - Mark tickets as blocked or complete

2. SYSTEM SETTINGS:
   - Change AI model (gpt-4o, gpt-4o-mini, claude-3-sonnet, etc.)
   - Update sprint name and goals
   - Reset workflow progress for new sprint
   - Get current settings status

3. ACCOUNTABILITY:
   - Add waiting-for items
   - Track who you're waiting on

4. STANDUPS & CAREER:
   - Log daily standups
   - Query recent activity

5. SEARCH & QUERY:
   - Search meetings for topics
   - Find signals by type
   - Query documents

6. NAVIGATION:
   - Guide to the right page
   - Explain app features

AVAILABLE AI MODELS: {', '.join(AVAILABLE_MODELS)}

EXAMPLE COMMANDS:
- "Switch to GPT-4o" / "Use Claude Sonnet"
- "Create a high priority task for fixing the login bug"
- "What are my blocked tickets?"
- "Reset workflow progress"
- "Update sprint name to Q1 Release"
- "Search meetings for API discussion"
- "Add waiting-for: John to review PR"
"""


# ============================================================================
# ROUTES
# All helper functions have been moved to agents/arjuna.py
# Routes use the async adapter functions for proper FastAPI integration
# ============================================================================

@router.post("/api/assistant/chat")
async def assistant_chat(request: Request):
    """Handle assistant chat messages."""
    import uuid
    from ..services.evaluations import (
        is_evaluation_enabled,
        evaluate_helpfulness,
        submit_feedback,
    )
    
    try:
        data = await request.json()
        message = data.get("message", "")
        conversation_history = data.get("history", [])
        thread_id = data.get("thread_id")  # For LangSmith thread grouping
        
        # Get current system context
        context = get_system_context()
        
        # Parse user intent with conversation history (pass thread_id for tracing)
        # Use async adapter for proper FastAPI integration
        intent_data = await parse_assistant_intent_async(message, context, conversation_history, thread_id=thread_id)
        
        # Get run_id from intent_data (if ArjunaAgent was used) or fallback to list_runs
        run_id = intent_data.get("run_id")
        if not run_id:
            try:
                from ..tracing import get_langsmith_client, get_project_name
                client = get_langsmith_client()
                if client:
                    runs = list(client.list_runs(
                        project_name=get_project_name(),
                        limit=1,
                    ))
                    if runs:
                        run_id = str(runs[0].id)
            except Exception:
                pass
        
        # If needs clarification, return questions
        if intent_data.get("clarifications") and intent_data.get("intent") == "needs_clarification":
            return JSONResponse({
                "response": intent_data.get("response_text", "I need more information."),
                "clarifications": intent_data.get("clarifications"),
                "needs_input": True,
                "run_id": run_id
            })
        
        # Execute the intent using async adapter
        execution_result = await execute_intent_async(intent_data)
        
        if not execution_result.get("success"):
            return JSONResponse({
                "response": f"Sorry, I encountered an error: {execution_result.get('error')}",
                "success": False,
                "run_id": run_id
            })
        
        # Build response
        response_text = intent_data.get("response_text", "Done!")
        
        # Add action-specific details
        action = execution_result.get("action")
        if action == "create_ticket":
            response_text += f"\n\n✅ Created ticket: **{execution_result.get('ticket_id')}**"
        elif action == "create_accountability":
            response_text += "\n\n✅ Added to your waiting-for list!"
        elif action == "create_standup":
            response_text += "\n\n✅ Standup logged!"
        elif action == "change_model":
            response_text += f"\n\n✅ AI model changed to **{execution_result.get('model')}**"
        elif action == "update_sprint":
            details = []
            if execution_result.get("sprint_name"):
                details.append(f"name: **{execution_result.get('sprint_name')}**")
            if execution_result.get("sprint_goal"):
                details.append(f"goal: **{execution_result.get('sprint_goal')}**")
            response_text += f"\n\n✅ Sprint updated - {', '.join(details)}"
        elif action == "reset_workflow":
            response_text += "\n\n✅ All workflow progress has been reset! Ready for a fresh sprint."
        elif action == "search_meetings":
            meetings = execution_result.get("meetings", [])
            if meetings:
                response_text += "\n\n📅 **Found meetings:**\n"
                for m in meetings[:5]:
                    response_text += f"• {m.get('meeting_name')} ({m.get('meeting_date')})\n"
            else:
                response_text += "\n\nNo meetings found matching your search."
        elif action == "list_tickets":
            tickets = execution_result.get("tickets", [])
            if tickets:
                response_text += "\n\n📋 **Your tickets:**\n"
                for t in tickets[:5]:
                    status_emoji = {"todo": "⬜", "in_progress": "🔄", "blocked": "🚫", "done": "✅"}.get(t.get("status"), "⬜")
                    response_text += f"• {status_emoji} {t.get('ticket_id')}: {t.get('title')}\n"
        
        # Include suggested page if present
        suggested = intent_data.get("suggested_page")
        navigate_to = execution_result.get("navigate_to")
        
        # Generate contextual follow-up suggestions based on action
        follow_ups = get_follow_up_suggestions(action, intent_data.get("intent"), execution_result)
        
        # === AUTOMATIC EVALUATION (async, non-blocking) ===
        # Run helpfulness evaluation in background and submit to LangSmith
        if is_evaluation_enabled() and response_text and message:
            try:
                import asyncio
                async def run_eval():
                    try:
                        result = evaluate_helpfulness(response_text, message)
                        if result.score is not None:
                            # Get the run_id from the most recent trace if available
                            from ..tracing import get_langsmith_client, get_project_name
                            client = get_langsmith_client()
                            if client:
                                # Find the most recent run for this agent
                                runs = list(client.list_runs(
                                    project_name=get_project_name(),
                                    limit=1,
                                ))
                                if runs:
                                    # Use custom key for numeric scores (not a built-in LangSmith evaluator)
                                    submit_feedback(
                                        run_id=str(runs[0].id),
                                        key="auto_helpfulness",  # Custom key accepts numeric scores
                                        score=result.score,
                                        comment=result.reasoning,
                                        source_info={"type": "auto_evaluator", "evaluator": "helpfulness"},
                                    )
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).debug(f"Auto-eval failed: {e}")
                
                # Fire and forget - don't wait for evaluation
                asyncio.create_task(run_eval())
            except Exception:
                pass  # Evaluation is optional
        
        return JSONResponse({
            "response": response_text,
            "success": True,
            "action": action,
            "result": execution_result,
            "suggested_page": suggested or navigate_to,
            "follow_ups": follow_ups,
            "run_id": run_id  # For user feedback
        })
    
    except Exception as e:
        return JSONResponse({
            "response": f"Sorry, I encountered an error: {str(e)}",
            "success": False
        }, status_code=500)


@router.get("/api/assistant/context")
async def get_assistant_context():
    """Get current system context for assistant."""
    context = get_system_context()
    return JSONResponse(context)


@router.get("/api/assistant/capabilities")
async def get_assistant_capabilities():
    """Get assistant capabilities and available pages."""
    return JSONResponse({
        "capabilities": CAPABILITIES,
        "pages": SYSTEM_PAGES
    })
