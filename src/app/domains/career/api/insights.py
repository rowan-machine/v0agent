# src/app/domains/career/api/insights.py
"""
Career Insights API Routes

Handles AI-generated career insights and tweaks.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_career_repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["career-insights"])


@router.post("/generate-insights")
async def generate_career_insights(request: Request):
    """Generate AI insights based on skills, projects, and profile."""
    career_repo = get_career_repository()
    
    # Gather context using repository
    profile = career_repo.get_profile()
    skills = career_repo.get_skills(min_proficiency=1, limit=15) or []
    
    # Projects and AI memories - fallback to empty if not available
    projects = []
    ai_memories = []
    
    # Format context
    profile_ctx = f"""
Current Role: {profile.current_role or 'Not set' if profile else 'Not set'}
Target Role: {profile.target_role or 'Not set' if profile else 'Not set'}
Strengths: {profile.strengths or 'Not set' if profile else 'Not set'}
Goals: {profile.goals or 'Not set' if profile else 'Not set'}
""" if profile else "No profile set"
    
    skills_ctx = "\n".join([
        f"- {s.skill_name} ({s.category}): {s.proficiency_level}%" 
        for s in skills
    ]) if skills else "No skills tracked"
    
    projects_ctx = "\n".join([
        f"- {p.get('title')}: {(p.get('description') or '')[:100]}..." 
        for p in projects
    ]) if projects else "No projects"
    
    ai_ctx = "\n".join([
        f"- {m.get('title')}: {m.get('technologies')}" 
        for m in ai_memories
    ]) if ai_memories else "No AI implementations"
    
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

    from ....agents.career_coach import get_career_coach_agent
    agent = get_career_coach_agent(db_connection=None)
    insights = await agent.ask_llm(
        prompt=prompt,
        task_type="career_insights",
    )
    
    try:
        career_repo.update_profile({"last_insights": insights})
    except Exception as e:
        logger.warning(f"Could not persist insights: {e}")
    
    return JSONResponse({
        "status": "ok", 
        "insights": insights, 
        "run_id": agent.last_run_id
    })


@router.get("/insights")
async def get_career_insights():
    """Get the last saved career insights."""
    career_repo = get_career_repository()
    result = career_repo.get_profile_insights()
    
    if result and result.get("last_insights"):
        return JSONResponse({
            "insights": result["last_insights"],
            "generated_at": result.get("updated_at")
        })
    return JSONResponse({"insights": None})


@router.get("/tweaks")
async def get_career_tweaks(request: Request):
    """Get saved career tweaks."""
    career_repo = get_career_repository()
    tweaks = career_repo.get_tweaks(limit=100)
    return JSONResponse({"tweaks": tweaks})


@router.post("/tweaks")
async def save_career_tweak(request: Request):
    """Save a new career tweak."""
    data = await request.json()
    content = (data.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    
    career_repo = get_career_repository()
    tweak = career_repo.add_tweak(content)
    return JSONResponse({"status": "ok", "tweak": tweak})


@router.delete("/tweaks/{tweak_id}")
async def delete_career_tweak(tweak_id: int):
    """Delete a career tweak."""
    career_repo = get_career_repository()
    career_repo.delete_tweak(tweak_id)
    return JSONResponse({"status": "ok"})


__all__ = ["router"]
