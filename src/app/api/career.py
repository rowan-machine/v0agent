# src/app/api/career.py
"""
Career API Routes - FastAPI endpoints for career development features.

This module delegates to CareerCoachAgent (Checkpoint 2.3) for AI-powered features,
maintaining backward compatibility through adapter functions.

Migration Status:
- CareerCoachAgent: src/app/agents/career_coach.py (new agent implementation)
- This file: Adapters + FastAPI routes (will be slimmed down over time)
"""

# Imports and router definition moved to top
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from ..db import connect
from ..services import tickets_supabase
# llm.ask removed - use lazy imports inside functions for backward compatibility
import json

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

# Place the /api/signals/status endpoint after router is defined
@router.post("/api/signals/status")
async def update_signal_status(request: Request):
    """Update the status of a signal and log feedback."""
    data = await request.json()
    meeting_id = data.get("meeting_id")
    signal_type = data.get("signal_type")
    signal_text = data.get("signal_text")
    status = data.get("status")

    if not (meeting_id and signal_type and signal_text and status):
        return JSONResponse({"error": "Missing required fields"}, status_code=400)

    with connect() as conn:
        # Update or insert signal status
        conn.execute("""
            INSERT INTO signal_status (meeting_id, signal_type, signal_text, status, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(meeting_id, signal_type, signal_text)
            DO UPDATE SET status = excluded.status, updated_at = datetime('now')
        """, (meeting_id, signal_type, signal_text, status))

        # Log feedback (up for approved, down for rejected, etc.)
        feedback = None
        if status == 'approved':
            feedback = 'up'
        elif status == 'rejected':
            feedback = 'down'
        elif status == 'archived':
            feedback = 'archived'
        elif status == 'completed':
            feedback = 'completed'
        if feedback:
            conn.execute("""
                INSERT INTO signal_feedback (meeting_id, signal_type, signal_text, feedback, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(meeting_id, signal_type, signal_text)
                DO UPDATE SET feedback = excluded.feedback, created_at = datetime('now')
            """, (meeting_id, signal_type, signal_text, feedback))
        conn.commit()

    return JSONResponse({"status": "ok"})

def get_code_locker_code_for_sprint_tickets(conn, tickets, max_lines=40, max_chars=2000):
    """Return a dict: {ticket_id: {filename: code}} for latest code locker entries for each file in current sprint tickets."""
    code_by_ticket = {}
    for t in tickets:
        # Handle both dict and sqlite3.Row objects
        tid = t['id'] if 'id' in t.keys() else None
        ticket_code = t['ticket_id'] if 'ticket_id' in t.keys() else None
        if not tid or not ticket_code:
            continue
        # Get all filenames for this ticket from ticket_files
        files = conn.execute("SELECT filename FROM ticket_files WHERE ticket_id = ?", (tid,)).fetchall()
        code_by_ticket[ticket_code] = {}
        for f in files:
            fname = f['filename']
            # Get latest code locker entry for this file/ticket
            row = conn.execute("""
                SELECT content FROM code_locker
                WHERE filename = ? AND ticket_id = ?
                ORDER BY version DESC LIMIT 1
            """, (fname, tid)).fetchone()
            if row and row['content']:
                code = row['content']
                # Truncate for brevity
                lines = code.splitlines()
                if len(lines) > max_lines:
                    code = '\n'.join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} lines total)"
                if len(code) > max_chars:
                    code = code[:max_chars] + f"\n... (truncated, {len(row['content'])} chars total)"
                code_by_ticket[ticket_code][fname] = code
    return code_by_ticket


# CAREER_REPO_CAPABILITIES - Now imported from agents/career_coach.py (Checkpoint 2.3)
# Using the imported version for single source of truth.

# _format_capabilities_context - Now imported as format_capabilities_context from agents/career_coach.py
# Local function removed to avoid duplication.


def _load_career_summary(conn):
    row = conn.execute(
        """SELECT summary FROM career_chat_updates
           WHERE summary IS NOT NULL AND summary != ''
           ORDER BY created_at DESC
           LIMIT 1"""
    ).fetchone()
    return row["summary"] if row else None


def _load_overlay_context(conn):
    meetings = conn.execute(
        """SELECT meeting_name, synthesized_notes
           FROM meeting_summaries
           ORDER BY COALESCE(meeting_date, created_at) DESC
           LIMIT 3"""
    ).fetchall()
    docs = conn.execute(
        """SELECT source, content
           FROM docs
           ORDER BY COALESCE(document_date, created_at) DESC
           LIMIT 3"""
    ).fetchall()
    tickets = conn.execute(
        """SELECT id, ticket_id, title, description, status
           FROM tickets
           WHERE status IN ('todo', 'in_progress', 'in_review', 'blocked')
           ORDER BY created_at DESC
           LIMIT 5"""
    ).fetchall()

    # Get code locker code for these tickets
    code_locker_context = get_code_locker_code_for_sprint_tickets(conn, tickets)

    meeting_text = "\n".join([
        f"- {m['meeting_name']}: {m['synthesized_notes'][:500]}" for m in meetings
    ]) or "No recent meetings."
    doc_text = "\n".join([
        f"- {d['source']}: {d['content'][:400]}" for d in docs
    ]) or "No recent documents."
    ticket_text = "\n".join([
        f"- {t['ticket_id']} {t['title']} ({t['status']})" for t in tickets
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

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


@router.delete("/api/career/standups/{standup_id}")
async def delete_standup(standup_id: int):
    """Delete a standup update by ID."""
    with connect() as conn:
        conn.execute("DELETE FROM standup_updates WHERE id = ?", (standup_id,))
        conn.commit()
    return JSONResponse({"status": "ok"})


@router.get("/api/career/profile")
async def get_career_profile(request: Request):
    """Get the current career profile."""
    with connect() as conn:
        profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
    
    if profile:
        keys = profile.keys()
        return JSONResponse({
            "current_role": profile["current_role"],
            "target_role": profile["target_role"],
            "strengths": profile["strengths"],
            "weaknesses": profile["weaknesses"],
            "interests": profile["interests"],
            "goals": profile["goals"],
            "certifications": profile["certifications"] if "certifications" in keys else None,
            "education": profile["education"] if "education" in keys else None,
            "years_experience": profile["years_experience"] if "years_experience" in keys else None,
            "preferred_work_style": profile["preferred_work_style"] if "preferred_work_style" in keys else None,
            "industry_focus": profile["industry_focus"] if "industry_focus" in keys else None,
            "leadership_experience": profile["leadership_experience"] if "leadership_experience" in keys else None,
            "notable_projects": profile["notable_projects"] if "notable_projects" in keys else None,
            "learning_priorities": profile["learning_priorities"] if "learning_priorities" in keys else None,
            "career_timeline": profile["career_timeline"] if "career_timeline" in keys else None,
            # New fields
            "technical_specializations": profile["technical_specializations"] if "technical_specializations" in keys else None,
            "soft_skills": profile["soft_skills"] if "soft_skills" in keys else None,
            "work_achievements": profile["work_achievements"] if "work_achievements" in keys else None,
            "career_values": profile["career_values"] if "career_values" in keys else None,
            "short_term_goals": profile["short_term_goals"] if "short_term_goals" in keys else None,
            "long_term_goals": profile["long_term_goals"] if "long_term_goals" in keys else None,
            "mentorship": profile["mentorship"] if "mentorship" in keys else None,
            "networking": profile["networking"] if "networking" in keys else None,
            "languages": profile["languages"] if "languages" in keys else None,
        })
    return JSONResponse({}, status_code=404)


@router.post("/api/career/profile")
async def update_career_profile(request: Request):
    """Update the career profile."""
    data = await request.json()
    
    with connect() as conn:
        conn.execute("""
            INSERT INTO career_profile (id, current_role, target_role, strengths, weaknesses, interests, goals,
                certifications, education, years_experience, preferred_work_style, industry_focus,
                leadership_experience, notable_projects, learning_priorities, career_timeline,
                technical_specializations, soft_skills, work_achievements, career_values,
                short_term_goals, long_term_goals, mentorship, networking, languages)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                current_role = excluded.current_role,
                target_role = excluded.target_role,
                strengths = excluded.strengths,
                weaknesses = excluded.weaknesses,
                interests = excluded.interests,
                goals = excluded.goals,
                certifications = excluded.certifications,
                education = excluded.education,
                years_experience = excluded.years_experience,
                preferred_work_style = excluded.preferred_work_style,
                industry_focus = excluded.industry_focus,
                leadership_experience = excluded.leadership_experience,
                notable_projects = excluded.notable_projects,
                learning_priorities = excluded.learning_priorities,
                career_timeline = excluded.career_timeline,
                technical_specializations = excluded.technical_specializations,
                soft_skills = excluded.soft_skills,
                work_achievements = excluded.work_achievements,
                career_values = excluded.career_values,
                short_term_goals = excluded.short_term_goals,
                long_term_goals = excluded.long_term_goals,
                mentorship = excluded.mentorship,
                networking = excluded.networking,
                languages = excluded.languages,
                updated_at = datetime('now')
        """, (
            data.get("current_role"),
            data.get("target_role"),
            data.get("strengths"),
            data.get("weaknesses"),
            data.get("interests"),
            data.get("goals"),
            data.get("certifications"),
            data.get("education"),
            data.get("years_experience"),
            data.get("preferred_work_style"),
            data.get("industry_focus"),
            data.get("leadership_experience"),
            data.get("notable_projects"),
            data.get("learning_priorities"),
            data.get("career_timeline"),
            data.get("technical_specializations"),
            data.get("soft_skills"),
            data.get("work_achievements"),
            data.get("career_values"),
            data.get("short_term_goals"),
            data.get("long_term_goals"),
            data.get("mentorship"),
            data.get("networking"),
            data.get("languages")
        ))
    
    return JSONResponse({"status": "ok"})


@router.get("/api/career/suggestions")
async def get_career_suggestions(request: Request, limit: int = Query(10, ge=1, le=50)):
    """Get career development suggestions."""
    with connect() as conn:
        suggestions = conn.execute("""
            SELECT * FROM career_suggestions 
            WHERE status IN ('suggested', 'accepted', 'in_progress', 'dismissed', 'completed')
            ORDER BY 
                CASE status 
                    WHEN 'in_progress' THEN 1
                    WHEN 'accepted' THEN 2
                    WHEN 'suggested' THEN 3
                    WHEN 'dismissed' THEN 4
                    WHEN 'completed' THEN 5
                END,
                created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    
    return JSONResponse([dict(s) for s in suggestions])


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

        with connect() as conn:
            # Get career profile
            profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
            if not profile:
                return JSONResponse({"error": "No career profile found"}, status_code=404)
            
            overlay_context = _load_overlay_context(conn) if include_context else None
            
            # Delegate to CareerCoachAgent adapter
            result = await generate_suggestions_adapter(
                profile=dict(profile),
                context=overlay_context,
                include_context=include_context,
                db_connection=conn,
            )
            
            if result.get("status") == "error":
                return JSONResponse({"error": result.get("error", "Unknown error")}, status_code=500)
            
            # Insert suggestions into database for persistence
            suggestions_data = result.get("suggestions", [])
            created_ids = []
            for sugg in suggestions_data:
                cur = conn.execute("""
                    INSERT INTO career_suggestions 
                    (suggestion_type, title, description, rationale, difficulty, time_estimate, related_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sugg.get('suggestion_type', 'skill_building'),
                    sugg.get('title', 'Growth Opportunity'),
                    sugg.get('description', ''),
                    sugg.get('rationale', ''),
                    sugg.get('difficulty', 'intermediate'),
                    sugg.get('time_estimate', 'varies'),
                    sugg.get('related_goal', '')
                ))
                created_ids.append(cur.lastrowid)
                
                # Sync to Supabase (fire-and-forget)
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
    with connect() as conn:
        rows = conn.execute(
            """SELECT message, response, summary, created_at
               FROM career_chat_updates
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
    return JSONResponse([dict(r) for r in rows][::-1])


@router.get("/api/career/chat/summary")
async def get_career_chat_summary(request: Request):
    """Return the latest career status summary."""
    with connect() as conn:
        summary = _load_career_summary(conn) or ""
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

    with connect() as conn:
        profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
        if not profile:
            return JSONResponse({"error": "No career profile found"}, status_code=404)

        overlay_context = _load_overlay_context(conn) if include_context else None

        # Delegate to CareerCoachAgent adapter
        try:
            result = await career_chat_adapter(
                message=message,
                profile=dict(profile),
                context=overlay_context,
                include_context=include_context,
                db_connection=conn,
            )
            
            # Store in chat history for persistence
            conn.execute(
                """INSERT INTO career_chat_updates (message, response, summary)
                   VALUES (?, ?, ?)""",
                (message, result.get("response", ""), result.get("summary", ""))
            )
            conn.commit()
            
            # Sync to Supabase (fire-and-forget)
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
    # Use ask_llm from module-level import
    
    with connect() as conn:
        # Gather context - handle missing tables gracefully
        profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
        
        try:
            skills = conn.execute("""
                SELECT skill_name, category, proficiency_level 
                FROM skill_tracker 
                WHERE proficiency_level > 0 
                ORDER BY proficiency_level DESC 
                LIMIT 15
            """).fetchall()
        except:
            skills = []
        
        # Check if completed_projects_bank table exists
        try:
            projects = conn.execute("""
                SELECT title, description, technologies, impact 
                FROM completed_projects_bank 
                ORDER BY completed_date DESC 
                LIMIT 10
            """).fetchall()
        except:
            projects = []
        
        # Check if ai_implementation_memories table exists
        try:
            ai_memories = conn.execute("""
                SELECT title, description, technologies 
                FROM ai_implementation_memories 
                ORDER BY created_at DESC 
                LIMIT 5
            """).fetchall()
        except:
            ai_memories = []
        
        # Format context
        profile_ctx = f"""
Current Role: {profile['current_role'] if profile else 'Not set'}
Target Role: {profile['target_role'] if profile else 'Not set'}
Strengths: {profile['strengths'] if profile else 'Not set'}
Goals: {profile['goals'] if profile else 'Not set'}
""" if profile else "No profile set"
        
        skills_ctx = "\n".join([f"- {s['skill_name']} ({s['category']}): {s['proficiency_level']}%" for s in skills]) if skills else "No skills tracked"
        projects_ctx = "\n".join([f"- {p['title']}: {p['description'][:100]}..." for p in projects]) if projects else "No projects"
        ai_ctx = "\n".join([f"- {m['title']}: {m['technologies']}" for m in ai_memories]) if ai_memories else "No AI implementations"
        
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
        agent = get_career_coach_agent(db_connection=conn)
        insights = await agent.ask_llm(
            prompt=prompt,
            task_type="career_insights",
        )
        
        return JSONResponse({
            "status": "ok", 
            "insights": insights, 
            "run_id": agent.last_run_id
        })


# ----------------------
# Career Tweaks Safe API
# ----------------------

@router.get("/api/career/tweaks")
async def get_career_tweaks(request: Request):
    """Get saved career tweaks."""
    with connect() as conn:
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS career_tweaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        tweaks = conn.execute("SELECT * FROM career_tweaks ORDER BY created_at DESC").fetchall()
    return JSONResponse({"tweaks": [dict(t) for t in tweaks]})


@router.post("/api/career/tweaks")
async def save_career_tweak(request: Request):
    """Save a new career tweak."""
    data = await request.json()
    content = (data.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS career_tweaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("INSERT INTO career_tweaks (content) VALUES (?)", (content,))
        conn.commit()
    return JSONResponse({"status": "ok"})


@router.delete("/api/career/tweaks/{tweak_id}")
async def delete_career_tweak(tweak_id: int):
    """Delete a career tweak."""
    with connect() as conn:
        conn.execute("DELETE FROM career_tweaks WHERE id = ?", (tweak_id,))
        conn.commit()
    return JSONResponse({"status": "ok"})


@router.post("/api/career/suggestions/{suggestion_id}/status")
async def update_suggestion_status(suggestion_id: int, request: Request):
    """Update the status of a career suggestion."""
    data = await request.json()
    status = data.get("status")
    
    with connect() as conn:
        conn.execute("""
            UPDATE career_suggestions 
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (status, suggestion_id))
    
    return JSONResponse({"status": "ok"})


@router.post("/api/career/suggestions/{suggestion_id}/to-ticket")
async def convert_suggestion_to_ticket(suggestion_id: int, request: Request):
    """Convert a career suggestion to a ticket."""
    try:
        with connect() as conn:
            suggestion = conn.execute(
                "SELECT * FROM career_suggestions WHERE id = ?",
                (suggestion_id,)
            ).fetchone()
            
            if not suggestion:
                return JSONResponse({"error": "Suggestion not found"}, status_code=404)
            
            # Create ticket
            ticket_id = f"CAREER-{suggestion_id}"
            cur = conn.execute("""
                INSERT INTO tickets (ticket_id, title, description, status, priority, tags)
                VALUES (?, ?, ?, 'backlog', 'medium', 'career,growth')
            """, (
                ticket_id,
                suggestion["title"],
                f"{suggestion['description']}\n\n**Rationale:** {suggestion['rationale']}\n**Difficulty:** {suggestion['difficulty']}\n**Time:** {suggestion['time_estimate']}"
            ))
            
            ticket_db_id = cur.lastrowid
            
            # Update suggestion
            conn.execute("""
                UPDATE career_suggestions 
                SET status = 'accepted', 
                    converted_to_ticket = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (ticket_db_id, suggestion_id))
        
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
    # Use ask_llm from module-level import (from ..llm import ask as ask_llm)
    
    try:
        with connect() as conn:
            # Get all active suggestions (status is 'suggested' not 'pending')
            rows = conn.execute("""
                SELECT id, title, description, suggestion_type, rationale
                FROM career_suggestions 
                WHERE status = 'suggested'
                ORDER BY created_at DESC
            """).fetchall()
            
            if len(rows) < 2:
                return JSONResponse({"status": "ok", "merged": 0, "removed": 0, "message": "Not enough suggestions to compress"})
            
            # Prepare for LLM analysis
            suggestions_text = "\n".join([
                f"[ID:{r['id']}] {r['title']}: {r['description'][:200]}"
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
                import json
                # Clean response
                response = response.strip()
                if response.startswith("```"):
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                result = json.loads(response)
            except:
                return JSONResponse({"status": "ok", "merged": 0, "removed": 0, "message": "Could not parse LLM response"})
            
            merged = 0
            removed = 0
            
            # Process groups - keep first, remove rest
            for group in result.get("groups", []):
                if len(group) > 1:
                    # Keep first ID, remove rest
                    to_remove = group[1:]
                    for rid in to_remove:
                        conn.execute("UPDATE career_suggestions SET status = 'dismissed' WHERE id = ?", (rid,))
                        merged += 1
            
            # Process removals
            for rid in result.get("remove", []):
                conn.execute("UPDATE career_suggestions SET status = 'dismissed' WHERE id = ?", (rid,))
                removed += 1
            
            conn.commit()
            
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
    with connect() as conn:
        standups = conn.execute("""
            SELECT * FROM standup_updates 
            ORDER BY standup_date DESC, created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return JSONResponse([dict(s) for s in standups])


@router.get("/career/standups")
async def standups_page(request: Request):
    """Render the standups and career chat page."""
    return templates.TemplateResponse("standups.html", {"request": request})


@router.get("/api/career/standups/today")
async def get_today_standup(request: Request):
    """Get today's standup if it exists."""
    from datetime import date
    today = date.today().isoformat()
    
    with connect() as conn:
        standup = conn.execute("""
            SELECT * FROM standup_updates 
            WHERE standup_date = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (today,)).fetchone()
    
    if standup:
        return JSONResponse(dict(standup))
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
    
    with connect() as conn:
        # If skip_feedback, just save without AI processing
        if skip_feedback:
            cur = conn.execute("""
                INSERT INTO standup_updates (standup_date, content, feedback, sentiment, key_themes)
                VALUES (?, ?, NULL, 'neutral', '')
            """, (standup_date, content))
            standup_id = cur.lastrowid
            conn.commit()
            return JSONResponse({
                "status": "ok",
                "id": standup_id,
                "feedback": None,
                "sentiment": "neutral",
                "key_themes": ""
            })
        
        # Get career profile for context
        profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
        profile_dict = dict(profile) if profile else {}
        
        # Get recent standups for pattern analysis
        recent_standups = conn.execute("""
            SELECT content, feedback, sentiment 
            FROM standup_updates 
            ORDER BY standup_date DESC 
            LIMIT 5
        """).fetchall()
        recent_standups_list = [dict(s) for s in recent_standups]
        
        # Get active tickets for context
        tickets = conn.execute("""
            SELECT ticket_id, title, status 
            FROM tickets 
            WHERE status IN ('todo', 'in_progress', 'in_review', 'blocked')
            AND in_sprint = 1
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()
        tickets_list = [dict(t) for t in tickets]
        
        # Delegate to CareerCoachAgent for AI feedback
        try:
            result = await analyze_standup_adapter(
                content=content,
                profile=profile_dict,
                tickets=tickets_list,
                recent_standups=recent_standups_list,
                db_connection=conn,
            )
            
            feedback = result.get("feedback", "")
            sentiment = result.get("sentiment", "neutral")
            key_themes = result.get("key_themes", "")
                
        except Exception as e:
            feedback = f"Could not generate feedback: {str(e)}"
            sentiment = 'neutral'
            key_themes = ''
        
        # Insert standup
        cur = conn.execute("""
            INSERT INTO standup_updates (standup_date, content, feedback, sentiment, key_themes)
            VALUES (?, ?, ?, ?, ?)
        """, (standup_date, content, feedback, sentiment, key_themes))
        
        standup_id = cur.lastrowid
        conn.commit()
    
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
    
    with connect() as conn:
        # Get active sprint tickets
        tickets = conn.execute("""
            SELECT t.id, t.ticket_id, t.title, t.status, t.description
            FROM tickets t
            WHERE t.status IN ('todo', 'in_progress', 'in_review', 'blocked')
            AND t.in_sprint = 1
            ORDER BY 
                CASE t.status 
                    WHEN 'in_progress' THEN 1
                    WHEN 'blocked' THEN 2
                    WHEN 'in_review' THEN 3
                    WHEN 'todo' THEN 4
                END
        """).fetchall()
        tickets_list = [dict(t) for t in tickets]
        
        # Get ticket files for each active ticket
        ticket_files_map = {}
        for t in tickets:
            files = conn.execute("""
                SELECT tf.filename, tf.file_type, tf.description, tf.base_content,
                       (SELECT MAX(version) FROM code_locker cl 
                        WHERE cl.filename = tf.filename AND cl.ticket_id = tf.ticket_id) as latest_version
                FROM ticket_files tf
                WHERE tf.ticket_id = ?
            """, (t['id'],)).fetchall()
            if files:
                ticket_files_map[t['ticket_id']] = [dict(f) for f in files]
        
        # Get recent code locker changes (last 24-48 hours)
        code_changes = conn.execute("""
            SELECT cl.filename, cl.ticket_id, cl.version, cl.notes, cl.is_initial,
                   t.ticket_id as ticket_code, t.title as ticket_title,
                   cl.created_at
            FROM code_locker cl
            LEFT JOIN tickets t ON cl.ticket_id = t.id
            WHERE cl.created_at >= datetime('now', '-2 days')
            ORDER BY cl.created_at DESC
            LIMIT 20
        """).fetchall()
        code_changes_list = [dict(c) for c in code_changes]
        
        # Get yesterday's standup for continuity
        yesterday_standup = conn.execute("""
            SELECT content, feedback 
            FROM standup_updates 
            WHERE standup_date < date('now')
            ORDER BY standup_date DESC 
            LIMIT 1
        """).fetchone()
        yesterday_standup_dict = dict(yesterday_standup) if yesterday_standup else None
        
        # Add code locker code context for current sprint tickets
        code_locker_code = get_code_locker_code_for_sprint_tickets(conn, tickets)
        
        # Delegate to CareerCoachAgent for AI suggestion
        try:
            result = await suggest_standup_adapter(
                tickets=tickets_list,
                ticket_files_map=ticket_files_map,
                code_changes=code_changes_list,
                code_locker_code=code_locker_code,
                yesterday_standup=yesterday_standup_dict,
                db_connection=conn,
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
        "code_changes_count": len(code_changes),
        "files_tracked": sum(len(f) for f in ticket_files_map.values())
    })


# ----------------------
# Code Locker API
# ----------------------

@router.get("/api/career/code-locker")
async def get_code_locker(request: Request, ticket_id: int = None, filename: str = None):
    """Get code locker entries, optionally filtered by ticket or filename."""
    with connect() as conn:
        query = """
            SELECT cl.*, t.ticket_id as ticket_code, t.title as ticket_title
            FROM code_locker cl
            LEFT JOIN tickets t ON cl.ticket_id = t.id
            WHERE 1=1
        """
        params = []
        
        if ticket_id:
            query += " AND cl.ticket_id = ?"
            params.append(ticket_id)
        if filename:
            query += " AND cl.filename LIKE ?"
            params.append(f"%{filename}%")
        
        query += " ORDER BY cl.filename, cl.version DESC"
        
        entries = conn.execute(query, params).fetchall()
    
    return JSONResponse([dict(e) for e in entries])


@router.get("/api/career/code-locker/files")
async def get_code_locker_files(request: Request):
    """Get unique filenames in code locker with latest version info."""
    with connect() as conn:
        files = conn.execute("""
            SELECT filename, 
                   ticket_id,
                   MAX(version) as latest_version,
                   COUNT(*) as version_count,
                   MAX(created_at) as last_updated
            FROM code_locker
            GROUP BY filename, ticket_id
            ORDER BY last_updated DESC
        """).fetchall()
    
    return JSONResponse([dict(f) for f in files])


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
    
    with connect() as conn:
        # Get current version for this file
        existing = conn.execute("""
            SELECT MAX(version) as max_version 
            FROM code_locker 
            WHERE filename = ?
        """, (filename,)).fetchone()
        
        next_version = (existing['max_version'] or 0) + 1
        
        # If this is marked as initial but versions exist, warn
        if is_initial and existing['max_version']:
            is_initial = False  # Can't be initial if versions exist
        
        # If no versions exist, this is initial
        if not existing['max_version']:
            is_initial = True
        
        cur = conn.execute("""
            INSERT INTO code_locker (filename, content, ticket_id, version, notes, is_initial)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (filename, content, ticket_id, next_version, notes, 1 if is_initial else 0))
        
        entry_id = cur.lastrowid
        conn.commit()
    
    return JSONResponse({
        "status": "ok",
        "id": entry_id,
        "version": next_version,
        "is_initial": is_initial
    })


@router.get("/api/career/code-locker/{entry_id}")
async def get_code_locker_entry(entry_id: int):
    """Get a specific code locker entry."""
    with connect() as conn:
        entry = conn.execute("""
            SELECT cl.*, t.ticket_id as ticket_code, t.title as ticket_title
            FROM code_locker cl
            LEFT JOIN tickets t ON cl.ticket_id = t.id
            WHERE cl.id = ?
        """, (entry_id,)).fetchone()
    
    if not entry:
        return JSONResponse({"error": "Entry not found"}, status_code=404)
    
    return JSONResponse(dict(entry))


@router.get("/api/career/code-locker/diff/{filename}")
async def get_code_diff(filename: str, v1: int = Query(...), v2: int = Query(...)):
    """Get diff between two versions of a file."""
    import difflib
    
    with connect() as conn:
        version1 = conn.execute("""
            SELECT content FROM code_locker 
            WHERE filename = ? AND version = ?
        """, (filename, v1)).fetchone()
        
        version2 = conn.execute("""
            SELECT content FROM code_locker 
            WHERE filename = ? AND version = ?
        """, (filename, v2)).fetchone()
    
    if not version1 or not version2:
        return JSONResponse({"error": "One or both versions not found"}, status_code=404)
    
    # Generate unified diff
    diff = list(difflib.unified_diff(
        version1['content'].splitlines(keepends=True),
        version2['content'].splitlines(keepends=True),
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
    with connect() as conn:
        conn.execute("DELETE FROM code_locker WHERE id = ?", (entry_id,))
        conn.commit()
    
    return JSONResponse({"status": "ok"})


# ----------------------
# Ticket Files API
# ----------------------

@router.get("/api/career/ticket-files/{ticket_id}")
async def get_ticket_files(ticket_id: int):
    """Get files associated with a ticket."""
    with connect() as conn:
        files = conn.execute("""
            SELECT tf.*, 
                   (SELECT MAX(version) FROM code_locker cl 
                    WHERE cl.filename = tf.filename AND cl.ticket_id = tf.ticket_id) as locker_version,
                   (SELECT COUNT(*) FROM code_locker cl 
                    WHERE cl.filename = tf.filename AND cl.ticket_id = tf.ticket_id) as locker_count
            FROM ticket_files tf
            WHERE tf.ticket_id = ?
            ORDER BY tf.file_type, tf.filename
        """, (ticket_id,)).fetchall()
    
    return JSONResponse([dict(f) for f in files])


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
    
    with connect() as conn:
        try:
            cur = conn.execute("""
                INSERT INTO ticket_files (ticket_id, filename, file_type, base_content, description)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, filename, file_type, base_content, description))
            
            file_id = cur.lastrowid
            
            # If this is an 'update' file with base_content, add it to code locker as v1
            if file_type == 'update' and base_content:
                conn.execute("""
                    INSERT INTO code_locker (ticket_id, filename, content, version, notes, is_initial)
                    VALUES (?, ?, ?, 1, 'Initial/baseline version from ticket', 1)
                """, (ticket_id, filename, base_content))
            
            conn.commit()
            
            return JSONResponse({
                "status": "ok",
                "id": file_id
            })
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                return JSONResponse({"error": "File already exists for this ticket"}, status_code=400)
            raise


@router.put("/api/career/ticket-files/{file_id}")
async def update_ticket_file(file_id: int, request: Request):
    """Update a ticket file's details."""
    data = await request.json()
    
    with connect() as conn:
        updates = []
        params = []
        
        if "description" in data:
            updates.append("description = ?")
            params.append(data["description"])
        if "base_content" in data:
            updates.append("base_content = ?")
            params.append(data["base_content"])
        if "file_type" in data:
            updates.append("file_type = ?")
            params.append(data["file_type"])
        
        if updates:
            params.append(file_id)
            conn.execute(f"""
                UPDATE ticket_files SET {', '.join(updates)} WHERE id = ?
            """, params)
            conn.commit()
    
    return JSONResponse({"status": "ok"})


@router.delete("/api/career/ticket-files/{file_id}")
async def delete_ticket_file(file_id: int):
    """Delete a ticket file."""
    with connect() as conn:
        conn.execute("DELETE FROM ticket_files WHERE id = ?", (file_id,))
        conn.commit()
    
    return JSONResponse({"status": "ok"})


@router.get("/api/career/tickets-with-files")
async def get_tickets_with_files():
    """Get all active tickets with their associated files for code locker selection."""
    with connect() as conn:
        tickets = conn.execute("""
            SELECT t.id, t.ticket_id, t.title, t.status
            FROM tickets t
            WHERE t.status IN ('todo', 'in_progress', 'in_review', 'blocked')
            AND t.in_sprint = 1
            ORDER BY 
                CASE t.status 
                    WHEN 'in_progress' THEN 1
                    WHEN 'blocked' THEN 2
                    WHEN 'in_review' THEN 3
                    WHEN 'todo' THEN 4
                END
        """).fetchall()
        
        result = []
        for ticket in tickets:
            # Get files for this ticket
            files = conn.execute("""
                SELECT tf.id, tf.filename, tf.file_type, tf.description,
                       (SELECT MAX(version) FROM code_locker cl 
                        WHERE cl.filename = tf.filename AND cl.ticket_id = tf.ticket_id) as latest_version
                FROM ticket_files tf
                WHERE tf.ticket_id = ?
                ORDER BY tf.file_type, tf.filename
            """, (ticket['id'],)).fetchall()
            
            result.append({
                **dict(ticket),
                "files": [dict(f) for f in files]
            })
    
    return JSONResponse(result)


@router.get("/api/career/code-locker/next-version")
async def get_next_version(filename: str = Query(...), ticket_id: int = Query(None)):
    """Get the next version number for a file in the locker."""
    with connect() as conn:
        # Check for existing versions
        query = "SELECT MAX(version) as max_version FROM code_locker WHERE filename = ?"
        params = [filename]
        
        if ticket_id:
            query += " AND ticket_id = ?"
            params.append(ticket_id)
        
        existing = conn.execute(query, params).fetchone()
        next_version = (existing['max_version'] or 0) + 1
        
        # Check if this file is linked to a ticket
        ticket_file = None
        if ticket_id:
            ticket_file = conn.execute("""
                SELECT tf.*, t.ticket_id as ticket_code
                FROM ticket_files tf
                JOIN tickets t ON tf.ticket_id = t.id
                WHERE tf.filename = ? AND tf.ticket_id = ?
            """, (filename, ticket_id)).fetchone()
        
        return JSONResponse({
            "filename": filename,
            "next_version": next_version,
            "is_new_file": existing['max_version'] is None,
            "ticket_file": dict(ticket_file) if ticket_file else None
        })


# ----------------------
# Career Chat API
# ----------------------

@router.post("/api/career/chat")
async def career_chat(request: Request):
    """Chat with the career agent about sprint progress, standups, and career advice."""
    data = await request.json()
    message = (data.get("message") or "").strip()
    history = data.get("history", [])
    
    if not message:
        return JSONResponse({"error": "Message is required"}, status_code=400)
    
    with connect() as conn:
        # Gather context
        
        # Career profile
        profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
        
        # Active sprint tickets
        tickets = conn.execute("""
            SELECT t.ticket_id, t.title, t.status, t.description, t.sprint_points
            FROM tickets t
            WHERE t.status IN ('todo', 'in_progress', 'in_review', 'blocked')
            AND t.in_sprint = 1
            ORDER BY 
                CASE t.status 
                    WHEN 'in_progress' THEN 1
                    WHEN 'blocked' THEN 2
                    WHEN 'in_review' THEN 3
                    WHEN 'todo' THEN 4
                END
        """).fetchall()
        
        # Recent standups
        standups = conn.execute("""
            SELECT standup_date, content, feedback, sentiment, key_themes
            FROM standup_updates 
            ORDER BY standup_date DESC
            LIMIT 7
        """).fetchall()
        
        # Sprint settings
        sprint = conn.execute("SELECT * FROM sprint_settings ORDER BY id DESC LIMIT 1").fetchone()
        
        # Recent code locker activity
        code_activity = conn.execute("""
            SELECT cl.filename, cl.version, cl.notes, cl.created_at,
                   t.ticket_id as ticket_code
            FROM code_locker cl
            LEFT JOIN tickets t ON cl.ticket_id = t.id
            WHERE cl.created_at >= datetime('now', '-7 days')
            ORDER BY cl.created_at DESC
            LIMIT 10
        """).fetchall()
        
        # Build context string
        profile_ctx = ""
        if profile:
            profile_ctx = f"""Career Profile:
    - Current Role: {profile['current_role'] or 'Not set'}
    - Target Role: {profile['target_role'] or 'Not set'}
    - Strengths: {profile['strengths'] or 'Not specified'}
    - Areas to Develop: {profile['weaknesses'] or 'Not specified'}
    - Goals: {profile['goals'] or 'Not specified'}
"""

        tickets_ctx = "Sprint Tickets:\n"
        if tickets:
            for t in tickets:
                tickets_ctx += f"- [{t['status'].upper()}] {t['ticket_id']}: {t['title']}"
                if t['sprint_points']:
                    tickets_ctx += f" ({t['sprint_points']} pts)"
                tickets_ctx += "\n"
        else:
            tickets_ctx += "No active sprint tickets.\n"

        # Add code locker code context for current sprint tickets
        code_locker_code = get_code_locker_code_for_sprint_tickets(conn, tickets)
        code_locker_context = ""
        for ticket_code, files in code_locker_code.items():
            if files:
                code_locker_context += f"\nCode for {ticket_code}:\n"
                for fname, code in files.items():
                    code_locker_context += f"- {fname} (latest):\n" + code + "\n"

        standups_ctx = "Recent Standups:\n"
        if standups:
            for s in standups:
                standups_ctx += f"- {s['standup_date']} ({s['sentiment'] or 'neutral'}): {s['content'][:150]}...\n"
        else:
            standups_ctx += "No recent standups.\n"

        sprint_ctx = ""
        if sprint:
            sprint_ctx = f"""Sprint Info:
    - Sprint #{sprint['sprint_number'] or 'N/A'}
    - Dates: {sprint['start_date'] or 'Not set'} to {sprint['end_date'] or 'Not set'}
    - Velocity: {sprint['velocity'] or 'Not set'} points
"""

        code_ctx = ""
        if code_activity:
            code_ctx = "Recent Code Activity:\n"
            for c in code_activity:
                code_ctx += f"- {c['filename']} v{c['version']} ({c['ticket_code'] or 'no ticket'}): {c['notes'] or 'no notes'}\n"

        # Format chat history
        history_ctx = ""
        if history:
            history_ctx = "Recent Conversation:\n"
            for h in history[-6:]:  # Last 6 messages
                role = "User" if h['role'] == 'user' else "Assistant"
                history_ctx += f"{role}: {h['content'][:200]}\n"

        prompt = f"""You are a supportive and insightful career coach AI assistant. You have access to the user's work context and can provide personalized advice.

{profile_ctx}
{sprint_ctx}
{tickets_ctx}
{code_locker_context}
{standups_ctx}
{code_ctx}
{history_ctx}

User's Question: {message}

Provide a helpful, encouraging response that:
- Directly addresses their question
- References specific data from their context when relevant
- Offers actionable suggestions when appropriate
- Maintains a professional but friendly tone
- Acknowledges their progress and effort
- If asked about blockers, help brainstorm solutions
- If asked about career growth, connect their work to their goals

Keep the response conversational and not too long (2-4 paragraphs typically). Be specific and practical."""

        try:
            # Lazy import for backward compatibility
            from ..llm import ask as ask_llm
            response = ask_llm(prompt, model="gpt-4o-mini")
        except Exception as e:
            response = f"I'm sorry, I encountered an error processing your request. Please try again. (Error: {str(e)})"
    
    return JSONResponse({
        "status": "ok",
        "response": response
    })


# ============================================
# Career Memories and Completed Projects
# ============================================

@router.get("/api/career/memories")
async def get_career_memories(memory_type: str = None, include_unpinned: bool = True):
    """Get career memories, optionally filtered by type."""
    with connect() as conn:
        if memory_type:
            if include_unpinned:
                rows = conn.execute("""
                    SELECT * FROM career_memories 
                    WHERE memory_type = ?
                    ORDER BY is_pinned DESC, created_at DESC
                """, (memory_type,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM career_memories 
                    WHERE memory_type = ? AND is_pinned = 1
                    ORDER BY created_at DESC
                """, (memory_type,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM career_memories 
                ORDER BY is_pinned DESC, created_at DESC
            """).fetchall()
    return JSONResponse([dict(r) for r in rows])


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
    is_pinned = 1 if data.get("is_pinned") else 0
    is_ai_work = 1 if data.get("is_ai_work") else 0
    metadata = json.dumps(data.get("metadata", {}))
    
    if not title:
        return JSONResponse({"error": "Title is required"}, status_code=400)
    
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO career_memories (memory_type, title, description, source_type, source_id, skills, is_pinned, is_ai_work, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (memory_type, title, description, source_type, source_id, skills, is_pinned, is_ai_work, metadata))
        conn.commit()
        memory_id = cur.lastrowid
    
    return JSONResponse({"status": "ok", "id": memory_id})


@router.post("/api/career/memories/{memory_id}/pin")
async def toggle_pin_memory(memory_id: int):
    """Toggle pin status of a memory."""
    with connect() as conn:
        row = conn.execute("SELECT is_pinned FROM career_memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return JSONResponse({"error": "Memory not found"}, status_code=404)
        
        new_status = 0 if row["is_pinned"] else 1
        conn.execute("UPDATE career_memories SET is_pinned = ?, updated_at = datetime('now') WHERE id = ?", (new_status, memory_id))
        conn.commit()
    
    return JSONResponse({"status": "ok", "is_pinned": bool(new_status)})


@router.delete("/api/career/memories/{memory_id}")
async def delete_career_memory(memory_id: int):
    """Delete a career memory (only if not pinned)."""
    with connect() as conn:
        row = conn.execute("SELECT is_pinned FROM career_memories WHERE id = ?", (memory_id,)).fetchone()
        if row and row["is_pinned"]:
            return JSONResponse({"error": "Cannot delete pinned memory. Unpin first."}, status_code=400)
        
        conn.execute("DELETE FROM career_memories WHERE id = ?", (memory_id,))
        conn.commit()
    
    return JSONResponse({"status": "ok"})


@router.get("/api/career/completed-projects")
async def get_completed_projects():
    """Get completed projects from tickets and career memories."""
    with connect() as conn:
        # Get completed tickets that haven't been synced to memories yet
        tickets = conn.execute("""
            SELECT t.*, 
                   GROUP_CONCAT(DISTINCT tf.filename) as files
            FROM tickets t
            LEFT JOIN ticket_files tf ON tf.ticket_id = t.id
            WHERE t.status IN ('done', 'complete', 'completed')
              AND NOT EXISTS (
                  SELECT 1 FROM career_memories cm 
                  WHERE cm.source_type = 'ticket' 
                    AND cm.source_id = CAST(t.id AS TEXT)
              )
            GROUP BY t.id
            ORDER BY t.updated_at DESC
            LIMIT 50
        """).fetchall()
        
        # Get completed project memories (includes synced tickets)
        memories = conn.execute("""
            SELECT * FROM career_memories 
            WHERE memory_type = 'completed_project'
            ORDER BY is_pinned DESC, created_at DESC
        """).fetchall()
    
    return JSONResponse({
        "tickets": [dict(t) for t in tickets],
        "memories": [dict(m) for m in memories]
    })


@router.post("/api/career/sync-completed-projects")
async def sync_completed_projects():
    """Sync completed tickets to career memories (without overwriting pinned ones) - reads from Supabase."""
    # Get completed tickets from Supabase
    all_tickets = tickets_supabase.get_all_tickets()
    completed_tickets = [t for t in all_tickets if t.get("status") in ('done', 'complete', 'completed')]
    
    with connect() as conn:
        # Get IDs already in memories
        existing = conn.execute("""
            SELECT source_id FROM career_memories WHERE source_type = 'ticket'
        """).fetchall()
        existing_ids = {row["source_id"] for row in existing}
        
        added = 0
        for t in completed_tickets:
            if t["id"] in existing_ids:
                continue
                
            # Create memory for completed ticket
            skills = t.get("tags") or ""
            metadata = json.dumps({
                "ticket_id": t.get("ticket_id"),
                "status": t.get("status"),
                "completed_at": t.get("updated_at")
            })
            
            conn.execute("""
                INSERT INTO career_memories (memory_type, title, description, source_type, source_id, skills, is_pinned, metadata)
                VALUES ('completed_project', ?, ?, 'ticket', ?, ?, 0, ?)
            """, (t.get("title") or "", t.get("ai_summary") or t.get("description") or "", t["id"], skills, metadata))
            added += 1
        
        conn.commit()
    
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
    with connect() as conn:
        # Get recent skill changes (skills with evidence or high proficiency)
        skills = conn.execute("""
            SELECT skill_name, category, proficiency_level, evidence, updated_at, projects_count
            FROM skill_tracker
            WHERE proficiency_level > 0
            ORDER BY 
                CASE WHEN updated_at IS NOT NULL THEN 0 ELSE 1 END,
                updated_at DESC,
                proficiency_level DESC
            LIMIT 20
        """).fetchall()
        
        # Get recent career memories as learning activities
        memories = conn.execute("""
            SELECT id, memory_type, title, description, skills, created_at
            FROM career_memories
            WHERE memory_type IN ('skill_milestone', 'achievement')
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()
        
        # Get completed projects from career_memories
        projects = conn.execute("""
            SELECT id, title, skills as technologies, description as impact, created_at as completed_date
            FROM career_memories
            WHERE memory_type = 'completed_project' OR is_ai_work = 1
            ORDER BY created_at DESC
            LIMIT 5
        """).fetchall()
        
        # Calculate summary stats
        total_skills = conn.execute("SELECT COUNT(*) FROM skill_tracker WHERE proficiency_level > 0").fetchone()[0]
        avg_proficiency = conn.execute("SELECT AVG(proficiency_level) FROM skill_tracker WHERE proficiency_level > 0").fetchone()[0] or 0
        
        # Skills by proficiency level
        skill_levels = {
            "beginner": conn.execute("SELECT COUNT(*) FROM skill_tracker WHERE proficiency_level BETWEEN 1 AND 30").fetchone()[0],
            "intermediate": conn.execute("SELECT COUNT(*) FROM skill_tracker WHERE proficiency_level BETWEEN 31 AND 60").fetchone()[0],
            "advanced": conn.execute("SELECT COUNT(*) FROM skill_tracker WHERE proficiency_level BETWEEN 61 AND 85").fetchone()[0],
            "expert": conn.execute("SELECT COUNT(*) FROM skill_tracker WHERE proficiency_level > 85").fetchone()[0],
        }
        
    return JSONResponse({
        "skills": [dict(s) for s in skills],
        "activities": [dict(m) for m in memories],
        "projects": [dict(p) for p in projects],
        "summary": {
            "total_skills": total_skills,
            "avg_proficiency": round(avg_proficiency, 1),
            "skill_levels": skill_levels
        }
    })


@router.get("/api/career/skills")
async def get_skills():
    """Get all tracked skills with categories."""
    with connect() as conn:
        skills = conn.execute("""
            SELECT * FROM skill_tracker
            ORDER BY category, proficiency_level DESC
        """).fetchall()
    
    # Group by category
    by_category = {}
    for s in skills:
        cat = s["category"] or "other"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(dict(s))
    
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
    
    with connect() as conn:
        added = 0
        
        if skills_with_categories:
            # New format: skills with their categories
            for item in skills_with_categories:
                skill_name = item.get("name") if isinstance(item, dict) else item
                category = item.get("category", "Custom") if isinstance(item, dict) else "Custom"
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO skill_tracker (skill_name, category, proficiency_level)
                        VALUES (?, ?, 0)
                    """, (skill_name, category))
                    if conn.execute("SELECT changes()").fetchone()[0] > 0:
                        added += 1
                except:
                    pass
        elif custom_skills:
            # Legacy format: just skill names (default to Custom category)
            for skill in custom_skills:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO skill_tracker (skill_name, category, proficiency_level)
                        VALUES (?, ?, 0)
                    """, (skill, "Custom"))
                    if conn.execute("SELECT changes()").fetchone()[0] > 0:
                        added += 1
                except:
                    pass
        else:
            # Add default skill categories
            for category, skills in SKILL_CATEGORIES.items():
                for skill in skills:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO skill_tracker (skill_name, category, proficiency_level)
                            VALUES (?, ?, 0)
                        """, (skill, category))
                        if conn.execute("SELECT changes()").fetchone()[0] > 0:
                            added += 1
                    except:
                        pass
        conn.commit()
    
    return JSONResponse({"status": "ok", "initialized": added})


@router.post("/api/career/skills/reset")
async def reset_skills():
    """Reset all skill data (delete all skills)."""
    with connect() as conn:
        conn.execute("DELETE FROM skill_tracker")
        conn.commit()
    return JSONResponse({"status": "ok", "message": "All skills reset"})


@router.post("/api/career/skills/remove-by-categories")
async def remove_skills_by_categories(request: Request):
    """Remove skills belonging to unselected categories."""
    data = await request.json()
    categories_to_remove = data.get("categories", [])
    
    if not categories_to_remove:
        return JSONResponse({"status": "ok", "removed": 0})
    
    with connect() as conn:
        placeholders = ",".join(["?" for _ in categories_to_remove])
        result = conn.execute(f"""
            DELETE FROM skill_tracker 
            WHERE category IN ({placeholders})
        """, categories_to_remove)
        removed = result.rowcount
        conn.commit()
    
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
            with connect() as conn:
                for skill in skills_data.get("skills", []):
                    conn.execute("""
                        INSERT INTO skill_tracker (skill_name, category, proficiency_level, evidence)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(skill_name) DO UPDATE SET
                            proficiency_level = MAX(proficiency_level, excluded.proficiency_level),
                            evidence = excluded.evidence,
                            updated_at = datetime('now')
                    """, (
                        skill.get("name"),
                        skill.get("category", "Custom"),
                        skill.get("proficiency", 30),
                        json.dumps([skill.get("evidence", "Extracted from resume")])
                    ))
                    skills_added += 1
                conn.commit()
            
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
                    if profile_match:
                        profile_data = json.loads(profile_match.group())
                        
                        # Build update query for non-null fields
                        with connect() as conn:
                            updates = []
                            values = []
                            for field in ['current_role', 'target_role', 'years_experience', 'education', 
                                         'certifications', 'technical_specializations', 'strengths',
                                         'short_term_goals', 'long_term_goals', 'soft_skills', 
                                         'languages', 'work_achievements']:
                                if field in profile_data and profile_data[field]:
                                    updates.append(f"{field} = ?")
                                    values.append(str(profile_data[field]))
                            
                            if updates:
                                # Check if profile exists
                                existing = conn.execute("SELECT id FROM career_profile LIMIT 1").fetchone()
                                if existing:
                                    values.append(existing['id'])
                                    conn.execute(f"""
                                        UPDATE career_profile 
                                        SET {', '.join(updates)}, updated_at = datetime('now')
                                        WHERE id = ?
                                    """, values)
                                else:
                                    # Insert new profile
                                    fields = [u.split(' = ')[0] for u in updates]
                                    conn.execute(f"""
                                        INSERT INTO career_profile ({', '.join(fields)})
                                        VALUES ({', '.join(['?' for _ in values])})
                                    """, values)
                                conn.commit()
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
    with connect() as conn:
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
                
                # Insert or update the specific skill
                conn.execute("""
                    INSERT INTO skill_tracker (skill_name, category, proficiency_level, evidence)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(skill_name) DO UPDATE SET
                        proficiency_level = MAX(proficiency_level, excluded.proficiency_level),
                        evidence = excluded.evidence,
                        last_used_at = datetime('now'),
                        updated_at = datetime('now')
                """, (skill, category, proficiency, evidence_json))
                skills_updated += 1
        
        conn.commit()
    
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
    """Populate skill tracker from completed projects and AI implementation memories."""
    with connect() as conn:
        skills_updated = 0
        projects_processed = 0
        memories_processed = 0
        
        # 1. Get skills/tags from completed project memories
        project_memories = conn.execute("""
            SELECT skills, title FROM career_memories 
            WHERE memory_type = 'completed_project' AND skills IS NOT NULL AND skills != ''
        """).fetchall()
        
        for mem in project_memories:
            projects_processed += 1
            for skill in (mem["skills"] or "").split(","):
                skill = skill.strip()
                if skill:
                    # Insert or update skill
                    conn.execute("""
                        INSERT INTO skill_tracker (skill_name, category, proficiency_level, projects_count)
                        VALUES (?, 'projects', 20, 1)
                        ON CONFLICT(skill_name) DO UPDATE SET
                            projects_count = projects_count + 1,
                            proficiency_level = MIN(100, proficiency_level + 5),
                            last_used_at = datetime('now'),
                            updated_at = datetime('now')
                    """, (skill,))
                    skills_updated += 1
        
        # 2. Get technologies from AI implementation memories (if table exists)
        try:
            ai_memories = conn.execute("""
                SELECT technologies, title FROM ai_implementation_memories 
                WHERE technologies IS NOT NULL AND technologies != ''
            """).fetchall()
            
            for mem in ai_memories:
                memories_processed += 1
                for tech in (mem["technologies"] or "").split(","):
                    tech = tech.strip()
                    if tech:
                        # Insert or update skill with AI category
                        conn.execute("""
                            INSERT INTO skill_tracker (skill_name, category, proficiency_level, projects_count)
                            VALUES (?, 'ai', 25, 1)
                            ON CONFLICT(skill_name) DO UPDATE SET
                                projects_count = projects_count + 1,
                                proficiency_level = MIN(100, proficiency_level + 8),
                                last_used_at = datetime('now'),
                                updated_at = datetime('now')
                        """, (tech,))
                        skills_updated += 1
        except Exception:
            pass  # ai_implementation_memories table may not exist
        
        # 3. Also process completed tickets with tags (from Supabase)
        all_tickets = tickets_supabase.get_all_tickets()
        completed_tickets = [t for t in all_tickets 
                           if t.get("status") in ('done', 'complete', 'completed')
                           and t.get("tags")]
        
        for ticket in completed_tickets:
            for tag in (ticket.get("tags") or "").split(","):
                tag = tag.strip()
                if tag:
                    conn.execute("""
                        INSERT INTO skill_tracker (skill_name, category, proficiency_level, tickets_count)
                        VALUES (?, 'tickets', 15, 1)
                        ON CONFLICT(skill_name) DO UPDATE SET
                            tickets_count = tickets_count + 1,
                            proficiency_level = MIN(100, proficiency_level + 3),
                            last_used_at = datetime('now'),
                            updated_at = datetime('now')
                    """, (tag,))
                    skills_updated += 1
        
        conn.commit()
    
    return JSONResponse({
        "status": "ok",
        "projects_processed": projects_processed,
        "memories_processed": memories_processed,
        "skills_updated": skills_updated
    })


@router.post("/api/career/skills/update-from-tickets")
async def update_skills_from_tickets():
    """Update skill counts based on completed tickets (from Supabase)."""
    # Get completed tickets from Supabase
    all_tickets = tickets_supabase.get_all_tickets()
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
    
    with connect() as conn:
        # Update skill tracker
        updated = 0
        for tag, count in tag_counts.items():
            # Try to match tag to skill
            conn.execute("""
                UPDATE skill_tracker 
                SET tickets_count = tickets_count + ?,
                    last_used_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE LOWER(skill_name) LIKE ?
            """, (count, f"%{tag}%"))
            updated += 1
        
        conn.commit()
    
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
    
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO career_memories (memory_type, title, description, source_type, skills, is_pinned, is_ai_work, metadata)
            VALUES ('ai_implementation', ?, ?, 'codebase', ?, 0, 1, ?)
        """, (title, description, skills, metadata))
        conn.commit()
        memory_id = cur.lastrowid
    
    return JSONResponse({"status": "ok", "id": memory_id})


@router.get("/api/career/ai-memories")
async def get_ai_memories():
    """Get all AI implementation memories."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT * FROM career_memories 
            WHERE is_ai_work = 1
            ORDER BY is_pinned DESC, created_at DESC
        """).fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.delete("/api/career/ai-memories/{memory_id}")
async def delete_ai_memory(memory_id: int):
    """Delete an AI implementation memory."""
    with connect() as conn:
        conn.execute("DELETE FROM career_memories WHERE id = ? AND is_ai_work = 1", (memory_id,))
        conn.commit()
    return JSONResponse({"status": "ok", "deleted": memory_id})


@router.post("/api/career/ai-memories/compress")
async def compress_ai_memories(request: Request):
    """Compress AI memories by removing duplicates and merging similar entries."""
    with connect() as conn:
        # Get all AI memories
        memories = conn.execute("""
            SELECT id, title, description, technologies, skills 
            FROM career_memories 
            WHERE is_ai_work = 1
            ORDER BY created_at DESC
        """).fetchall()
        
        if len(memories) <= 1:
            return JSONResponse({"status": "ok", "removed": 0, "merged": 0, "message": "Not enough memories to compress"})
        
        removed = 0
        merged = 0
        
        # Find and remove exact duplicates (same title)
        seen_titles = {}
        for mem in memories:
            title_lower = (mem['title'] or '').lower().strip()
            if title_lower in seen_titles:
                # Delete duplicate
                conn.execute("DELETE FROM career_memories WHERE id = ?", (mem['id'],))
                removed += 1
            else:
                seen_titles[title_lower] = mem['id']
        
        # Find similar entries (same technologies) and merge their skills
        if len(memories) > 3:
            tech_groups = {}
            for mem in memories:
                tech = (mem['technologies'] or '').lower().strip()
                if tech:
                    if tech not in tech_groups:
                        tech_groups[tech] = []
                    tech_groups[tech].append(mem)
            
            # Merge groups with same technology
            for tech, group in tech_groups.items():
                if len(group) > 1:
                    # Keep the first one, merge skills from others
                    keeper = group[0]
                    all_skills = set((keeper['skills'] or '').split(','))
                    all_skills = {s.strip() for s in all_skills if s.strip()}
                    
                    for other in group[1:]:
                        other_skills = (other['skills'] or '').split(',')
                        for s in other_skills:
                            if s.strip():
                                all_skills.add(s.strip())
                        # Delete the duplicate
                        conn.execute("DELETE FROM career_memories WHERE id = ?", (other['id'],))
                        removed += 1
                    
                    # Update the keeper with merged skills
                    if all_skills:
                        conn.execute("""
                            UPDATE career_memories 
                            SET skills = ?, updated_at = datetime('now')
                            WHERE id = ?
                        """, (','.join(sorted(all_skills)), keeper['id']))
                        merged += 1
        
        conn.commit()
    
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
            with connect() as conn:
                for pattern in patterns[:5]:
                    title = pattern.get("title", "Unknown Pattern")
                    description = pattern.get("description", "")
                    technologies = pattern.get("technologies", "")
                    code_insight = pattern.get("code_insight", "")
                    
                    full_desc = f"{description}\n\n**Code Insight:** {code_insight}" if code_insight else description
                    
                    # Check for duplicates
                    existing = conn.execute(
                        "SELECT id FROM career_memories WHERE title = ? AND is_ai_work = 1",
                        (title,)
                    ).fetchone()
                    
                    if not existing:
                        conn.execute("""
                            INSERT INTO career_memories (memory_type, title, description, source_type, skills, is_pinned, is_ai_work)
                            VALUES ('ai_implementation', ?, ?, 'codebase_ai', ?, 0, 1)
                        """, (title, full_desc, technologies))
                        added.append(title)
                        
                        # Sync to Supabase (fire-and-forget)
                        sync_memory_to_supabase({
                            'memory_type': 'ai_implementation',
                            'title': title,
                            'description': full_desc,
                            'skills': technologies,
                            'source_type': 'codebase_ai',
                            'is_ai_work': True,
                        })
                conn.commit()
            
            return JSONResponse({"status": "ok", "added": added, "count": len(added)})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})
    
    return JSONResponse({"status": "error", "message": "Failed to parse AI response"})
