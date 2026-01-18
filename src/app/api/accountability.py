# src/app/api/accountability.py

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from ..db import connect

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


@router.get("/accountability")
async def list_accountability_items(request: Request):
    """List all accountability (waiting-for) items."""
    with connect() as conn:
        items = conn.execute("""
            SELECT * FROM accountability_items
            WHERE status != 'cancelled'
            ORDER BY 
                CASE status 
                    WHEN 'waiting' THEN 1 
                    WHEN 'completed' THEN 2 
                END,
                created_at DESC
        """).fetchall()
    
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
        
        with connect() as conn:
            cur = conn.execute("""
                INSERT INTO accountability_items 
                (description, responsible_party, context, source_type, source_ref_id)
                VALUES (?, ?, ?, ?, ?)
            """, (description, responsible_party, context, source_type, source_ref_id))
            item_id = cur.lastrowid
        
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
        with connect() as conn:
            if status == 'completed':
                conn.execute("""
                    UPDATE accountability_items 
                    SET status = ?, completed_at = datetime('now'), updated_at = datetime('now')
                    WHERE id = ?
                """, (status, item_id))
            else:
                conn.execute("""
                    UPDATE accountability_items 
                    SET status = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, (status, item_id))
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/api/accountability/{item_id}/delete")
async def delete_accountability_item(item_id: int):
    """Delete an accountability item."""
    try:
        with connect() as conn:
            conn.execute("DELETE FROM accountability_items WHERE id = ?", (item_id,))
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
