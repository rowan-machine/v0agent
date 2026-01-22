# src/app/api/assistant.py
"""
Smart assistant chatbot that can update the knowledge base and help users navigate.

This module now delegates to the ArjunaAgent (Checkpoint 2.2) for core functionality,
maintaining backward compatibility through adapter functions.

Migration Status:
- ArjunaAgent: src/app/agents/arjuna.py (new agent implementation)
- This file: Adapters + FastAPI routes (will be slimmed down over time)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime, date, timedelta
import json
from ..db import connect
from ..llm import ask as ask_llm

# Import from new Arjuna agent (Checkpoint 2.2)
from ..agents.arjuna import (
    ArjunaAgent,
    get_arjuna_agent,
    AVAILABLE_MODELS,
    SYSTEM_PAGES as ARJUNA_SYSTEM_PAGES,
    MODEL_ALIASES,
    FOCUS_KEYWORDS,
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


def get_follow_up_suggestions(action: str, intent: str, result: dict) -> list:
    """Generate contextual follow-up suggestions based on action performed."""
    
    # Default suggestions if nothing specific
    default_suggestions = [
        {"emoji": "📋", "text": "My Tickets", "message": "What are my open tickets?"},
        {"emoji": "🎯", "text": "Focus", "message": "What should I focus on today?"},
        {"emoji": "💡", "text": "Help", "message": "What else can you help me with?"},
    ]
    
    if action == "create_ticket":
        return [
            {"emoji": "➕", "text": "Create Another", "message": "Create a task for "},
            {"emoji": "📋", "text": "View Tickets", "message": "Show me all my tickets"},
            {"emoji": "🎯", "text": "High Priority", "message": "What are my high priority tickets?"},
        ]
    
    elif action == "list_tickets":
        tickets = result.get("tickets", [])
        suggestions = [
            {"emoji": "➕", "text": "New Task", "message": "Create a task for "},
        ]
        if any(t.get("status") == "blocked" for t in tickets):
            suggestions.append({"emoji": "🚫", "text": "Unblock", "message": "Help me unblock a ticket"})
        if any(t.get("status") == "in_progress" for t in tickets):
            suggestions.append({"emoji": "✅", "text": "Complete", "message": "Mark a ticket as done"})
        suggestions.append({"emoji": "🔍", "text": "Filter", "message": "Show blocked tickets"})
        return suggestions[:4]
    
    elif action == "change_model":
        return [
            {"emoji": "🤖", "text": "Try GPT-4o", "message": "Switch to GPT-4o"},
            {"emoji": "🧠", "text": "Try Claude", "message": "Switch to Claude Sonnet"},
            {"emoji": "⚡", "text": "Fast Model", "message": "Switch to GPT-4o-mini"},
        ]
    
    elif action == "update_sprint":
        return [
            {"emoji": "🔄", "text": "Reset Progress", "message": "Reset workflow progress"},
            {"emoji": "📊", "text": "Sprint Status", "message": "What is the sprint status?"},
            {"emoji": "📋", "text": "View Tickets", "message": "Show me all tickets"},
        ]
    
    elif action == "reset_workflow":
        return [
            {"emoji": "🎯", "text": "Mode A", "message": "What are the steps for Mode A?"},
            {"emoji": "📋", "text": "Create Task", "message": "Create a task for "},
            {"emoji": "📊", "text": "Sprint Status", "message": "What is the sprint status?"},
        ]
    
    elif action == "search_meetings":
        return [
            {"emoji": "📅", "text": "Search More", "message": "Search meetings for "},
            {"emoji": "🔍", "text": "Signals", "message": "What decisions were made recently?"},
            {"emoji": "📝", "text": "New Meeting", "message": "Log a new meeting"},
        ]
    
    elif action == "navigate":
        return [
            {"emoji": "🏠", "text": "Dashboard", "message": "Go to dashboard"},
            {"emoji": "📋", "text": "Tickets", "message": "Go to tickets"},
            {"emoji": "🔍", "text": "Search", "message": "Search for "},
        ]
    
    elif action == "create_accountability":
        return [
            {"emoji": "⏳", "text": "Add Another", "message": "Add waiting-for: "},
            {"emoji": "📋", "text": "View All", "message": "What am I waiting on?"},
            {"emoji": "🎯", "text": "Focus", "message": "What should I focus on?"},
        ]
    
    elif action == "focus_recommendations":
        return [
            {"emoji": "📋", "text": "View Tickets", "message": "Show me all my tickets"},
            {"emoji": "🚫", "text": "Blockers", "message": "What are my blocked tickets?"},
            {"emoji": "➕", "text": "New Task", "message": "Create a task for "},
            {"emoji": "📊", "text": "Sprint", "message": "What is the sprint status?"},
        ]
    
    elif intent == "help" or intent == "explain":
        return [
            {"emoji": "📋", "text": "My Tickets", "message": "What are my tickets?"},
            {"emoji": "🤖", "text": "Change Model", "message": "Switch to GPT-4o"},
            {"emoji": "📅", "text": "Meetings", "message": "Search meetings for "},
            {"emoji": "➕", "text": "New Task", "message": "Create a task for "},
        ]
    
    return default_suggestions


def get_focus_recommendations() -> dict:
    """Generate smart focus recommendations based on current state.
    
    Returns prioritized recommendations with reasoning.
    """
    recommendations = []
    
    with connect() as conn:
        # 1. BLOCKED TICKETS (Highest Priority)
        blocked = conn.execute(
            """SELECT ticket_id, title, description FROM tickets 
               WHERE status = 'blocked' 
               ORDER BY priority DESC, updated_at DESC LIMIT 3"""
        ).fetchall()
        if blocked:
            for t in blocked:
                recommendations.append({
                    "priority": 1,
                    "type": "blocker",
                    "title": f"🚧 Unblock: {t['ticket_id']}",
                    "text": t['title'],
                    "reason": "Blocked tickets prevent all downstream work",
                    "action": f"Review and unblock {t['ticket_id']}"
                })
        
        # 2. HIGH PRIORITY IN-PROGRESS (Get things done)
        in_progress = conn.execute(
            """SELECT ticket_id, title FROM tickets 
               WHERE status = 'in_progress' 
               ORDER BY priority DESC, updated_at ASC LIMIT 2"""
        ).fetchall()
        if in_progress:
            for t in in_progress:
                recommendations.append({
                    "priority": 2,
                    "type": "active",
                    "title": f"🏃 Complete: {t['ticket_id']}",
                    "text": t['title'],
                    "reason": "Finishing in-progress work reduces context switching",
                    "action": "Continue working on this ticket"
                })
        
        # 3. SPRINT DEADLINE CHECK
        sprint = conn.execute(
            "SELECT * FROM sprint_settings WHERE id = 1"
        ).fetchone()
        if sprint and sprint['start_date']:
            try:
                start = datetime.strptime(sprint['start_date'], '%Y-%m-%d')
                length = sprint['length_days'] or 14
                end = start + timedelta(days=length)
                days_left = (end - datetime.now()).days
                
                if days_left <= 3 and days_left > 0:
                    todo_count = conn.execute(
                        "SELECT COUNT(*) as c FROM tickets WHERE status = 'todo'"
                    ).fetchone()['c']
                    if todo_count > 0:
                        recommendations.append({
                            "priority": 2,
                            "type": "deadline",
                            "title": f"⏰ Sprint ends in {days_left} day{'s' if days_left != 1 else ''}",
                            "text": f"{todo_count} items still in todo",
                            "reason": "Time is running out - consider scope reduction",
                            "action": "Review remaining work and prioritize ruthlessly"
                        })
            except:
                pass
        
        # 4. STALE WORK (Tickets stuck for a while)
        stale = conn.execute(
            """SELECT ticket_id, title, updated_at FROM tickets 
               WHERE status = 'in_progress' 
               AND date(updated_at) < date('now', '-2 days')
               ORDER BY updated_at ASC LIMIT 1"""
        ).fetchall()
        for t in stale:
            recommendations.append({
                "priority": 3,
                "type": "stale",
                "title": f"⏳ Stale: {t['ticket_id']}",
                "text": t['title'],
                "reason": "This has been in progress for days - is it blocked?",
                "action": "Either complete it or mark it blocked"
            })
        
        # 5. WAITING-FOR ITEMS (Follow up on dependencies)
        waiting = conn.execute(
            """SELECT description, responsible_party FROM accountability_items
               WHERE status = 'waiting'
               ORDER BY created_at ASC LIMIT 2"""
        ).fetchall()
        for w in waiting:
            recommendations.append({
                "priority": 4,
                "type": "waiting",
                "title": f"⏳ Follow up: {w['responsible_party']}",
                "text": w['description'][:60],
                "reason": "Dependencies on others can become blockers",
                "action": f"Check in with {w['responsible_party']}"
            })
        
        # 6. ACTION ITEMS FROM RECENT MEETINGS
        recent_meeting = conn.execute(
            """SELECT meeting_name, signals_json FROM meeting_summaries 
               WHERE signals_json IS NOT NULL
               ORDER BY meeting_date DESC LIMIT 1"""
        ).fetchone()
        if recent_meeting and recent_meeting['signals_json']:
            try:
                import json
                signals = json.loads(recent_meeting['signals_json'])
                actions = signals.get('action_items', [])
                for action in actions[:2]:
                    if action:
                        recommendations.append({
                            "priority": 5,
                            "type": "meeting_action",
                            "title": f"📋 From {recent_meeting['meeting_name']}",
                            "text": action[:60],
                            "reason": "Meeting action items often have implicit deadlines",
                            "action": "Create a ticket or complete this action"
                        })
            except:
                pass
        
        # 7. HIGH PRIORITY TODO (Only if nothing more urgent)
        if len(recommendations) < 3:
            high_priority_todo = conn.execute(
                """SELECT ticket_id, title FROM tickets 
                   WHERE status = 'todo' AND priority = 'high'
                   ORDER BY created_at ASC LIMIT 2"""
            ).fetchall()
            for t in high_priority_todo:
                recommendations.append({
                    "priority": 6,
                    "type": "todo",
                    "title": f"⭐ High Priority: {t['ticket_id']}",
                    "text": t['title'],
                    "reason": "High priority work should be started soon",
                    "action": "Start working on this ticket"
                })
        
        # 8. KNOWLEDGE GAP - Unreviewed signals
        unreviewed = conn.execute(
            """SELECT COUNT(*) as c FROM signal_status 
               WHERE status = 'pending' OR status IS NULL"""
        ).fetchone()
        if unreviewed and unreviewed['c'] > 10:
            recommendations.append({
                "priority": 7,
                "type": "knowledge",
                "title": "📥 Review Signals",
                "text": f"{unreviewed['c']} unreviewed signals",
                "reason": "Processing signals builds your knowledge base",
                "action": "Spend 10 mins reviewing and validating signals"
            })
    
    # Sort by priority and return top recommendations
    recommendations.sort(key=lambda r: r['priority'])
    return {
        "recommendations": recommendations[:5],
        "total_count": len(recommendations)
    }


def get_system_context() -> dict:
    """Get current system state for assistant context."""
    with connect() as conn:
        # Get sprint info
        sprint = conn.execute(
            "SELECT * FROM sprint_settings WHERE id = 1"
        ).fetchone()
        
        # Get current AI model
        model_row = conn.execute(
            "SELECT value FROM settings WHERE key = 'ai_model'"
        ).fetchone()
        current_model = model_row["value"] if model_row else "gpt-4o-mini"
        
        # Get ticket counts by status
        ticket_stats = conn.execute(
            """
            SELECT status, COUNT(*) as count 
            FROM tickets 
            GROUP BY status
            """
        ).fetchall()
        
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
        
        # Get today's standups for context (from standup_updates)
        today = date.today().isoformat()
        standups = conn.execute(
            """
            SELECT standup_date, content, feedback, sentiment, created_at
            FROM standup_updates
            WHERE standup_date = ?
            ORDER BY created_at DESC
            LIMIT 3
            """,
            (today,)
        ).fetchall()
        
        # Get career profile
        profile = conn.execute(
            "SELECT current_role, target_role FROM career_profile WHERE id = 1"
        ).fetchone()
    
    return {
        "sprint": dict(sprint) if sprint else None,
        "current_ai_model": current_model,
        "available_models": AVAILABLE_MODELS,
        "ticket_stats": {row['status']: row['count'] for row in ticket_stats},
        "recent_tickets": [dict(t) for t in tickets],
        "recent_meetings": [dict(m) for m in recent_meetings],
        "waiting_for": [dict(a) for a in accountability],
        "todays_standups": [dict(s) for s in standups],
        "career_profile": dict(profile) if profile else None,
        "available_pages": SYSTEM_PAGES
    }


def parse_assistant_intent(message: str, context: dict, history: list) -> dict:
    """Use LLM to understand user intent and extract structured data."""
    
    # SPECIAL HANDLING: Focus queries get smart recommendations
    focus_keywords = ['focus', 'should i do', 'what next', 'prioritize', 'work on today', 'start with']
    if any(kw in message.lower() for kw in focus_keywords):
        focus_data = get_focus_recommendations()
        recs = focus_data.get('recommendations', [])
        
        if recs:
            # Build a helpful response with prioritized recommendations
            response_parts = ["Hare Krishna! 🙏 Here's what I recommend you focus on:\n"]
            
            for i, rec in enumerate(recs[:5], 1):
                response_parts.append(f"**{i}. {rec['title']}**")
                response_parts.append(f"   {rec['text']}")
                response_parts.append(f"   _Why:_ {rec['reason']}\n")
            
            if len(recs) > 5:
                response_parts.append(f"\n_Plus {len(recs) - 5} more items to consider..._")
            
            return {
                "intent": "focus_recommendations",
                "confidence": 1.0,
                "entities": {},
                "clarifications": [],
                "response_text": "\n".join(response_parts),
                "suggested_page": "/tickets" if any(r['type'] in ['blocker', 'active', 'todo'] for r in recs) else None,
                "focus_data": focus_data
            }
        else:
            return {
                "intent": "focus_recommendations",
                "confidence": 1.0,
                "entities": {},
                "clarifications": [],
                "response_text": "Hare Krishna! 🙏 You're all caught up! No urgent items need attention right now.\n\nConsider:\n• Reviewing signals to build your knowledge base\n• Planning ahead for upcoming work\n• Taking a well-deserved break!",
                "suggested_page": None
            }
    
    # Format conversation history
    history_text = ""
    if history:
        history_text = "\n\nRecent conversation:\n"
        for msg in history[-6:]:  # Last 6 messages for context
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_text += f"{role}: {msg.get('content', '')[:200]}\n"
    
    system_prompt = f"""{CAPABILITIES}

CURRENT SYSTEM STATE:
Current AI Model: {context.get('current_ai_model', 'gpt-4o-mini')}
Available Models: {', '.join(context.get('available_models', AVAILABLE_MODELS))}

Sprint: {json.dumps(context.get('sprint', {}), indent=2) if context.get('sprint') else 'No sprint configured'}

Ticket Summary: {json.dumps(context.get('ticket_stats', {}), indent=2)}

Recent Tickets:
{json.dumps(context.get('recent_tickets', [])[:5], indent=2)}

Waiting For Items:
{json.dumps(context.get('waiting_for', []), indent=2)}

Today's Standups:
{json.dumps(context.get('todays_standups', []), indent=2)}
{history_text}

USER MESSAGE: "{message}"

Analyze the user's intent and respond with JSON:
{{
  "intent": "create_ticket" | "update_ticket" | "list_tickets" | "create_accountability" | "create_standup" | "change_model" | "update_sprint" | "reset_workflow" | "search_meetings" | "navigate" | "ask_question" | "needs_clarification" | "greeting",
  "confidence": 0.0-1.0,
  "entities": {{
    // For create_ticket: title, description, priority (low/medium/high), status (todo/in_progress/blocked/done)
    // For update_ticket: ticket_id, status, priority
    // For create_accountability: description, responsible_party, context
    // For create_standup: yesterday (what was done), today_plan (what will be done), blockers
    // For change_model: model (must be one of available models, normalize to exact name)
    // For update_sprint: sprint_name, sprint_goal (at least one required)
    // For reset_workflow: confirm (boolean)
    // For search_meetings: query (search term)
    // For navigate: target_page (key from available_pages)
  }},
  "clarifications": ["question1", "question2"],  // Only if critical info is missing
  "response_text": "Friendly response to the user...",
  "suggested_page": "/path" // Optional: suggest a page if relevant
}}

IMPORTANT GUIDELINES:
1. Be warm and helpful - you are Arjuna, greet with "Hare Krishna!" when appropriate
2. If user is lost or confused, suggest the right page to visit
3. For vague requests, make reasonable assumptions rather than asking too many questions
4. If creating tickets, generate a good title from context if not provided
5. For model changes, normalize the model name (e.g., "gpt4" → "gpt-4o", "claude" → "claude-3-sonnet")
6. For sprint updates, only update fields that are explicitly mentioned
7. Always explain what you did or will do
8. When user asks about app features, explain them clearly using your knowledge"""

    response = ask_llm(system_prompt, model="gpt-4o-mini")
    
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
        # Focus recommendations - already computed, just return success
        if intent == "focus_recommendations":
            return {
                "success": True, 
                "action": "focus_recommendations",
                "focus_data": intent_data.get("focus_data", {})
            }
        
        if intent == "create_ticket":
            with connect() as conn:
                ticket_id = f"AJ-{datetime.now().strftime('%y%m%d-%H%M')}"
                conn.execute(
                    """
                    INSERT INTO tickets (ticket_id, title, description, status, priority)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        ticket_id,
                        entities.get("title", "Untitled Task"),
                        entities.get("description", ""),
                        entities.get("status", "backlog"),
                        entities.get("priority", "medium")
                    )
                )
                return {"success": True, "ticket_id": ticket_id, "action": "create_ticket"}
        
        elif intent == "update_ticket":
            with connect() as conn:
                ticket_id = entities.get("ticket_id")
                if not ticket_id:
                    return {"success": False, "error": "No ticket ID provided"}
                
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
                return {"success": True, "action": "update_ticket"}
        
        elif intent == "list_tickets":
            with connect() as conn:
                status_filter = entities.get("status")
                if status_filter:
                    tickets = conn.execute(
                        "SELECT ticket_id, title, status, priority FROM tickets WHERE status = ? ORDER BY created_at DESC LIMIT 10",
                        (status_filter,)
                    ).fetchall()
                else:
                    tickets = conn.execute(
                        "SELECT ticket_id, title, status, priority FROM tickets ORDER BY created_at DESC LIMIT 10"
                    ).fetchall()
                return {"success": True, "tickets": [dict(t) for t in tickets], "action": "list_tickets"}
        
        elif intent == "create_accountability":
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO accountability_items (description, responsible_party, context, source_type)
                    VALUES (?, ?, ?, 'assistant')
                    """,
                    (
                        entities.get("description", ""),
                        entities.get("responsible_party", "Unknown"),
                        entities.get("context", "")
                    )
                )
                return {"success": True, "action": "create_accountability"}
        
        elif intent == "create_standup":
            # Store standup entries in the shared standup_updates table used by the Career hub
            from datetime import date as _date
            standup_date = _date.today().isoformat()
            content_parts = []
            if entities.get("yesterday"):
                content_parts.append(f"Yesterday: {entities['yesterday']}")
            if entities.get("today_plan"):
                content_parts.append(f"Today: {entities['today_plan']}")
            if entities.get("blockers"):
                content_parts.append(f"Blockers: {entities['blockers']}")
            content = "\n".join(content_parts) or intent_data.get("response_text") or "Standup update"

            with connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO standup_updates (standup_date, content, feedback, sentiment, key_themes)
                    VALUES (?, ?, NULL, 'neutral', '')
                    """,
                    (standup_date, content)
                )
                standup_id = cur.lastrowid
            return {"success": True, "action": "create_standup", "standup_id": standup_id}
        
        elif intent == "navigate":
            target = entities.get("target_page")
            if target and target in SYSTEM_PAGES:
                return {"success": True, "action": "navigate", "navigate_to": SYSTEM_PAGES[target]["path"]}
            return {"success": True, "action": "navigate"}
        
        elif intent == "change_model":
            model = entities.get("model", "").lower().strip()
            # Normalize model names
            model_map = {
                "gpt4": "gpt-4o",
                "gpt-4": "gpt-4o",
                "gpt4o": "gpt-4o",
                "gpt-4o": "gpt-4o",
                "gpt4omini": "gpt-4o-mini",
                "gpt-4o-mini": "gpt-4o-mini",
                "gpt4mini": "gpt-4o-mini",
                "mini": "gpt-4o-mini",
                "gpt4turbo": "gpt-4-turbo",
                "gpt-4-turbo": "gpt-4-turbo",
                "turbo": "gpt-4-turbo",
                "gpt35": "gpt-3.5-turbo",
                "gpt-3.5": "gpt-3.5-turbo",
                "gpt-3.5-turbo": "gpt-3.5-turbo",
                "claude": "claude-3-sonnet",
                "claude3": "claude-3-sonnet",
                "claudesonnet": "claude-3-sonnet",
                "claude-3-sonnet": "claude-3-sonnet",
                "sonnet": "claude-3-sonnet",
                "claudeopus": "claude-3-opus",
                "claude-3-opus": "claude-3-opus",
                "opus": "claude-3-opus",
                "claudehaiku": "claude-3-haiku",
                "claude-3-haiku": "claude-3-haiku",
                "haiku": "claude-3-haiku",
                "claude-sonnet-4": "claude-sonnet-4",
                "sonnet4": "claude-sonnet-4",
                "claude-opus-4": "claude-opus-4",
                "opus4": "claude-opus-4",
            }
            normalized = model_map.get(model.replace(" ", "").replace("-", ""), model)
            
            # Check if valid model
            if normalized not in AVAILABLE_MODELS:
                return {"success": False, "error": f"Unknown model: {model}. Available: {', '.join(AVAILABLE_MODELS)}"}
            
            with connect() as conn:
                conn.execute("""
                    INSERT INTO settings (key, value) 
                    VALUES ('ai_model', ?)
                    ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')
                """, (normalized, normalized))
            
            return {"success": True, "action": "change_model", "model": normalized}
        
        elif intent == "update_sprint":
            sprint_name = entities.get("sprint_name")
            sprint_goal = entities.get("sprint_goal")
            
            if not sprint_name and not sprint_goal:
                return {"success": False, "error": "No sprint name or goal provided"}
            
            with connect() as conn:
                updates = []
                params = []
                if sprint_name:
                    updates.append("sprint_name = ?")
                    params.append(sprint_name)
                if sprint_goal:
                    updates.append("sprint_goal = ?")
                    params.append(sprint_goal)
                
                if updates:
                    params.append(1)  # id = 1
                    conn.execute(
                        f"UPDATE sprint_settings SET {', '.join(updates)} WHERE id = ?",
                        params
                    )
            
            return {"success": True, "action": "update_sprint", "sprint_name": sprint_name, "sprint_goal": sprint_goal}
        
        elif intent == "reset_workflow":
            modes = ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g']
            with connect() as conn:
                for mode in modes:
                    conn.execute(
                        "DELETE FROM settings WHERE key = ?",
                        (f"workflow_progress_{mode}",)
                    )
            return {"success": True, "action": "reset_workflow"}
        
        elif intent == "search_meetings":
            query = entities.get("query", "")
            with connect() as conn:
                meetings = conn.execute(
                    """
                    SELECT meeting_name, meeting_date, signals_json
                    FROM meeting_summaries
                    WHERE meeting_name LIKE ? OR raw_notes LIKE ? OR signals_json LIKE ?
                    ORDER BY meeting_date DESC
                    LIMIT 5
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%")
                ).fetchall()
            return {"success": True, "action": "search_meetings", "meetings": [dict(m) for m in meetings]}
        
        elif intent in ("ask_question", "greeting", "needs_clarification"):
            return {"success": True, "action": intent}
        
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
        
        # Parse user intent with conversation history
        intent_data = parse_assistant_intent(message, context, conversation_history)
        
        # If needs clarification, return questions
        if intent_data.get("clarifications") and intent_data.get("intent") == "needs_clarification":
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
        
        return JSONResponse({
            "response": response_text,
            "success": True,
            "action": action,
            "result": execution_result,
            "suggested_page": suggested or navigate_to,
            "follow_ups": follow_ups
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
