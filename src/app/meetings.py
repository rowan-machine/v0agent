from fastapi import APIRouter, Form, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from zoneinfo import ZoneInfo
from .db import connect

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

@router.post("/meetings/synthesize")
def store_meeting(
    meeting_name: str = Form(...),
    synthesized_notes: str = Form(...),
    meeting_date: str = Form(...)
):
    with connect() as conn:
        conn.execute(
            "INSERT INTO meeting_summaries (meeting_name, synthesized_notes, meeting_date) VALUES (?, ?, ?)",
            (meeting_name, synthesized_notes, meeting_date),
        )
    return RedirectResponse(url="/meetings?success=meeting_created", status_code=303)

@router.get("/meetings")
def list_meetings(request: Request, success: str = Query(default=None)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, meeting_name, meeting_date, created_at FROM meeting_summaries ORDER BY COALESCE(meeting_date, created_at) DESC"
        ).fetchall()
    
    # Format dates for display in Central Time
    formatted_meetings = []
    for row in rows:
        meeting = dict(row)
        date_str = meeting['meeting_date'] or meeting['created_at']
        if date_str:
            try:
                # Parse the date (handles both date-only and datetime formats)
                if ' ' in date_str:
                    # Parse as UTC and convert to Central
                    dt = datetime.strptime(date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    dt_utc = dt.replace(tzinfo=ZoneInfo('UTC'))
                    dt_central = dt_utc.astimezone(ZoneInfo('America/Chicago'))
                    meeting['display_date'] = dt_central.strftime('%Y-%m-%d %I:%M %p %Z')
                else:
                    meeting['display_date'] = date_str
            except:
                meeting['display_date'] = date_str
        else:
            meeting['display_date'] = ''
        formatted_meetings.append(meeting)

    return templates.TemplateResponse(
        "list_meetings.html",
        {"request": request, "meetings": formatted_meetings, "success": success},
    )

@router.get("/meetings/{meeting_id}/edit")
def edit_meeting(meeting_id: int, request: Request):
    with connect() as conn:
        meeting = conn.execute(
            "SELECT * FROM meeting_summaries WHERE id = ?",
            (meeting_id,),
        ).fetchone()

    return templates.TemplateResponse(
        "edit_meeting.html",
        {"request": request, "meeting": meeting},
    )

@router.post("/meetings/{meeting_id}/edit")
def update_meeting(
    meeting_id: int,
    meeting_name: str = Form(...),
    synthesized_notes: str = Form(...),
    meeting_date: str = Form(...)
):
    with connect() as conn:
        conn.execute(
            """
            UPDATE meeting_summaries
            SET meeting_name = ?, synthesized_notes = ?, meeting_date = ?
            WHERE id = ?
            """,
            (meeting_name, synthesized_notes, meeting_date, meeting_id),
        )

    return RedirectResponse(url="/meetings?success=meeting_updated", status_code=303)

@router.post("/meetings/{meeting_id}/delete")
def delete_meeting(meeting_id: int):
    with connect() as conn:
        conn.execute(
            "DELETE FROM meeting_summaries WHERE id = ?",
            (meeting_id,),
        )
    return RedirectResponse(url="/meetings?success=meeting_deleted", status_code=303)
