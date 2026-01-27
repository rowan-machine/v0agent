# src/app/api/settings.py

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ..infrastructure.supabase_client import get_supabase_client

router = APIRouter()


def get_auth_enabled() -> bool:
    """Check if authentication is enabled."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("settings").select("value").eq("key", "auth_enabled").execute()
        if result.data:
            return result.data[0]["value"].lower() in ('true', '1', 'yes')
    except:
        pass
    return True  # Default: auth enabled


@router.get("/api/settings/auth")
async def get_auth_setting():
    """Get authentication enabled/disabled status."""
    return JSONResponse({"enabled": get_auth_enabled()})


@router.post("/api/settings/auth")
async def set_auth_setting(request: Request):
    """Toggle authentication on/off."""
    try:
        data = await request.json()
        enabled = data.get("enabled", True)
        
        supabase = get_supabase_client()
        supabase.table("settings").upsert({"key": "auth_enabled", "value": str(enabled)}).execute()
        
        return JSONResponse({"status": "ok", "enabled": enabled})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.get("/api/settings/model")
async def get_model_setting():
    """Get current AI model setting."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("settings").select("value").eq("key", "ai_model").execute()
        if result.data:
            return JSONResponse({"model": result.data[0]["value"]})
        return JSONResponse({"model": "gpt-4o-mini"})
    except Exception as e:
        return JSONResponse({"model": "gpt-4o-mini"})


@router.post("/api/settings/model")
async def set_model_setting(request: Request):
    """Set AI model setting."""
    try:
        data = await request.json()
        model = data.get("model", "gpt-4o-mini")
        
        supabase = get_supabase_client()
        supabase.table("settings").upsert({"key": "ai_model", "value": model}).execute()
        
        return JSONResponse({"status": "ok", "model": model})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# NOTE: /api/settings/workflow-progress routes are in api/workflow.py


@router.post("/api/settings/reset-workflow-progress")
async def reset_workflow_progress():
    """Reset all workflow progress for a new sprint."""
    try:
        modes = ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g']
        
        supabase = get_supabase_client()
        for mode in modes:
            supabase.table("settings").delete().eq("key", f"workflow_progress_{mode}").execute()
        
        return JSONResponse({"status": "ok", "message": "All workflow progress reset"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# ========================================
# Workflow Modes Management
# ========================================

DEFAULT_MODES = [
    {
        "mode_key": "mode-a",
        "name": "Context Distillation",
        "icon": "🎯",
        "description": "Select files, freeze context, seed agents",
        "steps_json": [
            {"title": "Select 12–16 canonical files", "description": "Create immutable context packet for this sprint"},
            {"title": "Lock context in agent memory", "description": "Freeze file versions for consistent responses"},
            {"title": "Run context digest", "description": "Generate AI summary of selected context"},
            {"title": "Confirm context is stable", "description": "Verify no pending changes to context files"}
        ],
        "sort_order": 0
    },
    {
        "mode_key": "mode-b",
        "name": "Implementation Planning",
        "icon": "📋",
        "description": "Review context, define scope, create plan",
        "steps_json": [
            {"title": "Review frozen context", "description": "Understand the scope of selected files"},
            {"title": "Define work scope", "description": "List deliverables for this sprint"},
            {"title": "Generate implementation plan", "description": "AI-assisted breakdown of work items"}
        ],
        "sort_order": 1
    },
    {
        "mode_key": "mode-c",
        "name": "Assisted Draft Intake",
        "icon": "✏️",
        "description": "Generate code, docs, and walkthroughs",
        "steps_json": [
            {"title": "Generate initial drafts", "description": "AI creates first pass of code/docs"},
            {"title": "Create documentation outline", "description": "Generate structure for required docs"},
            {"title": "Review AI suggestions", "description": "Evaluate and refine generated content"},
            {"title": "Commit intake batch", "description": "Save approved drafts to working directory"}
        ],
        "sort_order": 2
    },
    {
        "mode_key": "mode-d",
        "name": "Deep Review & Validation",
        "icon": "🔍",
        "description": "Line-by-line review, smoke test, fix loops",
        "steps_json": [
            {"title": "Line-by-line code review", "description": "Examine every change for correctness"},
            {"title": "Run smoke tests", "description": "Basic functionality verification"},
            {"title": "Fix identified issues", "description": "Address review findings"},
            {"title": "Validate fixes", "description": "Confirm all issues resolved"}
        ],
        "sort_order": 3
    },
    {
        "mode_key": "mode-e",
        "name": "Promotion Readiness",
        "icon": "🚀",
        "description": "Checklist, code locker, transfer packet",
        "steps_json": [
            {"title": "Complete PR checklist", "description": "All items verified before merge"},
            {"title": "Lock code for promotion", "description": "No further changes allowed"},
            {"title": "Create transfer packet", "description": "Documentation for handoff/deployment"},
            {"title": "Final sign-off", "description": "Approve for production promotion"}
        ],
        "sort_order": 4
    },
    {
        "mode_key": "mode-f",
        "name": "Controlled Ingress/Egress",
        "icon": "🔄",
        "description": "Push/pull, commit, PR, merge (Online)",
        "steps_json": [
            {"title": "Push to remote", "description": "Upload changes to Git repository"},
            {"title": "Create pull request", "description": "Open PR for review"},
            {"title": "Address review comments", "description": "Respond to feedback"},
            {"title": "Merge to main", "description": "Complete the merge process"}
        ],
        "sort_order": 5
    },
    {
        "mode_key": "mode-g",
        "name": "Execution (Writing Code)",
        "icon": "💻",
        "description": "Implement the current ticket checklist",
        "steps_json": [],
        "sort_order": 6
    }
]


@router.get("/api/settings/workflow-modes")
async def get_workflow_modes():
    """Get all workflow modes configuration."""
    try:
        import json
        supabase = get_supabase_client()
        response = supabase.table("workflow_modes").select("*").eq("is_active", True).order("sort_order").execute()
        modes = response.data
        
        if not modes:
            # Return default modes if none exist
            return JSONResponse({"modes": DEFAULT_MODES, "is_default": True})
        
        result = []
        for m in modes:
            result.append({
                "id": m["id"],
                "mode_key": m["mode_key"],
                "name": m["name"],
                "icon": m["icon"],
                "short_description": m.get("short_description", ""),
                "description": m["description"],
                "steps_json": json.loads(m["steps_json"]) if m["steps_json"] else [],
                "sort_order": m["sort_order"],
                "is_active": bool(m["is_active"])
            })
        
        return JSONResponse({"modes": result, "is_default": False})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/settings/workflow-modes")
async def save_workflow_mode(request: Request):
    """Create or update a workflow mode."""
    try:
        import json
        data = await request.json()
        
        mode_key = data.get("mode_key")
        name = data.get("name")
        icon = data.get("icon", "🎯")
        short_description = data.get("short_description", "")
        description = data.get("description", "")
        steps_json = json.dumps(data.get("steps_json", []))
        sort_order = data.get("sort_order", 0)
        mode_id = data.get("id")
        
        if not mode_key or not name:
            return JSONResponse({"error": "mode_key and name are required"}, status_code=400)
        
        supabase = get_supabase_client()
        if mode_id:
            # Update existing
            supabase.table("workflow_modes").update({
                "name": name,
                "icon": icon,
                "short_description": short_description,
                "description": description,
                "steps_json": steps_json,
                "sort_order": sort_order
            }).eq("id", mode_id).execute()
        else:
            # Insert new (upsert on mode_key)
            supabase.table("workflow_modes").upsert({
                "mode_key": mode_key,
                "name": name,
                "icon": icon,
                "short_description": short_description,
                "description": description,
                "steps_json": steps_json,
                "sort_order": sort_order
            }, on_conflict="mode_key").execute()
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/settings/workflow-modes/{mode_key}")
async def delete_workflow_mode(mode_key: str):
    """Delete (deactivate) a workflow mode."""
    try:
        supabase = get_supabase_client()
        supabase.table("workflow_modes").update({"is_active": False}).eq("mode_key", mode_key).execute()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/settings/workflow-modes/init-defaults")
async def init_default_modes():
    """Initialize database with default workflow modes."""
    try:
        import json
        supabase = get_supabase_client()
        for mode in DEFAULT_MODES:
            supabase.table("workflow_modes").upsert({
                "mode_key": mode["mode_key"],
                "name": mode["name"],
                "icon": mode["icon"],
                "description": mode["description"],
                "steps_json": json.dumps(mode["steps_json"]),
                "sort_order": mode["sort_order"]
            }, on_conflict="mode_key", ignore_duplicates=True).execute()
        return JSONResponse({"status": "ok", "message": "Default modes initialized"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================
# Feature Flags & Beta Features
# ============================================

@router.get("/api/settings/features")
async def get_feature_flags():
    """
    Get all feature flags with their current state.
    
    Returns enabled/disabled status and stability level for each feature.
    """
    from ..infrastructure.feature_flags import get_all_flags
    return JSONResponse(get_all_flags())


@router.get("/api/settings/features/beta")
async def get_beta_features():
    """
    Get beta features with known issues.
    
    These features are functional but may have bugs.
    """
    from ..infrastructure.feature_flags import get_beta_features
    return JSONResponse(get_beta_features())


@router.get("/api/settings/features/alpha")
async def get_alpha_features():
    """
    Get alpha/experimental features.
    
    These features are in early development and may be unstable.
    """
    from ..infrastructure.feature_flags import get_alpha_features
    return JSONResponse(get_alpha_features())


@router.get("/api/settings/features/diagnostics")
async def run_feature_diagnostics():
    """
    Run diagnostics on feature flags.
    
    Returns counts, environment overrides, and known issues summary.
    """
    from ..infrastructure.feature_flags import run_diagnostics
    return JSONResponse(run_diagnostics())

