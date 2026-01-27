# src/app/domains/career/api/code_locker.py
"""
Code Locker API Routes

Endpoints for storing and retrieving code snippets linked to tickets.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from ....repositories import get_career_repository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/code-locker")
async def get_code_entries(
    request: Request,
    ticket_id: Optional[int] = Query(None),
    filename: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Get code locker entries with optional filtering."""
    repo = get_career_repository()
    entries = repo.get_code_entries(
        ticket_id=ticket_id,
        filename=filename,
        limit=limit,
    )
    
    return JSONResponse({
        "entries": [
            {
                "id": e.id,
                "filename": e.filename,
                "content": e.content,
                "ticket_id": e.ticket_id,
                "version": e.version,
                "description": e.description,
                "created_at": e.created_at,
            }
            for e in entries
        ],
        "count": len(entries),
    })


@router.get("/code-locker/latest")
async def get_latest_code(
    ticket_id: int = Query(...),
    filename: str = Query(...),
):
    """Get the latest version of code for a file/ticket."""
    repo = get_career_repository()
    entry = repo.get_latest_code(ticket_id=ticket_id, filename=filename)
    
    if entry:
        return JSONResponse({
            "id": entry.id,
            "filename": entry.filename,
            "content": entry.content,
            "ticket_id": entry.ticket_id,
            "version": entry.version,
            "description": entry.description,
            "created_at": entry.created_at,
        })
    return JSONResponse({"error": "Code entry not found"}, status_code=404)


@router.post("/code-locker")
async def add_code_entry(request: Request):
    """Add a new code locker entry."""
    data = await request.json()
    
    if not data.get("filename"):
        return JSONResponse({"error": "filename is required"}, status_code=400)
    if not data.get("content"):
        return JSONResponse({"error": "content is required"}, status_code=400)
    if not data.get("ticket_id"):
        return JSONResponse({"error": "ticket_id is required"}, status_code=400)
    
    repo = get_career_repository()
    
    # Auto-increment version
    if "version" not in data:
        data["version"] = repo.get_next_version(
            ticket_id=data["ticket_id"],
            filename=data["filename"],
        )
    
    entry = repo.add_code_entry(data)
    
    if entry:
        return JSONResponse({
            "status": "ok",
            "id": entry.id,
            "version": entry.version,
        })
    return JSONResponse({"error": "Failed to add code entry"}, status_code=500)


@router.get("/code-locker/files")
async def get_code_locker_files(request: Request):
    """Get unique filenames in code locker with latest version info."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
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


@router.get("/code-locker/{entry_id}")
async def get_code_locker_entry(entry_id: int):
    """Get a specific code locker entry."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    result = supabase.table("code_locker").select("*").eq("id", entry_id).execute()
    
    if not result.data:
        return JSONResponse({"error": "Entry not found"}, status_code=404)
    
    entry = result.data[0]
    
    # Enrich with ticket info
    if entry.get("ticket_id"):
        ticket_result = supabase.table("tickets").select("ticket_id, title").eq(
            "id", entry["ticket_id"]
        ).execute()
        if ticket_result.data:
            entry["ticket_code"] = ticket_result.data[0].get("ticket_id")
            entry["ticket_title"] = ticket_result.data[0].get("title")
    
    return JSONResponse(entry)


@router.get("/code-locker/diff/{filename}")
async def get_code_diff(filename: str, v1: int = Query(...), v2: int = Query(...)):
    """Get diff between two versions of a file."""
    import difflib
    from ....infrastructure.supabase_client import get_supabase_client
    
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


@router.delete("/code-locker/{entry_id}")
async def delete_code_locker_entry(entry_id: int):
    """Delete a code locker entry."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("code_locker").delete().eq("id", entry_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/code-locker/next-version")
async def get_next_version(filename: str = Query(...), ticket_id: int = Query(None)):
    """Get the next version number for a file in the locker."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    query = supabase.table("code_locker").select("version").eq("filename", filename)
    if ticket_id:
        query = query.eq("ticket_id", ticket_id)
    
    result = query.order("version", desc=True).limit(1).execute()
    max_version = result.data[0].get("version") if result.data else 0
    next_version = (max_version or 0) + 1
    
    # Check if file is linked to a ticket
    ticket_file = None
    if ticket_id:
        tf_result = supabase.table("ticket_files").select("*").eq(
            "filename", filename
        ).eq("ticket_id", ticket_id).execute()
        
        if tf_result.data:
            tf = tf_result.data[0]
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


# ----------------------
# Ticket Files API
# ----------------------

@router.get("/ticket-files/{ticket_id}")
async def get_ticket_files(ticket_id: int):
    """Get files associated with a ticket."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    result = supabase.table("ticket_files").select("*").eq(
        "ticket_id", ticket_id
    ).order("file_type").order("filename").execute()
    
    files = result.data or []
    
    # Add locker version info
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


@router.post("/ticket-files/{ticket_id}")
async def add_ticket_file(ticket_id: int, request: Request):
    """Add a file to a ticket."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    data = await request.json()
    filename = (data.get("filename") or "").strip()
    file_type = data.get("file_type", "update")
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
        
        # If 'update' file with base_content, add to code locker as v1
        if file_type == 'update' and base_content:
            supabase.table("code_locker").insert({
                "ticket_id": ticket_id,
                "filename": filename,
                "content": base_content,
                "version": 1,
                "notes": "Initial/baseline version from ticket",
                "is_initial": True
            }).execute()
        
        return JSONResponse({"status": "ok", "id": file_id})
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            return JSONResponse({"error": "File already exists for this ticket"}, status_code=400)
        raise


@router.put("/ticket-files/{file_id}")
async def update_ticket_file(file_id: int, request: Request):
    """Update a ticket file's details."""
    from ....infrastructure.supabase_client import get_supabase_client
    
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


@router.delete("/ticket-files/{file_id}")
async def delete_ticket_file(file_id: int):
    """Delete a ticket file."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("ticket_files").delete().eq("id", file_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/tickets-with-files")
async def get_tickets_with_files():
    """Get all active tickets with their associated files."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse([])
    
    result = supabase.table("tickets").select("*").in_(
        "status", ["todo", "in_progress", "in_review", "blocked"]
    ).eq("in_sprint", True).execute()
    
    tickets = result.data or []
    
    # Sort by status priority
    status_order = {"in_progress": 1, "blocked": 2, "in_review": 3, "todo": 4}
    tickets.sort(key=lambda t: status_order.get(t.get("status", "todo"), 5))
    
    result_list = []
    for ticket in tickets:
        ticket_id = ticket.get('id')
        
        files_result = supabase.table("ticket_files").select(
            "id,filename,file_type,description"
        ).eq("ticket_id", ticket_id).order("file_type").order("filename").execute()
        
        files = files_result.data or []
        
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
