
# Imports and router definition moved to top
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from ..db import connect
from ..llm import ask as ask_llm
import json

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

# Place the delete_standup endpoint after router is defined
@router.delete("/api/career/standups/{standup_id}")
async def delete_standup(standup_id: int):
    """Delete a standup update by ID."""
    with connect() as conn:
        conn.execute("DELETE FROM standup_updates WHERE id = ?", (standup_id,))
        conn.commit()
    return JSONResponse({"status": "ok"})

def get_code_locker_code_for_sprint_tickets(conn, tickets, max_lines=40, max_chars=2000):
    """Return a dict: {ticket_id: {filename: code}} for latest code locker entries for each file in current sprint tickets."""
    code_by_ticket = {}
    for t in tickets:
        tid = t['id'] if 'id' in t else t.get('id')
        ticket_code = t['ticket_id'] if 'ticket_id' in t else t.get('ticket_id')
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

        prompt = f"""You are a friendly, supportive career coach having a casual conversation with someone about their career journey. Think of yourself as a mentor they're catching up with over coffee.

About them:
- Currently: {profile['current_role']}
- Aiming for: {profile['target_role']}
- They're great at: {profile['strengths']}
- Working on improving: {profile['weaknesses']}
- Interested in: {profile['interests']}
- Big picture goals: {profile['goals']}

Keep these in mind about the tools they use:
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

They said:
"{message}"

Respond naturally like a supportive friend who happens to have great career advice. Be warm, encouraging, and practical. If they share an accomplishment, celebrate it! If they're struggling, empathize first, then offer gentle guidance. Keep your response conversational - no bullet points unless they specifically ask for action items. Think "wise friend at a coffee shop" not "corporate HR presentation"."""

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


# ----------------------
# Career Insights API
# ----------------------

@router.post("/api/career/generate-insights")
async def generate_career_insights(request: Request):
    """Generate AI insights based on skills, projects, and profile."""
    from app.llm import get_llm_response
    
    with connect() as conn:
        # Gather context
        profile = conn.execute("SELECT * FROM career_profile WHERE id = 1").fetchone()
        skills = conn.execute("""
            SELECT skill_name, category, proficiency_level 
            FROM skill_tracker 
            WHERE proficiency_level > 0 
            ORDER BY proficiency_level DESC 
            LIMIT 15
        """).fetchall()
        projects = conn.execute("""
            SELECT title, description, technologies, impact 
            FROM completed_projects_bank 
            ORDER BY completed_date DESC 
            LIMIT 10
        """).fetchall()
        ai_memories = conn.execute("""
            SELECT title, description, technologies 
            FROM ai_implementation_memories 
            ORDER BY created_at DESC 
            LIMIT 5
        """).fetchall()
        
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

        insights = await get_llm_response(prompt, model="gpt-4o-mini")
        
        return JSONResponse({"status": "ok", "insights": insights})


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


@router.post("/api/career/suggestions/compress")
async def compress_suggestions(request: Request):
    """Compress/deduplicate AI suggestions using LLM analysis."""
    from app.llm import get_llm_response
    
    try:
        with connect() as conn:
            # Get all active suggestions
            rows = conn.execute("""
                SELECT id, title, description, suggestion_type, rationale
                FROM career_suggestions 
                WHERE status = 'pending'
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

            response = await get_llm_response(prompt, model="gpt-4o-mini")
            
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


# Backend learning from feedback (placeholder)
@router.get("/api/signals/feedback-learn")
async def learn_from_feedback():
    """Analyze signal feedback and return learning summary (placeholder)."""
    with connect() as conn:
        rows = conn.execute("SELECT signal_text, feedback, COUNT(*) as count FROM signal_feedback GROUP BY signal_text, feedback ORDER BY count DESC LIMIT 20").fetchall()
        summary = [dict(row) for row in rows]
    # TODO: Use this data to filter, re-rank, or improve future suggestions
    return JSONResponse({"learning_summary": summary})


@router.post("/api/career/standups")
async def create_standup(request: Request):
    """Upload a standup update and generate AI feedback."""
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
        
        # Get recent standups for pattern analysis
        recent_standups = conn.execute("""
            SELECT content, feedback, sentiment 
            FROM standup_updates 
            ORDER BY standup_date DESC 
            LIMIT 5
        """).fetchall()
        
        # Get active tickets for context
        tickets = conn.execute("""
            SELECT ticket_id, title, status 
            FROM tickets 
            WHERE status IN ('todo', 'in_progress', 'in_review', 'blocked')
            AND in_sprint = 1
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()
        
        recent_context = "\n".join([
            f"- {s['content'][:200]}... (Sentiment: {s['sentiment']})" 
            for s in recent_standups
        ]) or "No previous standups."
        
        tickets_context = "\n".join([
            f"- {t['ticket_id']}: {t['title']} ({t['status']})"
            for t in tickets
        ]) or "No active sprint tickets."
        
        # Generate AI feedback
        prompt = f"""You are a supportive career coach reviewing a standup update. Analyze this standup and provide helpful feedback.

Career Context:
- Current Role: {profile['current_role'] if profile else 'Unknown'}
- Target Role: {profile['target_role'] if profile else 'Unknown'}
- Goals: {profile['goals'] if profile else 'Not specified'}

Active Sprint Tickets:
{tickets_context}

Recent Standup History:
{recent_context}

Today's Standup Update:
{content}

Provide:
1. SENTIMENT: Classify as 'positive', 'neutral', 'blocked', or 'struggling'
2. KEY_THEMES: 2-4 comma-separated main themes/topics
3. FEEDBACK: 2-3 paragraphs of supportive, actionable feedback:
   - Acknowledge what's going well
   - If there are blockers, suggest approaches
   - Connect work to career growth when relevant
   - Keep it encouraging and practical

Format your response as:
SENTIMENT: <sentiment>
KEY_THEMES: <theme1>, <theme2>, <theme3>
FEEDBACK:
<your feedback paragraphs>"""

        try:
            response = ask_llm(prompt, model="gpt-4o-mini")
            
            # Parse response
            lines = response.strip().split('\n')
            sentiment = 'neutral'
            key_themes = ''
            feedback_lines = []
            in_feedback = False
            
            for line in lines:
                if line.startswith('SENTIMENT:'):
                    sentiment = line.replace('SENTIMENT:', '').strip().lower()
                    if sentiment not in ('positive', 'neutral', 'blocked', 'struggling'):
                        sentiment = 'neutral'
                elif line.startswith('KEY_THEMES:'):
                    key_themes = line.replace('KEY_THEMES:', '').strip()
                elif line.startswith('FEEDBACK:'):
                    in_feedback = True
                elif in_feedback:
                    feedback_lines.append(line)
            
            feedback = '\n'.join(feedback_lines).strip()
            if not feedback:
                feedback = response  # Use full response if parsing failed
                
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
    """Generate a suggested standup based on code locker changes and ticket progress."""
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
        
        # Get yesterday's standup for continuity
        yesterday_standup = conn.execute("""
            SELECT content, feedback 
            FROM standup_updates 
            WHERE standup_date < date('now')
            ORDER BY standup_date DESC 
            LIMIT 1
        """).fetchone()
        
        # Build context
        tickets_context = "\n".join([
            f"- {t['ticket_id']}: {t['title']} (Status: {t['status']})"
            for t in tickets
        ]) or "No active sprint tickets."

        # Build file context per ticket
        files_context = ""
        if ticket_files_map:
            files_parts = []
            for ticket_id, files in ticket_files_map.items():
                update_files = [f for f in files if f['file_type'] == 'update']
                new_files = [f for f in files if f['file_type'] == 'new']

                parts = [f"Files for {ticket_id}:"]
                if update_files:
                    parts.append("  Files to modify:")
                    for f in update_files:
                        version_info = f"v{f['latest_version']}" if f['latest_version'] else "baseline set"
                        has_base = "has base code" if f['base_content'] else "no base"
                        parts.append(f"    - {f['filename']} ({version_info}, {has_base})")
                if new_files:
                    parts.append("  New files to create:")
                    for f in new_files:
                        desc = f" - {f['description']}" if f['description'] else ""
                        parts.append(f"    - {f['filename']}{desc}")
                files_parts.append("\n".join(parts))
            files_context = "\n\nPlanned File Changes:\n" + "\n".join(files_parts)

        # Add code locker code context for current sprint tickets
        code_locker_code = get_code_locker_code_for_sprint_tickets(conn, tickets)
        code_locker_context = ""
        for ticket_code, files in code_locker_code.items():
            if files:
                code_locker_context += f"\nCode for {ticket_code}:\n"
                for fname, code in files.items():
                    code_locker_context += f"- {fname} (latest):\n" + code + "\n"

        code_context = ""
        if code_changes:
            code_context = "\nRecent code changes logged:\n" + "\n".join([
                f"- {c['filename']} (v{c['version']}) for {c['ticket_code'] or 'unassigned'}: {c['notes'] or 'no notes'}"
                for c in code_changes
            ])
        else:
            code_context = "\nNo recent code changes logged."

        yesterday_context = ""
        if yesterday_standup:
            yesterday_context = f"\n\nYesterday's standup:\n{yesterday_standup['content'][:500]}"

        prompt = f"""Generate a suggested standup update based on the following context.

Active Sprint Tickets:
{tickets_context}
{files_context}
{code_locker_context}
{code_context}
{yesterday_context}

Generate a professional standup update covering:
1. What was accomplished since last standup (reference specific code changes if any)
2. What's planned for today (mention specific files to modify or create)
3. Any blockers or concerns

When referencing files:
- For "files to modify": these are existing files that need changes
- For "new files to create": these are entirely new files being added (the diff would show everything as new)

Keep it concise but informative (3-5 bullet points per section).
Use first person (I, my, etc.)."""

        try:
            suggestion = ask_llm(prompt, model="gpt-4o-mini")
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
        # Get completed tickets
        tickets = conn.execute("""
            SELECT t.*, 
                   GROUP_CONCAT(DISTINCT tf.filename) as files
            FROM tickets t
            LEFT JOIN ticket_files tf ON tf.ticket_id = t.id
            WHERE t.status IN ('done', 'complete', 'completed')
            GROUP BY t.id
            ORDER BY t.updated_at DESC
            LIMIT 50
        """).fetchall()
        
        # Get pinned completed project memories
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
    """Sync completed tickets to career memories (without overwriting pinned ones)."""
    with connect() as conn:
        # Get completed tickets not already in memories
        tickets = conn.execute("""
            SELECT t.* FROM tickets t
            WHERE t.status IN ('done', 'complete', 'completed')
            AND NOT EXISTS (
                SELECT 1 FROM career_memories cm 
                WHERE cm.source_type = 'ticket' AND cm.source_id = t.id
            )
        """).fetchall()
        
        added = 0
        for t in tickets:
            # Create memory for completed ticket
            skills = t["tags"] if t["tags"] else ""
            metadata = json.dumps({
                "ticket_id": t["ticket_id"],
                "status": t["status"],
                "completed_at": t["updated_at"]
            })
            
            conn.execute("""
                INSERT INTO career_memories (memory_type, title, description, source_type, source_id, skills, is_pinned, metadata)
                VALUES ('completed_project', ?, ?, 'ticket', ?, ?, 0, ?)
            """, (t["title"], t["ai_summary"] or t["description"], t["id"], skills, metadata))
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


@router.post("/api/career/skills/assess-from-codebase")
async def assess_skills_from_codebase(request: Request):
    """Analyze codebase and update skill levels based on code evidence."""
    import os
    import glob
    
    # Define patterns to look for each skill category
    skill_patterns = {
        "ddd": ["domain", "aggregate", "entity", "value_object", "repository", "bounded_context", "event_source"],
        "python": ["hexagonal", "adapter", "port", "typing", "dataclass", "protocol", "abstract"],
        "analytics": ["dbt", "model", "metric", "dimension", "fact", "data_quality"],
        "backend": ["api", "route", "endpoint", "fastapi", "flask", "rest", "graphql"],
        "airflow": ["dag", "task", "operator", "sensor", "airflow", "pipeline"],
        "aws": ["boto3", "s3", "lambda", "glue", "redshift", "step_function"],
        "ai": ["openai", "llm", "embedding", "vector", "prompt", "rag", "langchain"],
        "data": ["etl", "transform", "pipeline", "data_quality", "lineage", "catalog"],
        "knowledge": ["dikw", "knowledge", "ontology", "semantic", "graph", "taxonomy"]
    }
    
    # Scan codebase
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    py_files = glob.glob(os.path.join(workspace_root, "**/*.py"), recursive=True)
    
    # Exclude common non-project directories
    py_files = [f for f in py_files if not any(x in f for x in ['__pycache__', '.venv', 'venv', 'node_modules', '.git'])]
    
    skill_evidence = {cat: {"files": [], "count": 0, "patterns_found": []} for cat in skill_patterns}
    
    for filepath in py_files[:100]:  # Limit to first 100 files
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                
            for category, patterns in skill_patterns.items():
                for pattern in patterns:
                    if pattern in content:
                        rel_path = os.path.relpath(filepath, workspace_root)
                        if rel_path not in skill_evidence[category]["files"]:
                            skill_evidence[category]["files"].append(rel_path)
                        skill_evidence[category]["count"] += content.count(pattern)
                        if pattern not in skill_evidence[category]["patterns_found"]:
                            skill_evidence[category]["patterns_found"].append(pattern)
        except Exception:
            pass
    
    # Map pattern categories to skill names that exist in skill_tracker
    pattern_to_skills = {
        "ddd": ["Domain Driven Design", "Bounded Contexts", "Aggregates", "Event Sourcing"],
        "python": ["Python", "typing", "Hexagonal Architecture"],
        "analytics": ["Data Analysis", "SQL/Databases", "Data Visualization"],
        "backend": ["REST APIs", "FastAPI", "Backend Development", "Microservices"],
        "airflow": ["Airflow", "Data Pipelines", "ETL"],
        "aws": ["AWS", "Cloud Platforms", "Lambda", "S3"],
        "ai": ["OpenAI", "LLM Integration", "RAG", "Embeddings", "AI/ML"],
        "data": ["ETL", "Data Pipelines", "Data Quality", "Data Lineage"],
        "knowledge": ["Knowledge Graphs", "DIKW", "Semantic", "Ontology"]
    }
    
    # Update skill levels based on evidence
    ai_memories_added = []
    skills_updated = 0
    with connect() as conn:
        for category, evidence in skill_evidence.items():
            file_count = len(evidence["files"])
            pattern_count = len(evidence["patterns_found"])
            
            if file_count > 0:
                # More gradual proficiency scale: max ~70% from codebase alone
                # Requires manual validation/projects to reach higher levels
                base_score = 15
                file_bonus = min(20, file_count * 2)  # Cap at 20
                pattern_bonus = min(15, pattern_count * 3)  # Cap at 15
                usage_bonus = min(20, evidence["count"] // 50)  # Much slower scaling
                proficiency = min(70, base_score + file_bonus + pattern_bonus + usage_bonus)
                
                # Update all skills matching this pattern category
                skills_to_update = pattern_to_skills.get(category, [])
                evidence_json = json.dumps(evidence["files"][:10])
                
                for skill in skills_to_update:
                    # First, ensure the skill exists
                    conn.execute("""
                        INSERT OR IGNORE INTO skill_tracker (skill_name, category, proficiency_level, evidence)
                        VALUES (?, ?, 0, '[]')
                    """, (skill, category))
                    
                    # Then update with evidence
                    result = conn.execute("""
                        UPDATE skill_tracker 
                        SET proficiency_level = MAX(proficiency_level, ?),
                            evidence = ?,
                            last_used_at = datetime('now'),
                            updated_at = datetime('now')
                        WHERE skill_name = ? OR LOWER(skill_name) LIKE LOWER(?)
                    """, (proficiency, evidence_json, skill, f"%{skill}%"))
                    skills_updated += result.rowcount
                
                # Also update by category match
                conn.execute("""
                    UPDATE skill_tracker 
                    SET proficiency_level = MAX(proficiency_level, ?),
                        evidence = ?,
                        last_used_at = datetime('now'),
                        updated_at = datetime('now')
                    WHERE LOWER(category) = LOWER(?)
                """, (proficiency, json.dumps(evidence["files"][:10]), category))
                
                # Auto-add AI implementation memories for AI-related patterns
                if category == "ai" and evidence["count"] > 5:
                    # Check if we haven't already added this
                    existing = conn.execute(
                        "SELECT id FROM ai_implementation_memories WHERE title LIKE ?",
                        (f"%{category.upper()} - Auto-discovered%",)
                    ).fetchone()
                    if not existing:
                        patterns_found = ", ".join(evidence["patterns_found"][:5])
                        files_found = "\n".join([f"- {f}" for f in evidence["files"][:5]])
                        conn.execute("""
                            INSERT INTO ai_implementation_memories (title, description, technologies, impact, lessons_learned)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            "AI/ML - Auto-discovered from codebase",
                            f"Automatically detected AI implementation patterns in codebase.\n\nPatterns found: {patterns_found}\n\nKey files:\n{files_found}",
                            patterns_found,
                            "Codebase analysis",
                            "Auto-generated from assess codebase feature"
                        ))
                        ai_memories_added.append(category)
        
        conn.commit()
    
    return JSONResponse({
        "status": "ok",
        "skills_updated": skills_updated,
        "evidence": {k: {"files": v["files"][:5], "patterns": v["patterns_found"]} for k, v in skill_evidence.items() if v["count"] > 0},
        "ai_memories_added": ai_memories_added
    })


@router.post("/api/career/skills/update-from-tickets")
async def update_skills_from_tickets():
    """Update skill counts based on completed tickets."""
    with connect() as conn:
        # Get tags from completed tickets
        tickets = conn.execute("""
            SELECT tags FROM tickets
            WHERE status IN ('done', 'complete', 'completed')
            AND tags IS NOT NULL AND tags != ''
        """).fetchall()
        
        # Count occurrences of each skill/tag
        tag_counts = {}
        for t in tickets:
            for tag in (t["tags"] or "").split(","):
                tag = tag.strip().lower()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
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


@router.post("/api/career/assess-codebase-ai")
async def assess_codebase_with_ai(request: Request):
    """Use AI to analyze codebase and generate technical implementation memories."""
    import os
    import glob
    from ..llm_new import ask_llm
    
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
                conn.commit()
            
            return JSONResponse({"status": "ok", "added": added, "count": len(added)})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})
    
    return JSONResponse({"status": "error", "message": "Failed to parse AI response"})
