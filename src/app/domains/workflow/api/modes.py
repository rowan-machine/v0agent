# src/app/domains/workflow/api/modes.py
"""
Workflow Mode API Routes

Handles workflow mode settings, suggested mode detection,
and expected duration tracking.
"""

import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/settings/mode")
async def set_workflow_mode(request: Request):
    """Save the current workflow mode to Supabase."""
    data = await request.json()
    mode = data.get("mode", "mode-a")
    
    try:
        sb = get_supabase_client()
        if sb:
            sb.table("settings").upsert({
                "key": "current_mode",
                "value": mode
            }, on_conflict="key").execute()
            return JSONResponse({"status": "ok", "mode": mode})
    except Exception as e:
        logger.error(f"Supabase settings save failed: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
    
    return JSONResponse({"status": "ok", "mode": mode})


@router.get("/api/settings/mode")
async def get_workflow_mode():
    """Get the current workflow mode from Supabase."""
    try:
        sb = get_supabase_client()
        if sb:
            result = sb.table("settings").select("value").eq("key", "current_mode").single().execute()
            if result.data:
                return JSONResponse({"mode": result.data["value"]})
    except Exception as e:
        logger.debug(f"Supabase settings read failed: {e}")
    
    return JSONResponse({"mode": "mode-a"})


@router.get("/api/settings/mode/suggested")
async def get_suggested_mode():
    """Get the suggested workflow mode based on sprint cadence.
    
    Uses SprintModeDetectJob logic to suggest A/B/C/D mode.
    Returns suggestion along with sprint context info.
    """
    from ....services.background_jobs import SprintModeDetectJob
    
    job = SprintModeDetectJob()
    sprint_info = job.get_current_sprint_info()
    suggested = job.detect_suggested_mode()
    mode_info = job.MODES.get(suggested, {})
    
    # Map internal mode (A/B/C/D) to UI mode (mode-a, mode-b, etc.)
    ui_mode_map = {
        "A": "mode-a",
        "B": "mode-b", 
        "C": "mode-c",
        "D": "mode-d",
    }
    ui_mode = ui_mode_map.get(suggested, "mode-a")
    
    return JSONResponse({
        "suggested_mode": ui_mode,
        "mode_letter": suggested,
        "mode_name": mode_info.get("name", ""),
        "mode_description": mode_info.get("description", ""),
        "sprint_info": sprint_info,
    })


@router.get("/api/settings/mode/expected-duration")
async def get_expected_mode_duration():
    """Get expected duration for each mode based on historical data with defaults.
    
    Returns expected minutes per mode, calculated from historical time tracking
    data with sensible defaults when insufficient data exists.
    """
    sb = get_supabase_client()
    
    # Default expected durations (in minutes) based on typical workflow
    defaults = {
        "mode-a": 60,   # Context Distillation: ~1 hour
        "mode-b": 45,   # Implementation Planning: ~45 min
        "mode-c": 90,   # Assisted Draft Intake: ~1.5 hours
        "mode-d": 60,   # Deep Review: ~1 hour
        "mode-e": 30,   # Promotion Readiness: ~30 min
        "mode-f": 20,   # Controlled Ingress/Egress: ~20 min
        "mode-g": 120,  # Execution: ~2 hours (variable)
    }
    
    result = {}
    
    # Get historical averages from Supabase mode_sessions table
    for mode, default_mins in defaults.items():
        try:
            rows = sb.table("mode_sessions").select("duration_seconds").eq("mode", mode).not_.is_("duration_seconds", "null").gt("duration_seconds", 0).execute().data
            session_count = len(rows) if rows else 0
            
            if session_count >= 3:  # Need at least 3 data points to trust the average
                avg_seconds = sum(r["duration_seconds"] for r in rows) / session_count
                avg_mins = int(avg_seconds / 60)
                # Use a blend: 70% historical, 30% default (to avoid extreme values)
                expected_mins = int(avg_mins * 0.7 + default_mins * 0.3)
            else:
                expected_mins = default_mins
            
            result[mode] = {
                "expected_minutes": expected_mins,
                "default_minutes": default_mins,
                "historical_sessions": session_count,
                "has_sufficient_data": session_count >= 3,
            }
        except:
            result[mode] = {
                "expected_minutes": default_mins,
                "default_minutes": default_mins,
                "historical_sessions": 0,
                "has_sufficient_data": False,
            }
    
    return JSONResponse(result)


@router.get("/api/settings/ai-model")
async def get_ai_model():
    """Get current AI model setting from Supabase."""
    try:
        sb = get_supabase_client()
        if sb:
            result = sb.table("settings").select("value").eq("key", "ai_model").single().execute()
            if result.data:
                return JSONResponse({"model": result.data["value"]})
    except Exception as e:
        logger.debug(f"Supabase AI model read failed: {e}")
    
    return JSONResponse({"model": "gpt-4o-mini"})


@router.post("/api/settings/ai-model")
async def set_ai_model(request: Request):
    """Set AI model to use in Supabase."""
    data = await request.json()
    model = data.get("model", "gpt-4o-mini")
    
    try:
        sb = get_supabase_client()
        if sb:
            sb.table("settings").upsert({
                "key": "ai_model",
                "value": model
            }, on_conflict="key").execute()
            return JSONResponse({"status": "ok", "model": model})
    except Exception as e:
        logger.error(f"Supabase AI model save failed: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
    
    return JSONResponse({"status": "ok", "model": model})
