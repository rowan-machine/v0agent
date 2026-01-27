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
from ..infrastructure.supabase_client import get_supabase_client
# llm.ask removed - use lazy imports inside functions for backward compatibility

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
    
    supabase = get_supabase_client()
    if not supabase:
        return {"recommendations": [], "total_count": 0}
    
    # 1. BLOCKED TICKETS (Highest Priority)
    blocked_result = supabase.table("tickets").select("ticket_id, title, description").eq("status", "blocked").order("priority", desc=True).order("updated_at", desc=True).limit(3).execute()
    blocked = blocked_result.data or []
    if blocked:
        for t in blocked:
            recommendations.append({
                "priority": 1,
                "type": "blocker",
                "title": f"🚧 Unblock: {t.get('ticket_id')}",
                "text": t.get('title', ''),
                "reason": "Blocked tickets prevent all downstream work",
                "action": f"Review and unblock {t.get('ticket_id')}"
            })
    
    # 2. HIGH PRIORITY IN-PROGRESS (Get things done)
    in_progress_result = supabase.table("tickets").select("ticket_id, title").eq("status", "in_progress").order("priority", desc=True).order("updated_at").limit(2).execute()
    in_progress = in_progress_result.data or []
    if in_progress:
        for t in in_progress:
            recommendations.append({
                "priority": 2,
                "type": "active",
                "title": f"🏃 Complete: {t.get('ticket_id')}",
                "text": t.get('title', ''),
                "reason": "Finishing in-progress work reduces context switching",
                "action": "Continue working on this ticket"
            })
    
    # 3. SPRINT DEADLINE CHECK
    sprint_result = supabase.table("sprint_settings").select("*").eq("id", 1).execute()
    sprints = sprint_result.data or []
    if sprints and sprints[0].get('start_date'):
        sprint = sprints[0]
        try:
            start = datetime.strptime(sprint['start_date'], '%Y-%m-%d')
            length = sprint.get('length_days') or 14
            end = start + timedelta(days=length)
            days_left = (end - datetime.now()).days
            
            if days_left <= 3 and days_left > 0:
                todo_result = supabase.table("tickets").select("id", count="exact").eq("status", "todo").execute()
                todo_count = todo_result.count or 0
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
    
    # 4. WAITING-FOR ITEMS (Follow up on dependencies)
    waiting_result = supabase.table("accountability_items").select("description, responsible_party").eq("status", "waiting").order("created_at").limit(2).execute()
    waiting = waiting_result.data or []
    for w in waiting:
        recommendations.append({
            "priority": 4,
            "type": "waiting",
            "title": f"⏳ Follow up: {w.get('responsible_party', 'Unknown')}",
            "text": (w.get('description') or '')[:60],
            "reason": "Dependencies on others can become blockers",
            "action": f"Check in with {w.get('responsible_party', 'Unknown')}"
        })
    
    # 5. ACTION ITEMS FROM RECENT MEETINGS
    recent_meeting_result = supabase.table("meetings").select("meeting_name, signals").not_.is_("signals", "null").order("meeting_date", desc=True).limit(1).execute()
    recent_meetings = recent_meeting_result.data or []
    if recent_meetings and recent_meetings[0].get('signals'):
        recent_meeting = recent_meetings[0]
        try:
            import json
            signals = json.loads(recent_meeting['signals']) if isinstance(recent_meeting['signals'], str) else recent_meeting['signals']
            actions = signals.get('action_items', [])
            for action in actions[:2]:
                if action:
                    recommendations.append({
                        "priority": 5,
                        "type": "meeting_action",
                        "title": f"📋 From {recent_meeting.get('meeting_name', 'Meeting')}",
                        "text": (action if isinstance(action, str) else str(action))[:60],
                        "reason": "Meeting action items often have implicit deadlines",
                        "action": "Create a ticket or complete this action"
                    })
        except:
            pass
    
    # 6. HIGH PRIORITY TODO (Only if nothing more urgent)
    if len(recommendations) < 3:
        high_priority_result = supabase.table("tickets").select("ticket_id, title").eq("status", "todo").eq("priority", "high").order("created_at").limit(2).execute()
        high_priority_todo = high_priority_result.data or []
        for t in high_priority_todo:
            recommendations.append({
                "priority": 6,
                "type": "todo",
                "title": f"⭐ High Priority: {t.get('ticket_id')}",
                "text": t.get('title', ''),
                "reason": "High priority work should be started soon",
                "action": "Start working on this ticket"
            })
    
    # 7. KNOWLEDGE GAP - Unreviewed signals
    unreviewed_result = supabase.table("signal_status").select("id", count="exact").or_("status.eq.pending,status.is.null").execute()
    unreviewed_count = unreviewed_result.count or 0
    if unreviewed_count > 10:
        recommendations.append({
            "priority": 7,
            "type": "knowledge",
            "title": "📥 Review Signals",
            "text": f"{unreviewed_count} unreviewed signals",
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
    supabase = get_supabase_client()
    if not supabase:
        return {
            "sprint": None,
            "current_ai_model": "gpt-4o-mini",
            "available_models": AVAILABLE_MODELS,
            "ticket_stats": {},
            "recent_tickets": [],
            "recent_meetings": [],
            "waiting_for": [],
            "todays_standups": [],
            "career_profile": None,
            "available_pages": SYSTEM_PAGES
        }
    
    # Get sprint info
    sprint_result = supabase.table("sprint_settings").select("*").eq("id", 1).execute()
    sprints = sprint_result.data or []
    sprint = sprints[0] if sprints else None
    
    # Get current AI model
    model_result = supabase.table("settings").select("value").eq("key", "ai_model").execute()
    models = model_result.data or []
    current_model = models[0]["value"] if models else "gpt-4o-mini"
    
    # Get ticket counts by status - need to do manual grouping
    tickets_result = supabase.table("tickets").select("status").execute()
    tickets_all = tickets_result.data or []
    ticket_stats = {}
    for t in tickets_all:
        status = t.get("status", "unknown")
        ticket_stats[status] = ticket_stats.get(status, 0) + 1
    
    # Get recent tickets
    recent_result = supabase.table("tickets").select("ticket_id, title, status, priority").order("created_at", desc=True).limit(10).execute()
    recent_tickets = recent_result.data or []
    
    # Get recent signals
    meetings_result = supabase.table("meetings").select("meeting_name, signals, meeting_date").not_.is_("signals", "null").order("meeting_date", desc=True).limit(3).execute()
    recent_meetings = meetings_result.data or []

    # Get accountability items
    accountability_result = supabase.table("accountability_items").select("description, responsible_party, status").eq("status", "waiting").limit(5).execute()
    waiting_for = accountability_result.data or []
    
    # Get today's standups for context
    today = date.today().isoformat()
    standups_result = supabase.table("standup_updates").select("standup_date, content, feedback, sentiment, created_at").eq("standup_date", today).order("created_at", desc=True).limit(3).execute()
    todays_standups = standups_result.data or []
    
    # Get career profile
    profile_result = supabase.table("career_profile").select("current_role, target_role").eq("id", 1).execute()
    profiles = profile_result.data or []
    career_profile = profiles[0] if profiles else None
    
    return {
        "sprint": sprint,
        "current_ai_model": current_model,
        "available_models": AVAILABLE_MODELS,
        "ticket_stats": ticket_stats,
        "recent_tickets": recent_tickets,
        "recent_meetings": recent_meetings,
        "waiting_for": waiting_for,
        "todays_standups": todays_standups,
        "career_profile": career_profile,
        "available_pages": SYSTEM_PAGES
    }


async def parse_assistant_intent(message: str, context: dict, history: list, thread_id: str = None) -> dict:
    """
    Use LLM to understand user intent and extract structured data.
    
    Args:
        message: User's message
        context: System context  
        history: Conversation history
        thread_id: Optional thread ID for LangSmith tracing
    
    Returns:
        Dict with intent, entities, response_text, and run_id for feedback
    """
    
    # SPECIAL HANDLING: 1-on-1 prep and work status queries → use ArjunaAgent
    oneone_keywords = ['1-on-1', '1:1', 'one-on-one', 'one on one', '1 on 1', 
                       'working on', 'top 3', 'need help', 'blockers', 'blocked',
                       'observations', 'feedback', 'discuss', 'prepare for']
    if any(kw in message.lower() for kw in oneone_keywords):
        from ..agents.arjuna import get_arjuna_agent
        
        agent = get_arjuna_agent()
        try:
            result = await agent.quick_ask(query=message)
            
            if result.get("success"):
                return {
                    "intent": "ask_question",
                    "confidence": 1.0,
                    "entities": {},
                    "clarifications": [],
                    "response_text": result.get("response", ""),
                    "suggested_page": None,
                    "run_id": agent.last_run_id,
                }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"ArjunaAgent quick_ask failed: {e}")
            # Fall through to normal handling
    
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

    # Lazy import for backward compatibility
    from ..llm import ask as ask_llm
    response = ask_llm(system_prompt, model="gpt-4o-mini", thread_id=thread_id)
    
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
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            ticket_id = f"AJ-{datetime.now().strftime('%y%m%d-%H%M')}"
            supabase.table("tickets").insert({
                "ticket_id": ticket_id,
                "title": entities.get("title", "Untitled Task"),
                "description": entities.get("description", ""),
                "status": entities.get("status", "backlog"),
                "priority": entities.get("priority", "medium")
            }).execute()
            return {"success": True, "ticket_id": ticket_id, "action": "create_ticket"}
        
        elif intent == "update_ticket":
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            ticket_id = entities.get("ticket_id")
            if not ticket_id:
                return {"success": False, "error": "No ticket ID provided"}
            
            update_data = {}
            if "status" in entities:
                update_data["status"] = entities["status"]
            if "priority" in entities:
                update_data["priority"] = entities["priority"]
            
            if update_data:
                supabase.table("tickets").update(update_data).eq("ticket_id", ticket_id).execute()
            return {"success": True, "action": "update_ticket"}
        
        elif intent == "list_tickets":
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            status_filter = entities.get("status")
            query = supabase.table("tickets").select("ticket_id, title, status, priority")
            if status_filter:
                query = query.eq("status", status_filter)
            result = query.order("created_at", desc=True).limit(10).execute()
            tickets = result.data or []
            return {"success": True, "tickets": tickets, "action": "list_tickets"}
        
        elif intent == "create_accountability":
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            supabase.table("accountability_items").insert({
                "description": entities.get("description", ""),
                "responsible_party": entities.get("responsible_party", "Unknown"),
                "context": entities.get("context", ""),
                "source_type": "assistant"
            }).execute()
            return {"success": True, "action": "create_accountability"}
        
        elif intent == "create_standup":
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
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

            result = supabase.table("standup_updates").insert({
                "standup_date": standup_date,
                "content": content,
                "feedback": None,
                "sentiment": "neutral",
                "key_themes": ""
            }).execute()
            standup_id = result.data[0]["id"] if result.data else None
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
            
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            supabase.table("settings").upsert({"key": "ai_model", "value": normalized}, on_conflict="key").execute()
            
            return {"success": True, "action": "change_model", "model": normalized}
        
        elif intent == "update_sprint":
            sprint_name = entities.get("sprint_name")
            sprint_goal = entities.get("sprint_goal")
            
            if not sprint_name and not sprint_goal:
                return {"success": False, "error": "No sprint name or goal provided"}
            
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            
            update_data = {}
            if sprint_name:
                update_data["sprint_name"] = sprint_name
            if sprint_goal:
                update_data["sprint_goal"] = sprint_goal
            
            if update_data:
                supabase.table("sprint_settings").update(update_data).eq("id", 1).execute()
            
            return {"success": True, "action": "update_sprint", "sprint_name": sprint_name, "sprint_goal": sprint_goal}
        
        elif intent == "reset_workflow":
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            modes = ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g']
            for mode in modes:
                supabase.table("settings").delete().eq("key", f"workflow_progress_{mode}").execute()
            return {"success": True, "action": "reset_workflow"}
        
        elif intent == "search_meetings":
            supabase = get_supabase_client()
            if not supabase:
                return {"success": False, "error": "Database not configured"}
            query_text = entities.get("query", "")
            result = supabase.table("meetings").select("meeting_name, meeting_date, signals").or_(f"meeting_name.ilike.%{query_text}%,raw_text.ilike.%{query_text}%,synthesized_notes.ilike.%{query_text}%").order("meeting_date", desc=True).limit(5).execute()
            meetings = result.data or []
            return {"success": True, "action": "search_meetings", "meetings": meetings}
        
        elif intent in ("ask_question", "greeting", "needs_clarification"):
            return {"success": True, "action": intent}
        
        return {"success": True, "intent": intent}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


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
        intent_data = await parse_assistant_intent(message, context, conversation_history, thread_id=thread_id)
        
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
        
        # Execute the intent
        execution_result = execute_intent(intent_data)
        
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
