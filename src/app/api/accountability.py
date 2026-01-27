# src/app/api/accountability.py

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from ..infrastructure.supabase_client import get_supabase_client

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


@router.get("/accountability")
async def list_accountability_items(request: Request):
    """List all accountability (waiting-for) items."""
    supabase = get_supabase_client()
    response = supabase.table("accountability_items").select("*").neq(
        "status", "cancelled"
    ).order("created_at", desc=True).execute()
    # Sort in Python: waiting first, then completed
    items = sorted(response.data, key=lambda x: (0 if x.get("status") == "waiting" else 1, x.get("created_at", "")))
    
    return templates.TemplateResponse("list_accountability.html", {
        "request": request,
        "items": items
    })


@router.post("/api/accountability/create")
async def create_accountability_item(request: Request):
    """Create a new accountability item."""
    try:
        # Handle both JSON and form data
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            data = await request.json()
            description = data.get("description")
            responsible_party = data.get("responsible_party")
            context = data.get("context")
            source_type = data.get("source_type", "manual")
            source_ref_id = data.get("source_ref_id")
        else:
            form = await request.form()
            description = form.get("description")
            responsible_party = form.get("responsible_party")
            context = form.get("context")
            source_type = form.get("source_type", "manual")
            source_ref_id = form.get("source_ref_id")
        
        supabase = get_supabase_client()
        result = supabase.table("accountability_items").insert({
            "description": description,
            "responsible_party": responsible_party,
            "context": context,
            "source_type": source_type,
            "source_ref_id": source_ref_id
        }).execute()
        item_id = result.data[0]["id"] if result.data else None
        
        return JSONResponse({"status": "ok", "id": item_id})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/api/accountability/{item_id}/status")
async def update_accountability_status(
    item_id: int,
    status: str = Form(...)
):
    """Update accountability item status."""
    try:
        from datetime import datetime as dt
        supabase = get_supabase_client()
        if status == 'completed':
            supabase.table("accountability_items").update({
                "status": status,
                "completed_at": dt.utcnow().isoformat()
            }).eq("id", item_id).execute()
        else:
            supabase.table("accountability_items").update({
                "status": status
            }).eq("id", item_id).execute()
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/api/accountability/{item_id}/delete")
async def delete_accountability_item(item_id: int):
    """Delete an accountability item."""
    try:
        supabase = get_supabase_client()
        supabase.table("accountability_items").delete().eq("id", item_id).execute()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
