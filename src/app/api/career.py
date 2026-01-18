# src/app/api/career.py

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from ..db import connect
from ..llm import ask as ask_llm
import json


CAREER_REPO_CAPABILITIES = {
    "capabilities": [
        "Meeting ingestion with signal extraction (decisions, action items, blockers, risks, ideas)",
        "DIKW pyramid promotion and synthesis for validated knowledge",
        "Tickets with AI summaries, decomposition, and implementation planning",
        "Quick AI updates with per-item actions (approve, reject, archive, create task, waiting-for)",
        "Accountability (waiting-for) tracking and status management",
        "Search and query across meetings and documents",
        "Workflow mode tracking with sprint-aligned checklists",
        "AI memory for retained context",
        "Career profile + AI-generated growth suggestions",
        "Session authentication and settings control",
    ],
    "tools_and_skills": [
        "Python 3.11 with FastAPI",
        "SQLite for local-first storage",
        "Jinja2 templates + Tailwind CSS for UI",
        "OpenAI-powered LLM integration",
        "Markdown rendering for summaries and notes",
    ],
    "unlocks_for_data_engineers": [
        "Turn meetings into prioritized, trackable work items",
        "Promote raw signals into structured knowledge (DIKW)",
        "Decompose data platform tickets into executable subtasks",
        "Track blockers/risks and accountability follow-ups",
        "Maintain sprint modes to separate planning vs execution",
        "Use AI quick asks for status, decisions, and action items",
        "Centralize project context for faster onboarding",
    ],
}


def _format_capabilities_context():
    caps = "\n".join([f"- {c}" for c in CAREER_REPO_CAPABILITIES["capabilities"]])
    tools = "\n".join([f"- {t}" for t in CAREER_REPO_CAPABILITIES["tools_and_skills"]])
    unlocks = "\n".join([f"- {u}" for u in CAREER_REPO_CAPABILITIES["unlocks_for_data_engineers"]])
    return (
        "Tool capabilities:\n" + caps + "\n\n"
        "Architecture, tools, and skills:\n" + tools + "\n\n"
        "Practical unlocks for data engineers:\n" + unlocks
    )


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
        """SELECT ticket_id, title, description, status
           FROM tickets
           WHERE status IN ('todo', 'in_progress', 'in_review', 'blocked')
           ORDER BY created_at DESC
           LIMIT 5"""
    ).fetchall()

    meeting_text = "\n".join([
        f"- {m['meeting_name']}: {m['synthesized_notes'][:500]}" for m in meetings
    ]) or "No recent meetings."
    doc_text = "\n".join([
        f"- {d['source']}: {d['content'][:400]}" for d in docs
    ]) or "No recent documents."
    ticket_text = "\n".join([
        f"- {t['ticket_id']} {t['title']} ({t['status']})" for t in tickets
    ]) or "No active tickets."

    return {
        "meetings": meeting_text,
        "documents": doc_text,
        "tickets": ticket_text,
    }

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


@router.get("/api/career/profile")
async def get_career_profile(request: Request):
    """Get the current career profile."""
    with connect() as conn:
        profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
    
    if profile:
        return JSONResponse({
            "current_role": profile["current_role"],
            "target_role": profile["target_role"],
            "strengths": profile["strengths"],
            "weaknesses": profile["weaknesses"],
            "interests": profile["interests"],
            "goals": profile["goals"]
        })
    return JSONResponse({}, status_code=404)


@router.post("/api/career/profile")
async def update_career_profile(request: Request):
    """Update the career profile."""
    data = await request.json()
    
    with connect() as conn:
        conn.execute("""
            INSERT INTO career_profile (id, current_role, target_role, strengths, weaknesses, interests, goals)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                current_role = excluded.current_role,
                target_role = excluded.target_role,
                strengths = excluded.strengths,
                weaknesses = excluded.weaknesses,
                interests = excluded.interests,
                goals = excluded.goals,
                updated_at = datetime('now')
        """, (
            data.get("current_role"),
            data.get("target_role"),
            data.get("strengths"),
            data.get("weaknesses"),
            data.get("interests"),
            data.get("goals")
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
    """Generate new AI-powered career development suggestions."""
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
            
            career_summary = _load_career_summary(conn) or "No career status summary yet."
            overlay_context = _load_overlay_context(conn) if include_context else None
            
            prompt = f"""Based on this career profile, generate 3-5 specific, actionable growth opportunities:

Current Role: {profile['current_role']}
Target Role: {profile['target_role']}
Strengths: {profile['strengths']}
Areas to Develop: {profile['weaknesses']}
Interests: {profile['interests']}
Career Goals: {profile['goals']}

Career status summary:
{career_summary}
"""

            if include_context and overlay_context:
                prompt += f"""

Meetings context:
{overlay_context['meetings']}

Documents context:
{overlay_context['documents']}

Active tickets context:
{overlay_context['tickets']}
"""

            prompt += """

Generate specific suggestions that:
1. Bridge the gap between current and target role
2. Build on strengths and address weaknesses
3. Align with stated interests
4. Are concrete and actionable

For each suggestion, provide:
- Type: stretch, skill_building, project, or learning
- Title: concise name
- Description: what to do (2-3 sentences)
- Rationale: why this helps career growth
- Difficulty: beginner, intermediate, or advanced
- Time estimate: rough time needed
- Related goal: which aspect of career goals this supports

Return as JSON array with these fields: suggestion_type, title, description, rationale, difficulty, time_estimate, related_goal"""

            response = ask_llm(prompt, model="gpt-4o-mini")
            
            # Parse AI response
            try:
                # Try to extract JSON from response
                json_start = response.find('[')
                json_end = response.rfind(']') + 1
                if json_start >= 0 and json_end > json_start:
                    suggestions_data = json.loads(response[json_start:json_end])
                else:
                    suggestions_data = json.loads(response)
                
                # Insert suggestions
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
                
                return JSONResponse({
                    "status": "ok",
                    "count": len(created_ids),
                    "ids": created_ids
                })
            except json.JSONDecodeError as e:
                return JSONResponse({
                    "error": "Failed to parse AI response",
                    "raw_response": response
                }, status_code=500)
    
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
async def get_career_capabilities(request: Request):
    """Return repo capabilities and unlocks for the career agent."""
    return JSONResponse(CAREER_REPO_CAPABILITIES)


@router.post("/api/career/chat")
async def career_chat(request: Request):
    """Career status chat and summary update."""
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

        prompt = f"""You are a career coach. Use the profile and tool capabilities to answer the user's update/question.

Profile:
Current Role: {profile['current_role']}
Target Role: {profile['target_role']}
Strengths: {profile['strengths']}
Areas to Develop: {profile['weaknesses']}
Interests: {profile['interests']}
Career Goals: {profile['goals']}
 
    {_format_capabilities_context()}
"""

        if include_context and overlay_context:
            prompt += f"""

Meetings context:
{overlay_context['meetings']}

Documents context:
{overlay_context['documents']}

Active tickets context:
{overlay_context['tickets']}
"""

        prompt += f"""

User message:
{message}

Respond with concise guidance and, if appropriate, a short set of next steps."""

        try:
            response = ask_llm(prompt, model="gpt-4o-mini")
        except Exception as e:
            return JSONResponse({"error": f"AI Error: {str(e)}"}, status_code=500)

        summary_prompt = f"""Summarize the latest career status update into 3-5 bullet points.

User message:
{message}

Assistant response:
{response}

Return bullet points only."""

        try:
            summary = ask_llm(summary_prompt, model="gpt-4o-mini")
        except Exception:
            summary = ""

        conn.execute(
            """INSERT INTO career_chat_updates (message, response, summary)
               VALUES (?, ?, ?)""",
            (message, response, summary)
        )
        conn.commit()

    return JSONResponse({"status": "ok", "response": response, "summary": summary})


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
                VALUES (?, ?, ?, 'todo', 'medium', 'career,growth')
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
