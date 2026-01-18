# src/app/api/assistant.py
"""Smart assistant chatbot that can update the knowledge base."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import json
from ..db import connect
from ..llm import ask as ask_llm

router = APIRouter()


def get_system_context() -> dict:
    """Get current system state for assistant context."""
    with connect() as conn:
        # Get sprint info
        sprint = conn.execute(
            "SELECT * FROM sprint_settings WHERE id = 1"
        ).fetchone()
        
        # Get recent tickets
        tickets = conn.execute(
            """
            SELECT ticket_id, title, status, priority 
            FROM tickets 
            ORDER BY created_at DESC 
            LIMIT 10
            """
        ).fetchall()
        
        # Get recent signals
        recent_meetings = conn.execute(
            """
            SELECT meeting_name, signals_json, meeting_date
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL
            ORDER BY meeting_date DESC
            LIMIT 3
            """
        ).fetchall()
        
        # Get accountability items
        accountability = conn.execute(
            """
            SELECT description, responsible_party, status
            FROM accountability_items
            WHERE status = 'waiting'
            LIMIT 5
            """
        ).fetchall()
        
        # Get recent AI updates
        ai_updates = conn.execute(
            """
            SELECT source_query, content
            FROM ai_memory
            WHERE status = 'approved'
            ORDER BY created_at DESC
            LIMIT 5
            """
        ).fetchall()
    
    return {
        "sprint": dict(sprint) if sprint else None,
        "tickets": [dict(t) for t in tickets],
        "recent_meetings": [dict(m) for m in recent_meetings],
        "accountability": [dict(a) for a in accountability],
        "ai_updates": [dict(u) for u in ai_updates]
    }


def parse_assistant_intent(message: str, context: dict) -> dict:
    """Use LLM to understand user intent and extract structured data."""
    system_prompt = f"""You are an assistant that helps manage a knowledge base system.
The system has:
- Tasks/Tickets (with status, priority)
- Meetings (with signals: decisions, actions, blockers, risks, ideas)
- Accountability items (waiting-for items)
- Sprint information

Current system state:
{json.dumps(context, indent=2)}

Parse the user's message and determine:
1. Intent: create_ticket, update_ticket, create_accountability, log_activity, ask_question, or needs_clarification
2. Entities: Extract relevant data (ticket title, description, status, etc.)
3. Clarifying questions: If information is missing, what to ask

Respond ONLY with valid JSON in this format:
{{
  "intent": "create_ticket",
  "confidence": 0.9,
  "entities": {{"title": "...", "description": "...", "status": "todo"}},
  "clarifications": ["What priority should this be?"],
  "response_text": "I'll create that ticket for you..."
}}"""

    response = ask_llm(f"{system_prompt}\n\nUser message: {message}")
    
    try:
        # Try to parse JSON from response
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        
        return json.loads(response)
    except:
        # Fallback if JSON parsing fails
        return {
            "intent": "ask_question",
            "confidence": 0.5,
            "entities": {},
            "clarifications": [],
            "response_text": response
        }


def execute_intent(intent_data: dict) -> dict:
    """Execute the parsed intent."""
    intent = intent_data.get("intent")
    entities = intent_data.get("entities", {})
    
    try:
        if intent == "create_ticket":
            with connect() as conn:
                ticket_id = f"HK-{datetime.now().strftime('%y%m%d-%H%M')}"
                conn.execute(
                    """
                    INSERT INTO tickets (ticket_id, title, description, status, priority)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        ticket_id,
                        entities.get("title", "Untitled"),
                        entities.get("description", ""),
                        entities.get("status", "todo"),
                        entities.get("priority", "medium")
                    )
                )
                return {"success": True, "ticket_id": ticket_id}
        
        elif intent == "update_ticket":
            with connect() as conn:
                ticket_id = entities.get("ticket_id")
                updates = []
                params = []
                
                if "status" in entities:
                    updates.append("status = ?")
                    params.append(entities["status"])
                if "priority" in entities:
                    updates.append("priority = ?")
                    params.append(entities["priority"])
                
                if updates:
                    params.append(ticket_id)
                    conn.execute(
                        f"UPDATE tickets SET {', '.join(updates)} WHERE ticket_id = ?",
                        params
                    )
                return {"success": True}
        
        elif intent == "create_accountability":
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO accountability_items (description, responsible_party, context, source_type)
                    VALUES (?, ?, ?, 'assistant')
                    """,
                    (
                        entities.get("description", ""),
                        entities.get("responsible_party"),
                        entities.get("context", "")
                    )
                )
                return {"success": True}
        
        elif intent == "log_activity":
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO ai_memory (source_type, content, source_query)
                    VALUES ('assistant', ?, ?)
                    """,
                    (entities.get("content", ""), entities.get("summary", "Activity log"))
                )
                return {"success": True}
        
        return {"success": True, "intent": intent}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/assistant/chat")
async def assistant_chat(request: Request):
    """Handle assistant chat messages."""
    try:
        data = await request.json()
        message = data.get("message", "")
        conversation_history = data.get("history", [])
        
        # Get current system context
        context = get_system_context()
        
        # Parse user intent
        intent_data = parse_assistant_intent(message, context)
        
        # If needs clarification, return questions
        if intent_data.get("clarifications"):
            return JSONResponse({
                "response": intent_data.get("response_text", "I need more information."),
                "clarifications": intent_data.get("clarifications"),
                "needs_input": True
            })
        
        # Execute the intent
        execution_result = execute_intent(intent_data)
        
        if not execution_result.get("success"):
            return JSONResponse({
                "response": f"Sorry, I encountered an error: {execution_result.get('error')}",
                "success": False
            })
        
        # Build response
        response_text = intent_data.get("response_text", "Done!")
        if intent_data.get("intent") == "create_ticket":
            response_text += f"\n\nCreated ticket: {execution_result.get('ticket_id')}"
        
        return JSONResponse({
            "response": response_text,
            "success": True,
            "action": intent_data.get("intent"),
            "result": execution_result
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
