# src/app/domains/career/api/insights.py
"""
Career Insights API Routes

Handles AI-generated career insights and tweaks.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["career-insights"])


@router.post("/generate-insights")
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
    
    try:
        projects_result = supabase.table("completed_projects_bank").select(
            "title, description, technologies, impact"
        ).order("completed_date", desc=True).limit(10).execute()
        projects = projects_result.data or []
    except:
        projects = []
    
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
    
    skills_ctx = "\n".join([
        f"- {s.get('skill_name')} ({s.get('category')}): {s.get('proficiency_level')}%" 
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


@router.get("/insights")
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


@router.get("/tweaks")
async def get_career_tweaks(request: Request):
    """Get saved career tweaks."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"tweaks": []})
    
    result = supabase.table("career_tweaks").select("*").order("created_at", desc=True).execute()
    return JSONResponse({"tweaks": result.data or []})


@router.post("/tweaks")
async def save_career_tweak(request: Request):
    """Save a new career tweak."""
    data = await request.json()
    content = (data.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("career_tweaks").insert({"content": content}).execute()
    return JSONResponse({"status": "ok", "tweak": result.data[0] if result.data else None})


@router.delete("/tweaks/{tweak_id}")
async def delete_career_tweak(tweak_id: int):
    """Delete a career tweak."""
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("career_tweaks").delete().eq("id", tweak_id).execute()
    return JSONResponse({"status": "ok"})


__all__ = ["router"]
