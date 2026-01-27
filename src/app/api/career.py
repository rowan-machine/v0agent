# src/app/api/career.py
"""
Career API Routes - FastAPI endpoints for career development features.

⚠️  DEPRECATED: This file is being replaced by the domain-driven structure.
    New implementation: src/app/domains/career/api/
    New routes available at: /api/domains/career/*
    
    This file will be removed in a future release.
    Please migrate to the new domain-based routes.

This module delegates to CareerCoachAgent (Checkpoint 2.3) for AI-powered features,
maintaining backward compatibility through adapter functions.

Migration Status:
- CareerCoachAgent: src/app/agents/career_coach.py (new agent implementation)
- This file: Adapters + FastAPI routes (will be slimmed down over time)
- FULLY MIGRATED TO SUPABASE (January 2026)
- DOMAIN DECOMPOSITION: See src/app/domains/career/ (January 2026)
"""
import warnings
warnings.warn(
    "career.py is deprecated. Use domains/career/api instead. "
    "Routes available at /api/domains/career/*",
    DeprecationWarning,
    stacklevel=2
)

# Imports and router definition moved to top
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from ..infrastructure.supabase_client import get_supabase_client
from ..services import ticket_service
# llm.ask removed - use lazy imports inside functions for backward compatibility
import json
import logging

logger = logging.getLogger(__name__)

# Import from new CareerCoach agent (Checkpoint 2.3)
from ..agents.career_coach import (
    CareerCoachAgent,
    get_career_coach_agent,
    CAREER_REPO_CAPABILITIES,
    format_capabilities_context,
    # Adapter functions
    get_career_capabilities as agent_get_capabilities,
    career_chat_adapter,
    generate_suggestions_adapter,
    analyze_standup_adapter,
)

# Import Supabase sync helpers for dual-write
from .career_supabase_helper import (
    sync_suggestion_to_supabase,
    sync_memory_to_supabase,
    sync_standup_to_supabase,
    sync_chat_to_supabase,
    sync_skill_to_supabase,
)

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

# NOTE: /api/signals/status endpoint is in main.py

def get_code_locker_code_for_sprint_tickets_supabase(supabase, tickets, max_lines=40, max_chars=2000):
    """Return a dict: {ticket_id: {filename: code}} for latest code locker entries for each file in current sprint tickets (Supabase version)."""
    code_by_ticket = {}
    for t in tickets:
        # Handle dict objects from Supabase
        tid = t.get('id')
        ticket_code = t.get('ticket_id')
        if not tid or not ticket_code:
            continue
        # Get all filenames for this ticket from ticket_files
        files_result = supabase.table("ticket_files").select("filename").eq("ticket_id", tid).execute()
        files = files_result.data or []
        code_by_ticket[ticket_code] = {}
        for f in files:
            fname = f.get('filename')
            if not fname:
                continue
            # Get latest code locker entry for this file/ticket
            row_result = supabase.table("code_locker").select("content").eq("filename", fname).eq("ticket_id", tid).order("version", desc=True).limit(1).execute()
            rows = row_result.data or []
            if rows and rows[0].get('content'):
                code = rows[0]['content']
                # Truncate for brevity
                lines = code.splitlines()
                if len(lines) > max_lines:
                    code = '\n'.join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} lines total)"
                if len(code) > max_chars:
                    code = code[:max_chars] + f"\n... (truncated, {len(rows[0]['content'])} chars total)"
                code_by_ticket[ticket_code][fname] = code
    return code_by_ticket


# CAREER_REPO_CAPABILITIES - Now imported from agents/career_coach.py (Checkpoint 2.3)
# Using the imported version for single source of truth.

# _format_capabilities_context - Now imported as format_capabilities_context from agents/career_coach.py
# Local function removed to avoid duplication.


def _load_career_summary(supabase):
    result = supabase.table("career_chat_updates").select("summary").neq("summary", "").not_.is_("summary", "null").order("created_at", desc=True).limit(1).execute()
    rows = result.data or []
    return rows[0]["summary"] if rows else None


def _load_overlay_context(supabase):
    meetings_result = supabase.table("meetings").select("meeting_name, synthesized_notes").order("meeting_date", desc=True, nullsfirst=False).limit(3).execute()
    meetings = meetings_result.data or []
    
    docs_result = supabase.table("documents").select("source, content").order("document_date", desc=True, nullsfirst=False).limit(3).execute()
    docs = docs_result.data or []
    
    tickets_result = supabase.table("tickets").select("id, ticket_id, title, description, status").in_("status", ["todo", "in_progress", "in_review", "blocked"]).order("created_at", desc=True).limit(5).execute()
    tickets = tickets_result.data or []

    # Get code locker code for these tickets
    code_locker_context = get_code_locker_code_for_sprint_tickets_supabase(supabase, tickets)

    meeting_text = "\n".join([
        f"- {m.get('meeting_name', 'Unknown')}: {(m.get('synthesized_notes') or '')[:500]}" for m in meetings
    ]) or "No recent meetings."
    doc_text = "\n".join([
        f"- {d.get('source', 'Unknown')}: {(d.get('content') or '')[:400]}" for d in docs
    ]) or "No recent documents."
    ticket_text = "\n".join([
        f"- {t.get('ticket_id', 'Unknown')} {t.get('title', '')} ({t.get('status', 'unknown')})" for t in tickets
    ]) or "No active tickets."

    code_locker_text = "\n".join([
        f"Ticket {tid}:\n" + "\n".join([f"  {fname}:\n    {code}" for fname, code in files.items()])
        for tid, files in code_locker_context.items()
    ]) or "No code locker entries."

    return {
        "meetings": meeting_text,
        "documents": doc_text,
        "tickets": ticket_text,
        "code_locker": code_locker_text,
    }


# NOTE: router and templates are defined once at the top of this file


@router.delete("/api/career/standups/{standup_id}")
async def delete_standup(standup_id: int):
    """Delete a standup update by ID."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    supabase.table("standup_updates").delete().eq("id", standup_id).execute()
    return JSONResponse({"status": "ok"})


@router.get("/api/career/profile")
async def get_career_profile(request: Request):
    """Get the current career profile."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("career_profile").select("*").eq("id", 1).execute()
    profiles = result.data or []
    
    if profiles:
        profile = profiles[0]
        return JSONResponse({
            "current_role": profile.get("current_role"),
            "target_role": profile.get("target_role"),
            "strengths": profile.get("strengths"),
            "weaknesses": profile.get("weaknesses"),
            "interests": profile.get("interests"),
            "goals": profile.get("goals"),
            "certifications": profile.get("certifications"),
            "education": profile.get("education"),
            "years_experience": profile.get("years_experience"),
            "preferred_work_style": profile.get("preferred_work_style"),
            "industry_focus": profile.get("industry_focus"),
            "leadership_experience": profile.get("leadership_experience"),
            "notable_projects": profile.get("notable_projects"),
            "learning_priorities": profile.get("learning_priorities"),
            "career_timeline": profile.get("career_timeline"),
            # New fields
            "technical_specializations": profile.get("technical_specializations"),
            "soft_skills": profile.get("soft_skills"),
            "work_achievements": profile.get("work_achievements"),
            "career_values": profile.get("career_values"),
            "short_term_goals": profile.get("short_term_goals"),
            "long_term_goals": profile.get("long_term_goals"),
            "mentorship": profile.get("mentorship"),
            "networking": profile.get("networking"),
            "languages": profile.get("languages"),
        })
    return JSONResponse({}, status_code=404)


@router.post("/api/career/profile")
async def update_career_profile(request: Request):
    """Update the career profile."""
    data = await request.json()
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    profile_data = {
        "id": 1,
        "current_role": data.get("current_role"),
        "target_role": data.get("target_role"),
        "strengths": data.get("strengths"),
        "weaknesses": data.get("weaknesses"),
        "interests": data.get("interests"),
        "goals": data.get("goals"),
        "certifications": data.get("certifications"),
        "education": data.get("education"),
        "years_experience": data.get("years_experience"),
        "preferred_work_style": data.get("preferred_work_style"),
        "industry_focus": data.get("industry_focus"),
        "leadership_experience": data.get("leadership_experience"),
        "notable_projects": data.get("notable_projects"),
        "learning_priorities": data.get("learning_priorities"),
        "career_timeline": data.get("career_timeline"),
        "technical_specializations": data.get("technical_specializations"),
        "soft_skills": data.get("soft_skills"),
        "work_achievements": data.get("work_achievements"),
        "career_values": data.get("career_values"),
        "short_term_goals": data.get("short_term_goals"),
        "long_term_goals": data.get("long_term_goals"),
        "mentorship": data.get("mentorship"),
        "networking": data.get("networking"),
        "languages": data.get("languages"),
    }
    
    supabase.table("career_profile").upsert(profile_data, on_conflict="id").execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/api/career/suggestions")
async def get_career_suggestions(request: Request, limit: int = Query(10, ge=1, le=50)):
    """Get career development suggestions."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([], status_code=200)
    
    result = supabase.table("career_suggestions").select("*").in_(
        "status", ["suggested", "accepted", "in_progress", "dismissed", "completed"]
    ).order("created_at", desc=True).limit(limit).execute()
    
    suggestions = result.data or []
    # Sort by status priority in Python
    status_order = {"in_progress": 1, "accepted": 2, "suggested": 3, "dismissed": 4, "completed": 5}
    suggestions.sort(key=lambda s: status_order.get(s.get("status", "suggested"), 3))
    
    return JSONResponse(suggestions)


@router.post("/api/career/generate-suggestions")
async def generate_career_suggestions(request: Request):
    """Generate new AI-powered career development suggestions.
    
    Delegates to CareerCoachAgent via adapter (Checkpoint 2.3).
    """
    try:
        try:
            data = await request.json()
        except Exception:
            data = {}
        include_context = bool(data.get("include_context", True))

        supabase = get_supabase_client()
        if not supabase:
            return JSONResponse({"error": "Database not configured"}, status_code=500)
        
        # Get career profile
        profile_result = supabase.table("career_profile").select("*").eq("id", 1).execute()
        profiles = profile_result.data or []
        if not profiles:
            return JSONResponse({"error": "No career profile found"}, status_code=404)
        profile = profiles[0]
        
        overlay_context = _load_overlay_context(supabase) if include_context else None
        
        # Delegate to CareerCoachAgent adapter
        result = await generate_suggestions_adapter(
            profile=profile,
            context=overlay_context,
            include_context=include_context,
            db_connection=None,  # Using Supabase now
        )
        
        if result.get("status") == "error":
            return JSONResponse({"error": result.get("error", "Unknown error")}, status_code=500)
        
        # Insert suggestions into database for persistence
        suggestions_data = result.get("suggestions", [])
        created_ids = []
        for sugg in suggestions_data:
            insert_data = {
                "suggestion_type": sugg.get('suggestion_type', 'skill_building'),
                "title": sugg.get('title', 'Growth Opportunity'),
                "description": sugg.get('description', ''),
                "rationale": sugg.get('rationale', ''),
                "difficulty": sugg.get('difficulty', 'intermediate'),
                "time_estimate": sugg.get('time_estimate', 'varies'),
                "related_goal": sugg.get('related_goal', '')
            }
            insert_result = supabase.table("career_suggestions").insert(insert_data).execute()
            if insert_result.data:
                created_ids.append(insert_result.data[0].get("id"))
            
            # Sync to Supabase (fire-and-forget) - now redundant but kept for compatibility
            sync_suggestion_to_supabase(sugg)
        
        return JSONResponse({
            "status": "ok",
            "count": len(created_ids),
            "ids": created_ids
        })
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/career/chat/history")
async def get_career_chat_history(request: Request, limit: int = Query(20, ge=1, le=100)):
    """Return recent career chat messages."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    result = supabase.table("career_chat_updates").select(
        "message, response, summary, created_at"
    ).order("created_at", desc=True).limit(limit).execute()
    
    rows = result.data or []
    return JSONResponse(rows[::-1])


@router.get("/api/career/chat/summary")
async def get_career_chat_summary(request: Request):
    """Return the latest career status summary."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"summary": ""})
    
    summary = _load_career_summary(supabase) or ""
    return JSONResponse({"summary": summary})


@router.get("/api/career/capabilities")
async def get_career_capabilities_endpoint(request: Request):
    """Return repo capabilities and unlocks for the career agent.
    
    Delegates to CareerCoachAgent (Checkpoint 2.3).
    """
    return JSONResponse(agent_get_capabilities())


@router.post("/api/career/chat")
async def career_chat(request: Request):
    """Career status chat and summary update.
    
    Delegates to CareerCoachAgent via adapter (Checkpoint 2.3).
    """
    data = await request.json()
    message = (data.get("message") or "").strip()
    include_context = bool(data.get("include_context", True))
    if not message:
        return JSONResponse({"error": "Message is required"}, status_code=400)

    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    profile_result = supabase.table("career_profile").select("*").eq("id", 1).execute()
    profiles = profile_result.data or []
    if not profiles:
        return JSONResponse({"error": "No career profile found"}, status_code=404)
    profile = profiles[0]

    overlay_context = _load_overlay_context(supabase) if include_context else None

    # Delegate to CareerCoachAgent adapter
    try:
        result = await career_chat_adapter(
            message=message,
            profile=profile,
            context=overlay_context,
            include_context=include_context,
            db_connection=None,  # Using Supabase now
        )
        
        # Store in chat history for persistence
        supabase.table("career_chat_updates").insert({
            "message": message,
            "response": result.get("response", ""),
            "summary": result.get("summary", "")
        }).execute()
        
        # Sync to Supabase (fire-and-forget) - now redundant but kept for compatibility
        sync_chat_to_supabase(
            message=message,
            response=result.get("response", ""),
            summary=result.get("summary", "")
        )
        
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": f"AI Error: {str(e)}"}, status_code=500)


# ----------------------
# Career Insights API
# ----------------------

@router.post("/api/career/generate-insights")
async def generate_career_insights(request: Request):
    """Generate AI insights based on skills, projects, and profile."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Gather context - handle missing tables gracefully
    profile_result = supabase.table("career_profile").select("*").eq("id", 1).execute()
    profile = profile_result.data[0] if profile_result.data else None
    
    try:
        skills_result = supabase.table("skill_tracker").select(
            "skill_name, category, proficiency_level"
        ).gt("proficiency_level", 0).order("proficiency_level", desc=True).limit(15).execute()
        skills = skills_result.data or []
    except:
        skills = []
    
    # Check if completed_projects_bank table exists
    try:
        projects_result = supabase.table("completed_projects_bank").select(
            "title, description, technologies, impact"
        ).order("completed_date", desc=True).limit(10).execute()
        projects = projects_result.data or []
    except:
        projects = []
    
    # Check if ai_implementation_memories table exists
    try:
        ai_mem_result = supabase.table("ai_implementation_memories").select(
            "title, description, technologies"
        ).order("created_at", desc=True).limit(5).execute()
        ai_memories = ai_mem_result.data or []
    except:
        ai_memories = []
    
    # Format context
    profile_ctx = f"""
Current Role: {profile.get('current_role', 'Not set') if profile else 'Not set'}
Target Role: {profile.get('target_role', 'Not set') if profile else 'Not set'}
Strengths: {profile.get('strengths', 'Not set') if profile else 'Not set'}
Goals: {profile.get('goals', 'Not set') if profile else 'Not set'}
""" if profile else "No profile set"
    
    skills_ctx = "\n".join([f"- {s.get('skill_name')} ({s.get('category')}): {s.get('proficiency_level')}%" for s in skills]) if skills else "No skills tracked"
    projects_ctx = "\n".join([f"- {p.get('title')}: {(p.get('description') or '')[:100]}..." for p in projects]) if projects else "No projects"
    ai_ctx = "\n".join([f"- {m.get('title')}: {m.get('technologies')}" for m in ai_memories]) if ai_memories else "No AI implementations"
    
    prompt = f"""Based on this career profile and tracked data, generate a concise career insight summary (3-5 bullet points max).

PROFILE:
{profile_ctx}

TOP SKILLS:
{skills_ctx}

RECENT PROJECTS:
{projects_ctx}

AI/ML IMPLEMENTATIONS:
{ai_ctx}

Generate actionable insights in this format:
## 🎯 Career Focus
- Key strength to leverage
- Skill gap to address  
- Next recommended step

Keep it brief, actionable, and encouraging. Use markdown formatting."""

    # Use CareerCoach agent for proper tracing
    from ..agents.career_coach import get_career_coach_agent
    agent = get_career_coach_agent(db_connection=None)
    insights = await agent.ask_llm(
        prompt=prompt,
        task_type="career_insights",
    )
    
    # Persist insights to career_profile for reload
    try:
        supabase.table("career_profile").update({
            "last_insights": insights
        }).eq("id", 1).execute()
    except Exception as e:
        logger.warning(f"Could not persist insights: {e}")
    
    return JSONResponse({
        "status": "ok", 
        "insights": insights, 
        "run_id": agent.last_run_id
    })


@router.get("/api/career/insights")
async def get_career_insights():
    """Get the last saved career insights."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"insights": None})
    
    result = supabase.table("career_profile").select("last_insights, updated_at").eq("id", 1).execute()
    if result.data and result.data[0].get("last_insights"):
        return JSONResponse({
            "insights": result.data[0]["last_insights"],
            "generated_at": result.data[0].get("updated_at")
        })
    return JSONResponse({"insights": None})


# ----------------------
# Career Tweaks Safe API
# ----------------------

@router.get("/api/career/tweaks")
async def get_career_tweaks(request: Request):
    """Get saved career tweaks."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"tweaks": []})
    
    result = supabase.table("career_tweaks").select("*").order("created_at", desc=True).execute()
    return JSONResponse({"tweaks": result.data or []})


@router.post("/api/career/tweaks")
async def save_career_tweak(request: Request):
    """Save a new career tweak."""
    data = await request.json()
    content = (data.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("career_tweaks").insert({"content": content}).execute()
    return JSONResponse({"status": "ok"})


@router.delete("/api/career/tweaks/{tweak_id}")
async def delete_career_tweak(tweak_id: int):
    """Delete a career tweak."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("career_tweaks").delete().eq("id", tweak_id).execute()
    return JSONResponse({"status": "ok"})


@router.post("/api/career/suggestions/{suggestion_id}/status")
async def update_suggestion_status(suggestion_id: int, request: Request):
    """Update the status of a career suggestion."""
    data = await request.json()
    status = data.get("status")
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("career_suggestions").update({
        "status": status
    }).eq("id", suggestion_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.post("/api/career/suggestions/{suggestion_id}/to-ticket")
async def convert_suggestion_to_ticket(suggestion_id: int, request: Request):
    """Convert a career suggestion to a ticket."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return JSONResponse({"error": "Database not configured"}, status_code=500)
        
        suggestion_result = supabase.table("career_suggestions").select("*").eq("id", suggestion_id).execute()
        suggestions = suggestion_result.data or []
        
        if not suggestions:
            return JSONResponse({"error": "Suggestion not found"}, status_code=404)
        suggestion = suggestions[0]
        
        # Create ticket
        ticket_id = f"CAREER-{suggestion_id}"
        ticket_result = supabase.table("tickets").insert({
            "ticket_id": ticket_id,
            "title": suggestion.get("title"),
            "description": f"{suggestion.get('description', '')}\n\n**Rationale:** {suggestion.get('rationale', '')}\n**Difficulty:** {suggestion.get('difficulty', '')}\n**Time:** {suggestion.get('time_estimate', '')}",
            "status": "backlog",
            "priority": "medium",
            "tags": "career,growth"
        }).execute()
        
        ticket_db_id = ticket_result.data[0].get("id") if ticket_result.data else None
        
        # Update suggestion
        supabase.table("career_suggestions").update({
            "status": "accepted",
            "converted_to_ticket": ticket_db_id
        }).eq("id", suggestion_id).execute()
        
        return JSONResponse({
            "status": "ok",
            "ticket_id": ticket_id,
            "ticket_db_id": ticket_db_id
        })
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/career/suggestions/compress")
async def compress_suggestions(request: Request):
    """Compress/deduplicate AI suggestions using LLM analysis."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return JSONResponse({"error": "Database not configured"}, status_code=500)
        
        # Get all active suggestions (status is 'suggested' not 'pending')
        result = supabase.table("career_suggestions").select(
            "id, title, description, suggestion_type, rationale"
        ).eq("status", "suggested").order("created_at", desc=True).execute()
        rows = result.data or []
        
        if len(rows) < 2:
            return JSONResponse({"status": "ok", "merged": 0, "removed": 0, "message": "Not enough suggestions to compress"})
        
        # Prepare for LLM analysis
        suggestions_text = "\n".join([
            f"[ID:{r.get('id')}] {r.get('title')}: {(r.get('description') or '')[:200]}"
            for r in rows
        ])
        
        prompt = f"""Analyze these career suggestions and identify duplicates or very similar items.
Return a JSON object with:
- "groups": array of arrays, each containing IDs that should be merged (keep first, remove rest)
- "remove": array of IDs to remove entirely (low quality or superseded)

Suggestions:
{suggestions_text}

Rules:
1. Group suggestions that have the same core advice or recommendation
2. Mark as remove any that are vague, unhelpful, or completely duplicated
3. Only group items that are truly about the same thing
4. Return valid JSON only, no markdown"""

        # Lazy import for backward compatibility
        from ..llm import ask as ask_llm
        response = ask_llm(prompt, model="gpt-4o-mini")
        
        # Parse response
        try:
            import json as json_module
            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            llm_result = json_module.loads(response)
        except:
            return JSONResponse({"status": "ok", "merged": 0, "removed": 0, "message": "Could not parse LLM response"})
        
        merged = 0
        removed = 0
        
        # Process groups - keep first, remove rest
        for group in llm_result.get("groups", []):
            if len(group) > 1:
                # Keep first ID, remove rest
                to_remove = group[1:]
                for rid in to_remove:
                    supabase.table("career_suggestions").update({"status": "dismissed"}).eq("id", rid).execute()
                    merged += 1
        
        # Process removals
        for rid in llm_result.get("remove", []):
            supabase.table("career_suggestions").update({"status": "dismissed"}).eq("id", rid).execute()
            removed += 1
        
        return JSONResponse({
            "status": "ok", 
            "merged": merged, 
            "removed": removed
        })
    
    except Exception as e:
        import traceback
        print(f"Compress error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


# ----------------------
# Standup Updates API
# ----------------------

# Place the /api/signals/status endpoint after router is defined
@router.get("/api/career/standups")
async def get_standups(request: Request, limit: int = Query(30, ge=1, le=100)):
    """Get recent standup updates with feedback."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    try:
        # Try ordering by standup_date first, fall back to created_at
        result = supabase.table("standup_updates").select("*").order(
            "standup_date", desc=True
        ).order("created_at", desc=True).limit(limit).execute()
        return JSONResponse(result.data or [])
    except Exception as e:
        # If standup_date doesn't exist, try just created_at
        try:
            result = supabase.table("standup_updates").select("*").order(
                "created_at", desc=True
            ).limit(limit).execute()
            return JSONResponse(result.data or [])
        except Exception:
            return JSONResponse([])


@router.get("/career/standups")
async def standups_page(request: Request):
    """Render the standups and career chat page."""
    return templates.TemplateResponse("standups.html", {"request": request})


@router.get("/api/career/standups/today")
async def get_today_standup(request: Request):
    """Get today's standup if it exists."""
    from datetime import date
    today = date.today().isoformat()
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse(None)
    
    result = supabase.table("standup_updates").select("*").eq(
        "standup_date", today
    ).order("created_at", desc=True).limit(1).execute()
    
    if result.data:
        return JSONResponse(result.data[0])
    return JSONResponse(None)


# Signal Learning API - PC-1 Implementation
@router.get("/api/signals/feedback-learn")
async def learn_from_feedback():
    """
    Analyze signal feedback patterns and return learning summary.
    
    PC-1 Implementation: Signal feedback → AI learning loop
    
    Returns:
        - Feedback summary by signal type
        - Acceptance rates
        - Patterns identified from rejections/approvals
        - Learning context used for signal extraction
    """
    from ..services.signal_learning import get_signal_learning_service
    
    service = get_signal_learning_service()
    summary = service.get_feedback_summary()
    learning_context = service.generate_learning_context()
    
    return JSONResponse({
        "status": "ok",
        "feedback_summary": summary,
        "learning_context": learning_context,
        "has_sufficient_data": summary.get("total_feedback", 0) >= 5,
    })


@router.post("/api/signals/refresh-learnings")
async def refresh_signal_learnings():
    """
    Refresh signal learnings and store in ai_memory for context retrieval.
    
    Call this periodically or after significant feedback to update the
    learning patterns used by MeetingAnalyzerAgent.
    """
    from ..services.signal_learning import refresh_signal_learnings
    
    success = refresh_signal_learnings()
    
    return JSONResponse({
        "status": "ok" if success else "no_data",
        "message": "Signal learnings refreshed" if success else "Not enough feedback data to generate learnings"
    })


@router.get("/api/signals/quality-hints/{signal_type}")
async def get_signal_quality_hints(signal_type: str):
    """
    Get quality hints for a specific signal type based on user feedback.
    
    Args:
        signal_type: One of decision, action_item, blocker, risk, idea
    
    Returns:
        Quality hints including acceptance rate and patterns
    """
    from ..services.signal_learning import get_signal_learning_service
    
    service = get_signal_learning_service()
    hints = service.get_signal_quality_hints(signal_type)
    
    return JSONResponse(hints)


@router.post("/api/career/standups")
async def create_standup(request: Request):
    """
    Upload a standup update and generate AI feedback.
    
    Delegates to CareerCoachAgent.analyze_standup() for AI processing.
    """
    from ..agents.career_coach import analyze_standup_adapter
    
    data = await request.json()
    content = (data.get("content") or "").strip()
    standup_date = data.get("date")  # Optional, defaults to today
    skip_feedback = data.get("skip_feedback", False)
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    from datetime import date
    if not standup_date:
        standup_date = date.today().isoformat()
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # If skip_feedback, just save without AI processing
    if skip_feedback:
        result = supabase.table("standup_updates").insert({
            "standup_date": standup_date,
            "content": content,
            "feedback": None,
            "sentiment": "neutral",
            "key_themes": ""
        }).execute()
        standup_id = result.data[0].get("id") if result.data else None
        return JSONResponse({
            "status": "ok",
            "id": standup_id,
            "feedback": None,
            "sentiment": "neutral",
            "key_themes": ""
        })
    
    # Get career profile for context
    profile_result = supabase.table("career_profile").select("*").eq("id", 1).execute()
    profile_dict = profile_result.data[0] if profile_result.data else {}
    
    # Get recent standups for pattern analysis
    recent_result = supabase.table("standup_updates").select(
        "content, feedback, sentiment"
    ).order("standup_date", desc=True).limit(5).execute()
    recent_standups_list = recent_result.data or []
    
    # Get active tickets for context
    tickets_result = supabase.table("tickets").select(
        "ticket_id, title, status"
    ).in_("status", ["todo", "in_progress", "in_review", "blocked"]).eq(
        "in_sprint", True
    ).order("created_at", desc=True).limit(10).execute()
    tickets_list = tickets_result.data or []
    
    # Delegate to CareerCoachAgent for AI feedback
    try:
        result = await analyze_standup_adapter(
            content=content,
            profile=profile_dict,
            tickets=tickets_list,
            recent_standups=recent_standups_list,
            db_connection=None,  # Using Supabase now
        )
        
        feedback = result.get("feedback", "")
        sentiment = result.get("sentiment", "neutral")
        key_themes = result.get("key_themes", "")
            
    except Exception as e:
        feedback = f"Could not generate feedback: {str(e)}"
        sentiment = 'neutral'
        key_themes = ''
    
    # Insert standup
    insert_result = supabase.table("standup_updates").insert({
        "standup_date": standup_date,
        "content": content,
        "feedback": feedback,
        "sentiment": sentiment,
        "key_themes": key_themes
    }).execute()
    
    standup_id = insert_result.data[0].get("id") if insert_result.data else None
    
    return JSONResponse({
        "status": "ok",
        "id": standup_id,
        "feedback": feedback,
        "sentiment": sentiment,
        "key_themes": key_themes
    })


@router.post("/api/career/standups/suggest")
async def suggest_standup(request: Request):
    """
    Generate a suggested standup based on code locker changes and ticket progress.
    
    Delegates to CareerCoachAgent.suggest_standup() for AI processing.
    """
    from ..agents.career_coach import suggest_standup_adapter
    
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
    
    # Sort by status priority in Python
    status_order = {"in_progress": 1, "blocked": 2, "in_review": 3, "todo": 4}
    tickets.sort(key=lambda t: status_order.get(t.get("status", "todo"), 5))
    
    tickets_list = tickets
    
    # Get ticket files for each active ticket
    ticket_files_map = {}
    for t in tickets:
        files_result = supabase.table("ticket_files").select(
            "filename, file_type, description, base_content"
        ).eq("ticket_id", t.get("id")).execute()
        files = files_result.data or []
        if files:
            # Get latest version for each file
            for f in files:
                version_result = supabase.table("code_locker").select("version").eq(
                    "filename", f.get("filename")
                ).eq("ticket_id", t.get("id")).order("version", desc=True).limit(1).execute()
                f["latest_version"] = version_result.data[0].get("version") if version_result.data else None
            ticket_files_map[t.get("ticket_id")] = files
    
    # Get recent code locker changes (last 24-48 hours)
    from datetime import datetime, timedelta
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
    from datetime import date
    today = date.today().isoformat()
    yesterday_result = supabase.table("standup_updates").select(
        "content, feedback"
    ).lt("standup_date", today).order("standup_date", desc=True).limit(1).execute()
    yesterday_standup_dict = yesterday_result.data[0] if yesterday_result.data else None
    
    # Add code locker code context for current sprint tickets
    code_locker_code = get_code_locker_code_for_sprint_tickets_supabase(supabase, tickets)
    
    # Delegate to CareerCoachAgent for AI suggestion
    try:
        result = await suggest_standup_adapter(
            tickets=tickets_list,
            ticket_files_map=ticket_files_map,
            code_changes=code_changes_list,
            code_locker_code=code_locker_code,
            yesterday_standup=yesterday_standup_dict,
            db_connection=None,  # Using Supabase now
        )
        
        suggestion = result.get("suggestion", "")
        if result.get("error"):
            suggestion = f"Could not generate suggestion: {result['error']}"
    except Exception as e:
        suggestion = f"Could not generate suggestion: {str(e)}"
    
    return JSONResponse({
        "status": "ok",
        "suggestion": suggestion,
        "tickets_count": len(tickets),
        "code_changes_count": len(code_changes_list),
        "files_tracked": sum(len(f) for f in ticket_files_map.values())
    })


# ----------------------
# Code Locker API
# ----------------------

@router.get("/api/career/code-locker")
async def get_code_locker(request: Request, ticket_id: int = None, filename: str = None):
    """Get code locker entries, optionally filtered by ticket or filename."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    query = supabase.table("code_locker").select("*")
    
    if ticket_id:
        query = query.eq("ticket_id", ticket_id)
    if filename:
        query = query.ilike("filename", f"%{filename}%")
    
    query = query.order("filename").order("version", desc=True)
    result = query.execute()
    entries = result.data or []
    
    # Enrich with ticket info
    for e in entries:
        if e.get("ticket_id"):
            ticket_result = supabase.table("tickets").select("ticket_id, title").eq("id", e["ticket_id"]).execute()
            if ticket_result.data:
                e["ticket_code"] = ticket_result.data[0].get("ticket_id")
                e["ticket_title"] = ticket_result.data[0].get("title")
    
    return JSONResponse(entries)


@router.get("/api/career/code-locker/files")
async def get_code_locker_files(request: Request):
    """Get unique filenames in code locker with latest version info."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    # Get all entries and aggregate in Python
    result = supabase.table("code_locker").select(
        "filename, ticket_id, version, created_at"
    ).order("created_at", desc=True).execute()
    
    # Aggregate by filename, ticket_id
    files_map = {}
    for row in (result.data or []):
        key = (row.get("filename"), row.get("ticket_id"))
        if key not in files_map:
            files_map[key] = {
                "filename": row.get("filename"),
                "ticket_id": row.get("ticket_id"),
                "latest_version": row.get("version"),
                "version_count": 1,
                "last_updated": row.get("created_at")
            }
        else:
            files_map[key]["version_count"] += 1
            if row.get("version", 0) > files_map[key].get("latest_version", 0):
                files_map[key]["latest_version"] = row.get("version")
    
    files = list(files_map.values())
    files.sort(key=lambda f: f.get("last_updated") or "", reverse=True)
    
    return JSONResponse(files)


@router.post("/api/career/code-locker")
async def add_to_code_locker(request: Request):
    """Add or update a file in the code locker."""
    data = await request.json()
    filename = (data.get("filename") or "").strip()
    content = data.get("content") or ""
    ticket_id = data.get("ticket_id")  # Optional
    notes = data.get("notes") or ""
    is_initial = data.get("is_initial", False)
    
    if not filename:
        return JSONResponse({"error": "Filename is required"}, status_code=400)
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Get current version for this file
    existing_result = supabase.table("code_locker").select("version").eq(
        "filename", filename
    ).order("version", desc=True).limit(1).execute()
    
    max_version = existing_result.data[0].get("version") if existing_result.data else 0
    next_version = (max_version or 0) + 1
    
    # If this is marked as initial but versions exist, warn
    if is_initial and max_version:
        is_initial = False  # Can't be initial if versions exist
    
    # If no versions exist, this is initial
    if not max_version:
        is_initial = True
    
    insert_result = supabase.table("code_locker").insert({
        "filename": filename,
        "content": content,
        "ticket_id": ticket_id,
        "version": next_version,
        "notes": notes,
        "is_initial": is_initial
    }).execute()
    
    entry_id = insert_result.data[0].get("id") if insert_result.data else None
    
    return JSONResponse({
        "status": "ok",
        "id": entry_id,
        "version": next_version,
        "is_initial": is_initial
    })


@router.get("/api/career/code-locker/{entry_id}")
async def get_code_locker_entry(entry_id: int):
    """Get a specific code locker entry."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("code_locker").select("*").eq("id", entry_id).execute()
    
    if not result.data:
        return JSONResponse({"error": "Entry not found"}, status_code=404)
    
    entry = result.data[0]
    
    # Enrich with ticket info if available
    if entry.get("ticket_id"):
        ticket_result = supabase.table("tickets").select("ticket_id, title").eq("id", entry["ticket_id"]).execute()
        if ticket_result.data:
            entry["ticket_code"] = ticket_result.data[0].get("ticket_id")
            entry["ticket_title"] = ticket_result.data[0].get("title")
    
    return JSONResponse(entry)


@router.get("/api/career/code-locker/diff/{filename}")
async def get_code_diff(filename: str, v1: int = Query(...), v2: int = Query(...)):
    """Get diff between two versions of a file."""
    import difflib
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    v1_result = supabase.table("code_locker").select("content").eq(
        "filename", filename
    ).eq("version", v1).execute()
    
    v2_result = supabase.table("code_locker").select("content").eq(
        "filename", filename
    ).eq("version", v2).execute()
    
    if not v1_result.data or not v2_result.data:
        return JSONResponse({"error": "One or both versions not found"}, status_code=404)
    
    version1_content = v1_result.data[0].get("content", "")
    version2_content = v2_result.data[0].get("content", "")
    
    # Generate unified diff
    diff = list(difflib.unified_diff(
        version1_content.splitlines(keepends=True),
        version2_content.splitlines(keepends=True),
        fromfile=f"{filename} (v{v1})",
        tofile=f"{filename} (v{v2})"
    ))
    
    return JSONResponse({
        "filename": filename,
        "v1": v1,
        "v2": v2,
        "diff": "".join(diff),
        "lines_added": sum(1 for line in diff if line.startswith('+')),
        "lines_removed": sum(1 for line in diff if line.startswith('-'))
    })


@router.delete("/api/career/code-locker/{entry_id}")
async def delete_code_locker_entry(entry_id: int):
    """Delete a code locker entry."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("code_locker").delete().eq("id", entry_id).execute()
    
    return JSONResponse({"status": "ok"})


# ----------------------
# Ticket Files API
# ----------------------

@router.get("/api/career/ticket-files/{ticket_id}")
async def get_ticket_files(ticket_id: int):
    """Get files associated with a ticket."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    result = supabase.table("ticket_files").select("*").eq(
        "ticket_id", ticket_id
    ).order("file_type").order("filename").execute()
    
    files = result.data or []
    
    # Add locker version and count for each file
    for f in files:
        version_result = supabase.table("code_locker").select("version").eq(
            "filename", f.get("filename")
        ).eq("ticket_id", f.get("ticket_id")).order("version", desc=True).limit(1).execute()
        
        count_result = supabase.table("code_locker").select("id").eq(
            "filename", f.get("filename")
        ).eq("ticket_id", f.get("ticket_id")).execute()
        
        f["locker_version"] = version_result.data[0].get("version") if version_result.data else None
        f["locker_count"] = len(count_result.data) if count_result.data else 0
    
    return JSONResponse(files)


@router.post("/api/career/ticket-files/{ticket_id}")
async def add_ticket_file(ticket_id: int, request: Request):
    """Add a file to a ticket (new or update)."""
    data = await request.json()
    filename = (data.get("filename") or "").strip()
    file_type = data.get("file_type", "update")  # 'new' or 'update'
    base_content = data.get("base_content") or ""
    description = data.get("description") or ""
    
    if not filename:
        return JSONResponse({"error": "Filename is required"}, status_code=400)
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    try:
        insert_result = supabase.table("ticket_files").insert({
            "ticket_id": ticket_id,
            "filename": filename,
            "file_type": file_type,
            "base_content": base_content,
            "description": description
        }).execute()
        
        file_id = insert_result.data[0].get("id") if insert_result.data else None
        
        # If this is an 'update' file with base_content, add it to code locker as v1
        if file_type == 'update' and base_content:
            supabase.table("code_locker").insert({
                "ticket_id": ticket_id,
                "filename": filename,
                "content": base_content,
                "version": 1,
                "notes": "Initial/baseline version from ticket",
                "is_initial": True
            }).execute()
        
        return JSONResponse({
            "status": "ok",
            "id": file_id
        })
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            return JSONResponse({"error": "File already exists for this ticket"}, status_code=400)
        raise


@router.put("/api/career/ticket-files/{file_id}")
async def update_ticket_file(file_id: int, request: Request):
    """Update a ticket file's details."""
    data = await request.json()
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    update_data = {}
    if "description" in data:
        update_data["description"] = data["description"]
    if "base_content" in data:
        update_data["base_content"] = data["base_content"]
    if "file_type" in data:
        update_data["file_type"] = data["file_type"]
    
    if update_data:
        supabase.table("ticket_files").update(update_data).eq("id", file_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.delete("/api/career/ticket-files/{file_id}")
async def delete_ticket_file(file_id: int):
    """Delete a ticket file."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("ticket_files").delete().eq("id", file_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/api/career/tickets-with-files")
async def get_tickets_with_files():
    """Get all active tickets with their associated files for code locker selection."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    # Get active tickets from Supabase
    result = supabase.table("tickets").select("*").in_(
        "status", ["todo", "in_progress", "in_review", "blocked"]
    ).eq("in_sprint", True).execute()
    
    tickets = result.data or []
    
    # Sort by status priority
    status_order = {"in_progress": 1, "blocked": 2, "in_review": 3, "todo": 4}
    tickets.sort(key=lambda t: status_order.get(t.get("status", "todo"), 5))
    
    # Get files from Supabase for each ticket
    result_list = []
    for ticket in tickets:
        ticket_id = ticket.get('id')
        
        # Get files for this ticket
        files_result = supabase.table("ticket_files").select(
            "id,filename,file_type,description"
        ).eq("ticket_id", ticket_id).order("file_type").order("filename").execute()
        
        files = files_result.data or []
        
        # Add latest_version for each file
        for f in files:
            version_result = supabase.table("code_locker").select("version").eq(
                "filename", f.get("filename")
            ).eq("ticket_id", ticket_id).order("version", desc=True).limit(1).execute()
            f["latest_version"] = version_result.data[0].get("version") if version_result.data else None
        
        result_list.append({
            "id": ticket.get("id"),
            "ticket_id": ticket.get("ticket_id"),
            "title": ticket.get("title", ""),
            "status": ticket.get("status"),
            "files": files
        })
    
    return JSONResponse(result_list)


@router.get("/api/career/code-locker/next-version")
async def get_next_version(filename: str = Query(...), ticket_id: int = Query(None)):
    """Get the next version number for a file in the locker."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Check for existing versions
    query = supabase.table("code_locker").select("version").eq("filename", filename)
    if ticket_id:
        query = query.eq("ticket_id", ticket_id)
    
    result = query.order("version", desc=True).limit(1).execute()
    max_version = result.data[0].get("version") if result.data else 0
    next_version = (max_version or 0) + 1
    
    # Check if this file is linked to a ticket
    ticket_file = None
    if ticket_id:
        tf_result = supabase.table("ticket_files").select("*").eq(
            "filename", filename
        ).eq("ticket_id", ticket_id).execute()
        
        if tf_result.data:
            tf = tf_result.data[0]
            # Get ticket code
            ticket_result = supabase.table("tickets").select("ticket_id").eq(
                "id", ticket_id
            ).execute()
            ticket_code = ticket_result.data[0].get("ticket_id") if ticket_result.data else None
            tf["ticket_code"] = ticket_code
            ticket_file = tf
    
    return JSONResponse({
        "filename": filename,
        "next_version": next_version,
        "is_new_file": max_version is None or max_version == 0,
        "ticket_file": ticket_file
    })


# NOTE: /api/career/chat route is defined earlier in this file (around line 396)


# ============================================
# Career Memories and Completed Projects
# ============================================

@router.get("/api/career/memories")
async def get_career_memories(memory_type: str = None, include_unpinned: bool = True):
    """Get career memories, optionally filtered by type."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    query = supabase.table("career_memories").select("*")
    
    if memory_type:
        query = query.eq("memory_type", memory_type)
        if not include_unpinned:
            query = query.eq("is_pinned", True)
    
    result = query.order("is_pinned", desc=True).order("created_at", desc=True).execute()
    return JSONResponse(result.data or [])


@router.post("/api/career/memories")
async def create_career_memory(request: Request):
    """Create a new career memory."""
    data = await request.json()
    memory_type = data.get("memory_type", "achievement")
    title = data.get("title")
    description = data.get("description")
    source_type = data.get("source_type")
    source_id = data.get("source_id")
    skills = data.get("skills", "")
    is_pinned = data.get("is_pinned", False)
    is_ai_work = data.get("is_ai_work", False)
    metadata = json.dumps(data.get("metadata", {}))
    
    if not title:
        return JSONResponse({"error": "Title is required"}, status_code=400)
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("career_memories").insert({
        "memory_type": memory_type,
        "title": title,
        "description": description,
        "source_type": source_type,
        "source_id": source_id,
        "skills": skills,
        "is_pinned": is_pinned,
        "is_ai_work": is_ai_work,
        "metadata": metadata
    }).execute()
    
    memory_id = result.data[0].get("id") if result.data else None
    
    return JSONResponse({"status": "ok", "id": memory_id})


@router.post("/api/career/memories/{memory_id}/pin")
async def toggle_pin_memory(memory_id: int):
    """Toggle pin status of a memory."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("career_memories").select("is_pinned").eq("id", memory_id).execute()
    if not result.data:
        return JSONResponse({"error": "Memory not found"}, status_code=404)
    
    current_status = result.data[0].get("is_pinned", False)
    new_status = not current_status
    
    supabase.table("career_memories").update({
        "is_pinned": new_status
    }).eq("id", memory_id).execute()
    
    return JSONResponse({"status": "ok", "is_pinned": new_status})


@router.delete("/api/career/memories/{memory_id}")
async def delete_career_memory(memory_id: int):
    """Delete a career memory (only if not pinned)."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("career_memories").select("is_pinned").eq("id", memory_id).execute()
    if result.data and result.data[0].get("is_pinned"):
        return JSONResponse({"error": "Cannot delete pinned memory. Unpin first."}, status_code=400)
    
    supabase.table("career_memories").delete().eq("id", memory_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/api/career/completed-projects")
async def get_completed_projects():
    """Get completed projects from tickets and career memories."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"tickets": [], "memories": []})
    
    # Get completed tickets
    tickets_result = supabase.table("tickets").select("*").in_(
        "status", ["done", "complete", "completed"]
    ).order("updated_at", desc=True).limit(50).execute()
    
    all_tickets = tickets_result.data or []
    
    # Get memories that are already synced
    synced_result = supabase.table("career_memories").select("source_id").eq(
        "source_type", "ticket"
    ).execute()
    synced_ids = {str(m.get("source_id")) for m in (synced_result.data or [])}
    
    # Filter tickets to only those not yet synced
    tickets = []
    for t in all_tickets:
        if str(t.get("id")) not in synced_ids:
            # Get files for this ticket
            files_result = supabase.table("ticket_files").select("filename").eq(
                "ticket_id", t.get("id")
            ).execute()
            file_names = [f.get("filename") for f in (files_result.data or [])]
            t["files"] = ",".join(file_names) if file_names else None
            tickets.append(t)
    
    # Get completed project memories (includes synced tickets)
    memories_result = supabase.table("career_memories").select("*").eq(
        "memory_type", "completed_project"
    ).order("is_pinned", desc=True).order("created_at", desc=True).execute()
    
    return JSONResponse({
        "tickets": tickets,
        "memories": memories_result.data or []
    })


@router.post("/api/career/sync-completed-projects")
async def sync_completed_projects():
    """Sync completed tickets to career memories (without overwriting pinned ones) - reads from Supabase."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Get completed tickets from Supabase
    all_tickets = ticket_service.get_all_tickets()
    completed_tickets = [t for t in all_tickets if t.get("status") in ('done', 'complete', 'completed')]
    
    # Get IDs already in memories
    existing_result = supabase.table("career_memories").select("source_id").eq(
        "source_type", "ticket"
    ).execute()
    existing_ids = {str(row.get("source_id")) for row in (existing_result.data or [])}
    
    added = 0
    for t in completed_tickets:
        if str(t.get("id")) in existing_ids:
            continue
            
        # Create memory for completed ticket
        skills = t.get("tags") or ""
        metadata = json.dumps({
            "ticket_id": t.get("ticket_id"),
            "status": t.get("status"),
            "completed_at": t.get("updated_at")
        })
        
        supabase.table("career_memories").insert({
            "memory_type": "completed_project",
            "title": t.get("title") or "",
            "description": t.get("ai_summary") or t.get("description") or "",
            "source_type": "ticket",
            "source_id": str(t.get("id")),
            "skills": skills,
            "is_pinned": False,
            "metadata": metadata
        }).execute()
        added += 1
    
    return JSONResponse({"status": "ok", "added": added})


# ============================================
# Skills Tracker
# ============================================

# Pre-defined skill categories with initial skills
SKILL_CATEGORIES = {
    "ddd": ["Domain Driven Design", "Bounded Contexts", "Aggregates", "Event Sourcing", "CQRS"],
    "python": ["Python Advanced", "Hexagonal Architecture", "Clean Architecture", "Design Patterns", "Type Hints"],
    "analytics": ["Analytics Engineering", "Data Modeling", "dbt", "Data Quality", "Metrics Layer"],
    "backend": ["Backend Development", "API Design", "REST APIs", "GraphQL", "Microservices"],
    "airflow": ["Apache Airflow", "DAG Design", "Task Dependencies", "Operators", "Sensors"],
    "aws": ["AWS Services", "S3", "Lambda", "Step Functions", "Glue", "Redshift"],
    "ai": ["AI/ML Integration", "LLM APIs", "Prompt Engineering", "RAG", "Vector Databases"],
    "agentic": ["Agentic AI Design", "MCP Servers", "Tool Calling", "Agent Orchestration", "ReAct Patterns", "Chain of Thought", "Function Calling", "Multi-Agent Systems"],
    "data": ["Data Engineering", "ETL/ELT", "Data Pipelines", "Data Governance", "Apache Atlas", "Data Catalog"],
    "knowledge": ["Knowledge Engineering", "Knowledge Graphs", "Ontologies", "Semantic Web", "DIKW Framework"]
}


@router.get("/api/career/development-tracker")
async def get_development_tracker():
    """Get development tracker data - skill progress and learning activities."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"skills": [], "activities": [], "projects": [], "summary": {}})
    
    # Get recent skill changes (skills with evidence or high proficiency)
    skills_result = supabase.table("skill_tracker").select(
        "skill_name,category,proficiency_level,evidence,updated_at,projects_count"
    ).gt("proficiency_level", 0).order("updated_at", desc=True).order(
        "proficiency_level", desc=True
    ).limit(20).execute()
    skills = skills_result.data or []
    
    # Get recent career memories as learning activities
    memories_result = supabase.table("career_memories").select(
        "id,memory_type,title,description,skills,created_at"
    ).in_("memory_type", ["skill_milestone", "achievement"]).order(
        "created_at", desc=True
    ).limit(10).execute()
    memories = memories_result.data or []
    
    # Get completed projects from career_memories
    projects_result = supabase.table("career_memories").select(
        "id,title,skills,description,created_at"
    ).or_("memory_type.eq.completed_project,is_ai_work.eq.true").order(
        "created_at", desc=True
    ).limit(5).execute()
    # Rename fields for compatibility
    projects = []
    for p in (projects_result.data or []):
        projects.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "technologies": p.get("skills"),
            "impact": p.get("description"),
            "completed_date": p.get("created_at")
        })
    
    # Calculate summary stats
    all_skills_result = supabase.table("skill_tracker").select("proficiency_level").gt(
        "proficiency_level", 0
    ).execute()
    all_skills = all_skills_result.data or []
    total_skills = len(all_skills)
    avg_proficiency = sum(s.get("proficiency_level", 0) for s in all_skills) / total_skills if total_skills else 0
    
    # Skills by proficiency level
    skill_levels = {
        "beginner": len([s for s in all_skills if 1 <= s.get("proficiency_level", 0) <= 30]),
        "intermediate": len([s for s in all_skills if 31 <= s.get("proficiency_level", 0) <= 60]),
        "advanced": len([s for s in all_skills if 61 <= s.get("proficiency_level", 0) <= 85]),
        "expert": len([s for s in all_skills if s.get("proficiency_level", 0) > 85]),
    }
    
    return JSONResponse({
        "skills": skills,
        "activities": memories,
        "projects": projects,
        "summary": {
            "total_skills": total_skills,
            "avg_proficiency": round(avg_proficiency, 1),
            "skill_levels": skill_levels
        }
    })


@router.get("/api/career/skills")
async def get_skills():
    """Get all tracked skills with categories."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"skills": [], "by_category": {}, "categories": list(SKILL_CATEGORIES.keys())})
    
    result = supabase.table("skill_tracker").select("*").order(
        "category"
    ).order("proficiency_level", desc=True).execute()
    skills = result.data or []
    
    # Group by category
    by_category = {}
    for s in skills:
        cat = s.get("category") or "other"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(s)
    
    return JSONResponse({
        "skills": [dict(s) for s in skills],
        "by_category": by_category,
        "categories": list(SKILL_CATEGORIES.keys())
    })


@router.post("/api/career/skills/initialize")
async def initialize_skills(request: Request):
    """Initialize skill tracker with pre-defined categories or custom skills."""
    try:
        body = await request.json()
        skills_with_categories = body.get("skills_with_categories", [])
        custom_skills = body.get("skills", [])  # Legacy format
    except:
        skills_with_categories = []
        custom_skills = []
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    added = 0
    
    if skills_with_categories:
        # New format: skills with their categories
        for item in skills_with_categories:
            skill_name = item.get("name") if isinstance(item, dict) else item
            category = item.get("category", "Custom") if isinstance(item, dict) else "Custom"
            try:
                # Check if exists first
                existing = supabase.table("skill_tracker").select("id").eq(
                    "skill_name", skill_name
                ).execute()
                if not existing.data:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill_name,
                        "category": category,
                        "proficiency_level": 0
                    }).execute()
                    added += 1
            except:
                pass
    elif custom_skills:
        # Legacy format: just skill names (default to Custom category)
        for skill in custom_skills:
            try:
                existing = supabase.table("skill_tracker").select("id").eq(
                    "skill_name", skill
                ).execute()
                if not existing.data:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill,
                        "category": "Custom",
                        "proficiency_level": 0
                    }).execute()
                    added += 1
            except:
                pass
    else:
        # Add default skill categories
        for category, skills in SKILL_CATEGORIES.items():
            for skill in skills:
                try:
                    existing = supabase.table("skill_tracker").select("id").eq(
                        "skill_name", skill
                    ).execute()
                    if not existing.data:
                        supabase.table("skill_tracker").insert({
                            "skill_name": skill,
                            "category": category,
                            "proficiency_level": 0
                        }).execute()
                        added += 1
                except:
                    pass
    
    return JSONResponse({"status": "ok", "initialized": added})


@router.post("/api/career/skills/reset")
async def reset_skills():
    """Reset all skill data (delete all skills)."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Delete all skills - need to use a filter since Supabase requires one
    supabase.table("skill_tracker").delete().gte("id", 0).execute()
    return JSONResponse({"status": "ok", "message": "All skills reset"})


@router.post("/api/career/skills/remove-by-categories")
async def remove_skills_by_categories(request: Request):
    """Remove skills belonging to unselected categories."""
    data = await request.json()
    categories_to_remove = data.get("categories", [])
    
    if not categories_to_remove:
        return JSONResponse({"status": "ok", "removed": 0})
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    removed = 0
    for category in categories_to_remove:
        result = supabase.table("skill_tracker").delete().eq("category", category).execute()
        removed += len(result.data) if result.data else 0
    
    return JSONResponse({"status": "ok", "removed": removed, "categories": categories_to_remove})


@router.post("/api/career/skills/from-resume")
async def extract_skills_from_resume(request: Request):
    """Extract skills from uploaded resume text using AI."""
    data = await request.json()
    resume_text = data.get("resume_text", "")
    update_profile = data.get("update_profile", False)
    
    if not resume_text.strip():
        return JSONResponse({"error": "No resume text provided"}, status_code=400)
    
    # Use AI to extract skills from resume
    prompt = f"""Analyze this resume and extract technical skills with estimated proficiency levels.

Resume:
{resume_text[:8000]}

Return a JSON object with this structure:
{{
    "skills": [
        {{"name": "Skill Name", "category": "category_name", "proficiency": 50, "evidence": "Brief reason from resume"}}
    ]
}}

Categories should be one of: python, backend, data, analytics, aws, Agentic AI, ddd, knowledge, Custom
Proficiency should be 1-100 based on the level of experience shown.

Return ONLY the JSON object, no other text."""

    profile_updated = False
    try:
        # Lazy import for backward compatibility
        from ..llm import ask as ask_llm
        response = ask_llm(prompt, model="gpt-4o-mini")
        # Parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            skills_data = json.loads(json_match.group())
            
            # Insert skills into database
            skills_added = 0
            supabase = get_supabase_client()
            if supabase:
                for skill in skills_data.get("skills", []):
                    skill_name = skill.get("name")
                    category = skill.get("category", "Custom")
                    proficiency = skill.get("proficiency", 30)
                    evidence = json.dumps([skill.get("evidence", "Extracted from resume")])
                    
                    # Check if exists and upsert
                    existing = supabase.table("skill_tracker").select("id,proficiency_level").eq(
                        "skill_name", skill_name
                    ).execute()
                    
                    if existing.data:
                        # Update if new proficiency is higher
                        current_prof = existing.data[0].get("proficiency_level", 0)
                        if proficiency > current_prof:
                            supabase.table("skill_tracker").update({
                                "proficiency_level": proficiency,
                                "evidence": evidence
                            }).eq("skill_name", skill_name).execute()
                    else:
                        supabase.table("skill_tracker").insert({
                            "skill_name": skill_name,
                            "category": category,
                            "proficiency_level": proficiency,
                            "evidence": evidence
                        }).execute()
                    skills_added += 1
            
            # If update_profile is requested, extract and update profile info
            if update_profile:
                profile_prompt = f"""Analyze this resume and extract profile information.

Resume:
{resume_text[:8000]}

Return a JSON object with these fields (include only what you can find):
{{
    "current_role": "current or most recent job title",
    "target_role": "next career goal if mentioned",
    "years_experience": number or null,
    "education": "degrees, schools",
    "certifications": "certifications mentioned",
    "technical_specializations": "main technical focus areas",
    "strengths": "key strengths shown",
    "short_term_goals": "any short-term goals mentioned",
    "long_term_goals": "any long-term career aspirations",
    "soft_skills": "leadership, communication skills etc",
    "languages": "programming or spoken languages",
    "work_achievements": "notable achievements"
}}

Return ONLY valid JSON, no other text. Use null for fields you can't determine."""

                try:
                    # Lazy import for backward compatibility
                    from ..llm import ask as ask_llm
                    profile_response = ask_llm(profile_prompt, model="gpt-4o-mini")
                    profile_match = re.search(r'\{[\s\S]*\}', profile_response)
                    if profile_match and supabase:
                        profile_data = json.loads(profile_match.group())
                        
                        # Build update dict for non-null fields
                        update_data = {}
                        for field in ['current_role', 'target_role', 'years_experience', 'education', 
                                     'certifications', 'technical_specializations', 'strengths',
                                     'short_term_goals', 'long_term_goals', 'soft_skills', 
                                     'languages', 'work_achievements']:
                            if field in profile_data and profile_data[field]:
                                val = profile_data[field]
                                if isinstance(val, list):
                                    val = ', '.join(str(item) for item in val)
                                update_data[field] = str(val)
                        
                        if update_data:
                            # Check if profile exists
                            existing = supabase.table("career_profile").select("id").limit(1).execute()
                            if existing.data:
                                supabase.table("career_profile").update(update_data).eq(
                                    "id", existing.data[0].get("id")
                                ).execute()
                            else:
                                supabase.table("career_profile").insert(update_data).execute()
                            profile_updated = True
                except Exception as pe:
                    print(f"Profile update error: {pe}")
            
            return JSONResponse({
                "status": "ok",
                "skills_added": skills_added,
                "skills": skills_data.get("skills", []),
                "profile_updated": profile_updated
            })
        else:
            return JSONResponse({"error": "Could not parse AI response"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/career/extract-resume-text")
async def extract_resume_text(request: Request):
    """Extract text from uploaded PDF resume file."""
    from fastapi import UploadFile, File
    import tempfile
    
    form = await request.form()
    file = form.get("file")
    
    if not file:
        return JSONResponse({"error": "No file uploaded"}, status_code=400)
    
    filename = file.filename.lower()
    
    # Read file content
    content = await file.read()
    
    # For PDF files, try to extract text
    if filename.endswith('.pdf'):
        try:
            # Try PyPDF2 first
            try:
                import PyPDF2
                import io
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text() or '')
                text = '\n'.join(text_parts)
                if text.strip():
                    return JSONResponse({"status": "ok", "text": text})
            except ImportError:
                pass
            
            # Fallback: try pdfplumber
            try:
                import pdfplumber
                import io
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    text_parts = []
                    for page in pdf.pages:
                        text_parts.append(page.extract_text() or '')
                    text = '\n'.join(text_parts)
                    if text.strip():
                        return JSONResponse({"status": "ok", "text": text})
            except ImportError:
                pass
            
            return JSONResponse({
                "error": "PDF parsing libraries not available. Please install PyPDF2 or pdfplumber, or paste the text manually."
            }, status_code=500)
            
        except Exception as e:
            return JSONResponse({"error": f"Failed to parse PDF: {str(e)}"}, status_code=500)
    
    # For text files
    if filename.endswith('.txt'):
        try:
            text = content.decode('utf-8')
            return JSONResponse({"status": "ok", "text": text})
        except:
            return JSONResponse({"error": "Failed to decode text file"}, status_code=500)
    
    return JSONResponse({"error": "Unsupported file type"}, status_code=400)


@router.post("/api/career/skills/assess-from-codebase")
async def assess_skills_from_codebase(request: Request):
    """Analyze codebase and update skill levels based on code evidence."""
    import os
    import glob
    import random
    
    # Define patterns to look for each skill - now with per-skill patterns
    skill_patterns = {
        # Domain Driven Design
        "Domain Driven Design": ["domain", "aggregate", "bounded_context", "ubiquitous"],
        "Bounded Contexts": ["bounded_context", "context_map", "anti_corruption"],
        "Aggregates": ["aggregate", "aggregate_root", "entity"],
        "Event Sourcing": ["event_source", "event_store", "cqrs", "event_driven"],
        # Python
        "Python": ["def ", "class ", "import ", "async def", "__init__"],
        "typing": ["typing", "Optional", "List[", "Dict[", "Union[", "Callable"],
        "Hexagonal Architecture": ["hexagonal", "adapter", "port", "driven_adapter"],
        # Analytics
        "Data Analysis": ["pandas", "numpy", "analysis", "dataframe"],
        "SQL/Databases": ["sqlite", "postgresql", "execute(", "SELECT", "INSERT"],
        "Data Visualization": ["matplotlib", "plotly", "chart", "visualization"],
        # Backend
        "REST APIs": ["@app.get", "@app.post", "@router", "endpoint", "api/"],
        "FastAPI": ["fastapi", "FastAPI", "APIRouter", "Depends"],
        "Backend Development": ["middleware", "authentication", "authorization"],
        "Microservices": ["microservice", "service_mesh", "container"],
        # AI/ML - Agentic AI specific
        "LLM Integration": ["openai", "anthropic", "llm", "chat_completion", "gpt"],
        "RAG": ["rag", "retrieval", "embedding", "vector_store", "chromadb"],
        "Embeddings": ["embedding", "embed_text", "vector", "cosine_similarity"],
        "Prompt Engineering": ["prompt", "system_message", "user_message", "few_shot"],
        "MCP Servers": ["mcp", "model_context_protocol", "mcp_server", "@mcp", "McpServer"],
        "Tool Calling": ["tool_call", "function_call", "@tool", "tools=", "tool_registry", "TOOL_REGISTRY"],
        "Agent Orchestration": ["agent", "orchestrat", "workflow", "chain_of_thought"],
        "ReAct Patterns": ["react", "reason", "act", "observation", "thought"],
        "Function Calling": ["function_call", "functions=", "@function", "call_function"],
        "Multi-Agent Systems": ["multi_agent", "agent_team", "collaboration", "delegate"],
        # Data Engineering
        "ETL": ["etl", "extract", "transform", "load", "pipeline"],
        "Data Pipelines": ["pipeline", "dag", "workflow", "orchestration"],
        "Data Quality": ["data_quality", "validation", "schema", "constraint"],
        "Data Lineage": ["lineage", "provenance", "tracking", "metadata"],
        # Cloud/AWS
        "AWS": ["boto3", "aws", "s3_client", "lambda_handler"],
        "Cloud Platforms": ["cloud", "gcp", "azure", "terraform"],
        "Lambda": ["lambda_handler", "serverless", "aws_lambda", "lambda_function", "@lambda"],
        "S3": ["s3", "bucket", "s3_client", "upload_file"],
        # Knowledge
        "Knowledge Graphs": ["knowledge_graph", "neo4j", "graph_db", "triplet"],
        "DIKW": ["dikw", "data_information", "knowledge_wisdom"],
        "Semantic": ["semantic", "ontology", "rdf", "sparql"],
    }
    
    # Scan codebase
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    py_files = glob.glob(os.path.join(workspace_root, "**/*.py"), recursive=True)
    
    # Exclude common non-project directories
    py_files = [f for f in py_files if not any(x in f for x in ['__pycache__', '.venv', 'venv', 'node_modules', '.git'])]
    
    # Track evidence per skill (not per category)
    skill_evidence = {skill: {"files": [], "count": 0, "patterns_found": []} for skill in skill_patterns}
    
    for filepath in py_files[:150]:  # Increase limit to 150 files
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                content_lower = content.lower()
                
            for skill, patterns in skill_patterns.items():
                for pattern in patterns:
                    pattern_lower = pattern.lower()
                    if pattern_lower in content_lower:
                        rel_path = os.path.relpath(filepath, workspace_root)
                        if rel_path not in skill_evidence[skill]["files"]:
                            skill_evidence[skill]["files"].append(rel_path)
                        skill_evidence[skill]["count"] += content_lower.count(pattern_lower)
                        if pattern not in skill_evidence[skill]["patterns_found"]:
                            skill_evidence[skill]["patterns_found"].append(pattern)
        except Exception:
            pass
    
    # Map skills to their categories for the database
    skill_categories = {
        "Domain Driven Design": "ddd", "Bounded Contexts": "ddd", "Aggregates": "ddd", "Event Sourcing": "ddd",
        "Python": "python", "typing": "python", "Hexagonal Architecture": "python",
        "Data Analysis": "analytics", "SQL/Databases": "analytics", "Data Visualization": "analytics",
        "REST APIs": "backend", "FastAPI": "backend", "Backend Development": "backend", "Microservices": "backend",
        "LLM Integration": "Agentic AI", "RAG": "Agentic AI", "Embeddings": "Agentic AI", "Prompt Engineering": "Agentic AI",
        "MCP Servers": "Agentic AI", "Tool Calling": "Agentic AI", "Agent Orchestration": "Agentic AI",
        "ReAct Patterns": "Agentic AI", "Function Calling": "Agentic AI", "Multi-Agent Systems": "Agentic AI",
        "ETL": "data", "Data Pipelines": "data", "Data Quality": "data", "Data Lineage": "data",
        "AWS": "aws", "Cloud Platforms": "aws", "Lambda": "aws", "S3": "aws",
        "Knowledge Graphs": "knowledge", "DIKW": "knowledge", "Semantic": "knowledge",
    }
    
    # Update skill levels based on evidence - now per-skill with variance
    skills_updated = 0
    supabase = get_supabase_client()
    if supabase:
        for skill, evidence in skill_evidence.items():
            file_count = len(evidence["files"])
            pattern_count = len(evidence["patterns_found"])
            total_count = evidence["count"]
            
            if file_count > 0 or total_count > 0:
                # Calculate proficiency with more variance
                # Base score depends on pattern matches
                base_score = min(25, pattern_count * 8)  # 0-25 based on pattern variety
                file_bonus = min(20, file_count * 3)  # 0-20 based on file spread
                usage_bonus = min(25, total_count // 10)  # 0-25 based on usage frequency
                
                # Add some controlled variance (+/- 5) to avoid identical scores
                variance = random.randint(-5, 5)
                
                proficiency = max(5, min(70, base_score + file_bonus + usage_bonus + variance))
                
                category = skill_categories.get(skill, "Custom")
                evidence_json = json.dumps(evidence["files"][:10])
                
                # Check if exists and upsert
                existing = supabase.table("skill_tracker").select("id,proficiency_level").eq(
                    "skill_name", skill
                ).execute()
                
                if existing.data:
                    current_prof = existing.data[0].get("proficiency_level", 0)
                    if proficiency > current_prof:
                        supabase.table("skill_tracker").update({
                            "proficiency_level": proficiency,
                            "evidence": evidence_json,
                            "last_used_at": "now()"
                        }).eq("skill_name", skill).execute()
                else:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill,
                        "category": category,
                        "proficiency_level": proficiency,
                        "evidence": evidence_json
                    }).execute()
                skills_updated += 1
    
    # Build evidence summary for response
    evidence_summary = {
        skill: {
            "files": evidence["files"][:5],
            "patterns": evidence["patterns_found"],
            "count": evidence["count"]
        }
        for skill, evidence in skill_evidence.items()
        if evidence["count"] > 0
    }
    
    return JSONResponse({
        "status": "ok",
        "skills_updated": skills_updated,
        "evidence": evidence_summary
    })


@router.post("/api/career/skills/populate-from-projects")
async def populate_skills_from_projects():
    """Populate skill tracker from completed projects and AI implementation memories.
    
    Tracks which memories/tickets have been processed to avoid double-counting.
    Uses skill_import_tracking table to remember what's already been imported.
    """
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    skills_updated = 0
    projects_processed = 0
    memories_processed = 0
    skipped_already_processed = 0
    
    # Get already processed IDs from tracking table
    tracking_result = supabase.table("skill_import_tracking").select("source_type,source_id").execute()
    processed = {(r.get("source_type"), str(r.get("source_id"))) for r in (tracking_result.data or [])}
    
    # 1. Get skills/tags from completed project memories
    project_memories_result = supabase.table("career_memories").select(
        "id,skills,title"
    ).eq("memory_type", "completed_project").not_.is_("skills", "null").neq("skills", "").execute()
    
    for mem in (project_memories_result.data or []):
        mem_id = str(mem.get("id"))
        
        if ("career_memory", mem_id) in processed:
            skipped_already_processed += 1
            continue
        
        projects_processed += 1
        for skill in (mem.get("skills") or "").split(","):
            skill = skill.strip()
            if skill:
                # Check if skill exists and upsert
                existing = supabase.table("skill_tracker").select("id,proficiency_level,projects_count").eq(
                    "skill_name", skill
                ).execute()
                
                if existing.data:
                    current = existing.data[0]
                    new_prof = min(100, (current.get("proficiency_level") or 0) + 5)
                    new_count = (current.get("projects_count") or 0) + 1
                    supabase.table("skill_tracker").update({
                        "proficiency_level": new_prof,
                        "projects_count": new_count
                    }).eq("id", current.get("id")).execute()
                else:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill,
                        "category": "projects",
                        "proficiency_level": 20,
                        "projects_count": 1
                    }).execute()
                skills_updated += 1
        
        # Mark as processed
        supabase.table("skill_import_tracking").insert({
            "source_type": "career_memory",
            "source_id": mem_id
        }).execute()
    
    # 2. Process completed tickets with tags (from Supabase tickets)
    all_tickets = ticket_service.get_all_tickets()
    completed_tickets = [t for t in all_tickets 
                       if t.get("status") in ('done', 'complete', 'completed')
                       and t.get("tags")]
    
    for ticket in completed_tickets:
        ticket_id = str(ticket.get("id", ticket.get("key", "")))
        
        if ("ticket", ticket_id) in processed:
            skipped_already_processed += 1
            continue
        
        for tag in (ticket.get("tags") or "").split(","):
            tag = tag.strip()
            if tag:
                existing = supabase.table("skill_tracker").select("id,proficiency_level,tickets_count").eq(
                    "skill_name", tag
                ).execute()
                
                if existing.data:
                    current = existing.data[0]
                    new_prof = min(100, (current.get("proficiency_level") or 0) + 3)
                    new_count = (current.get("tickets_count") or 0) + 1
                    supabase.table("skill_tracker").update({
                        "proficiency_level": new_prof,
                        "tickets_count": new_count
                    }).eq("id", current.get("id")).execute()
                else:
                    supabase.table("skill_tracker").insert({
                        "skill_name": tag,
                        "category": "tickets",
                        "proficiency_level": 15,
                        "tickets_count": 1
                    }).execute()
                skills_updated += 1
        
        # Mark as processed
        supabase.table("skill_import_tracking").insert({
            "source_type": "ticket",
            "source_id": ticket_id
        }).execute()
    
    return JSONResponse({
        "status": "ok",
        "projects_processed": projects_processed,
        "memories_processed": memories_processed,
        "skills_updated": skills_updated,
        "skipped_already_processed": skipped_already_processed
    })


@router.post("/api/career/skills/update-from-tickets")
async def update_skills_from_tickets():
    """Update skill counts based on completed tickets (from Supabase)."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Get completed tickets from Supabase
    all_tickets = ticket_service.get_all_tickets()
    completed_tickets = [t for t in all_tickets 
                       if t.get("status") in ('done', 'complete', 'completed')
                       and t.get("tags")]
    
    # Count occurrences of each skill/tag
    tag_counts = {}
    for t in completed_tickets:
        for tag in (t.get("tags") or "").split(","):
            tag = tag.strip().lower()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Update skill tracker
    updated = 0
    for tag, count in tag_counts.items():
        # Find matching skills (case insensitive)
        result = supabase.table("skill_tracker").select("id,tickets_count").ilike(
            "skill_name", f"%{tag}%"
        ).execute()
        
        for skill in (result.data or []):
            new_count = (skill.get("tickets_count") or 0) + count
            supabase.table("skill_tracker").update({
                "tickets_count": new_count
            }).eq("id", skill.get("id")).execute()
            updated += 1
    
    return JSONResponse({"status": "ok", "tags_processed": len(tag_counts)})


# ============================================
# AI Implementation Memories
# ============================================

@router.post("/api/career/add-ai-memory")
async def add_ai_implementation_memory(request: Request):
    """Add a memory specifically for AI implementation work in this app."""
    data = await request.json()
    title = data.get("title")
    description = data.get("description")
    skills = data.get("skills", "AI/ML Integration, LLM APIs, Prompt Engineering")
    
    if not title:
        return JSONResponse({"error": "Title is required"}, status_code=400)
    
    metadata = json.dumps({
        "app": "v0agent",
        "type": "ai_implementation",
        "features": data.get("features", [])
    })
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("career_memories").insert({
        "memory_type": "ai_implementation",
        "title": title,
        "description": description,
        "source_type": "codebase",
        "skills": skills,
        "is_pinned": False,
        "is_ai_work": True,
        "metadata": metadata
    }).execute()
    
    memory_id = result.data[0].get("id") if result.data else None
    
    return JSONResponse({"status": "ok", "id": memory_id})


@router.get("/api/career/ai-memories")
async def get_ai_memories():
    """Get all AI implementation memories."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    result = supabase.table("career_memories").select("*").eq(
        "is_ai_work", True
    ).order("is_pinned", desc=True).order("created_at", desc=True).execute()
    
    return JSONResponse(result.data or [])


@router.delete("/api/career/ai-memories/{memory_id}")
async def delete_ai_memory(memory_id: int):
    """Delete an AI implementation memory."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("career_memories").delete().eq("id", memory_id).eq("is_ai_work", True).execute()
    return JSONResponse({"status": "ok", "deleted": memory_id})


@router.post("/api/career/ai-memories/compress")
async def compress_ai_memories(request: Request):
    """Compress AI memories by removing duplicates and merging similar entries."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    # Get all AI memories
    result = supabase.table("career_memories").select(
        "id,title,description,technologies,skills"
    ).eq("is_ai_work", True).order("created_at", desc=True).execute()
    
    memories = result.data or []
    
    if len(memories) <= 1:
        return JSONResponse({"status": "ok", "removed": 0, "merged": 0, "message": "Not enough memories to compress"})
    
    removed = 0
    merged = 0
    
    # Find and remove exact duplicates (same title)
    seen_titles = {}
    for mem in memories:
        title_lower = (mem.get('title') or '').lower().strip()
        if title_lower in seen_titles:
            # Delete duplicate
            supabase.table("career_memories").delete().eq("id", mem.get('id')).execute()
            removed += 1
        else:
            seen_titles[title_lower] = mem.get('id')
    
    # Find similar entries (same technologies) and merge their skills
    if len(memories) > 3:
        tech_groups = {}
        for mem in memories:
            tech = (mem.get('technologies') or '').lower().strip()
            if tech:
                if tech not in tech_groups:
                    tech_groups[tech] = []
                tech_groups[tech].append(mem)
        
        # Merge groups with same technology
        for tech, group in tech_groups.items():
            if len(group) > 1:
                # Keep the first one, merge skills from others
                keeper = group[0]
                all_skills = set((keeper.get('skills') or '').split(','))
                all_skills = {s.strip() for s in all_skills if s.strip()}
                
                for other in group[1:]:
                    other_skills = (other.get('skills') or '').split(',')
                    for s in other_skills:
                        if s.strip():
                            all_skills.add(s.strip())
                    # Delete the duplicate
                    supabase.table("career_memories").delete().eq("id", other.get('id')).execute()
                    removed += 1
                
                # Update the keeper with merged skills
                if all_skills:
                    supabase.table("career_memories").update({
                        "skills": ','.join(sorted(all_skills))
                    }).eq("id", keeper.get('id')).execute()
                    merged += 1
    
    return JSONResponse({
        "status": "ok",
        "removed": removed,
        "merged": merged,
        "message": f"Removed {removed} duplicates, merged {merged} entries"
    })


@router.post("/api/career/assess-codebase-ai")
async def assess_codebase_with_ai(request: Request):
    """Use AI to analyze codebase and generate technical implementation memories."""
    import os
    import glob
    
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # Scan for key technical files
    py_files = glob.glob(os.path.join(workspace_root, "src/**/*.py"), recursive=True)
    py_files = [f for f in py_files if not any(x in f for x in ['__pycache__', '.venv', 'venv', '.git'])][:30]
    
    # Build code context
    code_samples = []
    for filepath in py_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for interesting patterns
                if any(term in content.lower() for term in ['llm', 'openai', 'embedding', 'prompt', 'async def', 'fastapi', 'router', 'sqlite', 'langchain', 'anthropic']):
                    rel_path = os.path.relpath(filepath, workspace_root)
                    # Get first 100 lines or key functions
                    lines = content.split('\n')[:80]
                    code_samples.append(f"### {rel_path}\n```python\n{''.join(lines[:60]) if len(lines) > 60 else chr(10).join(lines)}\n```")
        except Exception:
            pass
    
    if not code_samples:
        return JSONResponse({"status": "error", "message": "No relevant code found"})
    
    # Limit context
    context = "\n\n".join(code_samples[:10])
    
    prompt = f"""Analyze this codebase and identify 3-5 **technical** AI/ML implementation patterns. Focus on:
1. LLM integration patterns (API usage, prompt engineering, streaming)
2. Architecture decisions (async patterns, caching, error handling)
3. Data flow and state management
4. Performance optimizations
5. Security/best practices

For each pattern found, provide:
- A technical title (e.g., "Async LLM Streaming with Fallback", "Multi-Provider Model Routing")
- Technical description of how it's implemented
- Key technologies/libraries used
- Code-level insights

Codebase samples:
{context}

Respond in JSON format:
{{
  "patterns": [
    {{
      "title": "Technical pattern name",
      "description": "Detailed technical description of implementation",
      "technologies": "tech1, tech2, tech3",
      "code_insight": "Specific code-level observation"
    }}
  ]
}}"""
    
    try:
        # Lazy import for backward compatibility
        from ..llm import ask as ask_llm
        response = ask_llm(prompt, model="gpt-4o-mini")
        # Parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            patterns = data.get("patterns", [])
            
            added = []
            supabase = get_supabase_client()
            if supabase:
                for pattern in patterns[:5]:
                    title = pattern.get("title", "Unknown Pattern")
                    description = pattern.get("description", "")
                    technologies = pattern.get("technologies", "")
                    code_insight = pattern.get("code_insight", "")
                    
                    full_desc = f"{description}\n\n**Code Insight:** {code_insight}" if code_insight else description
                    
                    # Check for duplicates
                    existing = supabase.table("career_memories").select("id").eq(
                        "title", title
                    ).eq("is_ai_work", True).execute()
                    
                    if not existing.data:
                        supabase.table("career_memories").insert({
                            "memory_type": "ai_implementation",
                            "title": title,
                            "description": full_desc,
                            "source_type": "codebase_ai",
                            "skills": technologies,
                            "is_pinned": False,
                            "is_ai_work": True
                        }).execute()
                        added.append(title)
            
            return JSONResponse({"status": "ok", "added": added, "count": len(added)})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})
    
    return JSONResponse({"status": "error", "message": "Failed to parse AI response"})

# ============================================
# Documentation-Based Career Features
# ============================================

@router.get("/api/career/docs/adrs")
async def get_documentation_adrs():
    """
    Get Architecture Decision Records from repository documentation.
    
    Returns ADRs with parsed metadata including technologies and status.
    """
    from ..services.documentation_reader import get_adrs
    
    try:
        adrs = get_adrs()
        return JSONResponse({
            "status": "ok",
            "count": len(adrs),
            "adrs": adrs
        })
    except Exception as e:
        logger.error(f"Error reading ADRs: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/api/career/docs/ai-implementations")
async def get_documentation_ai_implementations():
    """
    Get AI implementation records extracted from repository documentation.
    
    Scans docs for AI/ML-related content and returns structured implementation records.
    """
    from ..services.documentation_reader import get_ai_implementations
    
    try:
        implementations = get_ai_implementations()
        return JSONResponse({
            "status": "ok",
            "count": len(implementations),
            "implementations": implementations
        })
    except Exception as e:
        logger.error(f"Error extracting AI implementations: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/api/career/docs/skill-evidence")
async def get_documentation_skill_evidence():
    """
    Get skill evidence extracted from repository documentation.
    
    Returns technologies/skills mentioned in docs with their source locations.
    """
    from ..services.documentation_reader import get_skill_evidence
    
    try:
        evidence = get_skill_evidence()
        return JSONResponse({
            "status": "ok",
            "skills_count": len(evidence),
            "evidence": evidence
        })
    except Exception as e:
        logger.error(f"Error extracting skill evidence: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/api/career/docs/assess-codebase")
async def get_codebase_assessment():
    """
    Get comprehensive codebase assessment.
    
    Analyzes project structure, languages, frameworks, and metrics.
    """
    from ..services.documentation_reader import assess_codebase
    
    try:
        assessment = assess_codebase()
        return JSONResponse({
            "status": "ok",
            "assessment": assessment
        })
    except Exception as e:
        logger.error(f"Error assessing codebase: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/api/career/docs/sync-to-memories")
async def sync_docs_to_memories():
    """
    Sync documentation-based AI implementations to career memories.
    
    This imports AI implementation records from docs into the career_memories table.
    """
    from ..services.documentation_reader import get_ai_implementations
    
    try:
        implementations = get_ai_implementations()
        added = []
        updated = []
        
        supabase = get_supabase_client()
        if not supabase:
            return JSONResponse({"error": "Database not configured"}, status_code=500)
        
        for impl in implementations:
            title = impl.get("title", "Unknown Implementation")
            description = impl.get("summary", "")
            technologies = ", ".join(impl.get("technologies", []))
            source = impl.get("source", "docs")
            
            # Check if already exists
            existing = supabase.table("career_memories").select("id").eq(
                "title", title
            ).eq("source_type", "documentation").execute()
            
            if existing.data:
                # Update existing
                supabase.table("career_memories").update({
                    "description": description,
                    "skills": technologies
                }).eq("id", existing.data[0].get("id")).execute()
                updated.append(title)
            else:
                # Insert new
                supabase.table("career_memories").insert({
                    "memory_type": "ai_implementation",
                    "title": title,
                    "description": description,
                    "source_type": "documentation",
                    "skills": technologies,
                    "is_pinned": False,
                    "is_ai_work": True,
                    "metadata": json.dumps({"source": source})
                }).execute()
                added.append(title)
        
        return JSONResponse({
            "status": "ok",
            "added": added,
            "updated": updated,
            "added_count": len(added),
            "updated_count": len(updated)
        })
    except Exception as e:
        logger.error(f"Error syncing docs to memories: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/api/career/backends/status")
async def get_backend_status():
    """
    Get status of all configured Supabase backends.
    
    Shows which backends (default, career, analytics) are configured.
    """
    from ..infrastructure.supabase_multi import list_backends
    
    try:
        backends = list_backends()
        return JSONResponse({
            "status": "ok",
            "backends": backends
        })
    except Exception as e:
        logger.error(f"Error checking backends: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)