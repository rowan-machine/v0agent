from fastapi import APIRouter, Form, Request, Query, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
import json
import base64

from .db import connect
from .memory.embed import embed_text, EMBED_MODEL
from .memory.vector_store import upsert_embedding
from .mcp.parser import parse_meeting_summary
from .mcp.extract import extract_structured_signals
from .mcp.cleaner import clean_meeting_text
from .llm import analyze_image

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


def process_screenshots(meeting_id: int, screenshots: List[UploadFile]) -> List[str]:
    """Process uploaded screenshots with vision API and store summaries."""
    summaries = []
    
    for screenshot in screenshots:
        if not screenshot.filename or screenshot.size == 0:
            continue
            
        try:
            # Read image data
            image_data = screenshot.file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Analyze with vision API
            summary = analyze_image(image_base64)
            summaries.append(summary)
            
            # Store in database
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO meeting_screenshots (meeting_id, filename, content_type, image_summary)
                    VALUES (?, ?, ?, ?)
                    """,
                    (meeting_id, screenshot.filename, screenshot.content_type, summary)
                )
        except Exception as e:
            print(f"Error processing screenshot {screenshot.filename}: {e}")
            continue
    
    return summaries


def get_meeting_screenshots(meeting_id: int) -> List[dict]:
    """Get all screenshot summaries for a meeting."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, image_summary, created_at
            FROM meeting_screenshots
            WHERE meeting_id = ?
            ORDER BY created_at
            """,
            (meeting_id,)
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/meetings/synthesize")
async def store_meeting(
    meeting_name: str = Form(...),
    synthesized_notes: str = Form(...),
    meeting_date: str = Form(...),
    screenshots: List[UploadFile] = File(default=[])
):
    # Clean the text (remove aside tags and markdown headers)
    cleaned_notes = clean_meeting_text(synthesized_notes)
    
    # Parse and extract structured signals
    parsed_sections = parse_meeting_summary(cleaned_notes)
    signals = extract_structured_signals(parsed_sections)
    
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO meeting_summaries (meeting_name, synthesized_notes, meeting_date, signals_json)
            VALUES (?, ?, ?, ?)
            """,
            (meeting_name, cleaned_notes, meeting_date, json.dumps(signals)),
        )
        meeting_id = cur.lastrowid

    # Process screenshots with vision API
    screenshot_summaries = []
    if screenshots:
        screenshot_summaries = process_screenshots(meeting_id, screenshots)
    
    # ---- VX.2b: embedding on ingest ----
    # Include screenshot summaries in embedding for searchability
    screenshot_text = "\n\n".join([f"[Screenshot]: {s}" for s in screenshot_summaries]) if screenshot_summaries else ""
    text_for_embedding = f"{meeting_name}\n{synthesized_notes}\n{screenshot_text}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("meeting", meeting_id, EMBED_MODEL, vector)

    return RedirectResponse(url="/meetings?success=meeting_created", status_code=303)


@router.get("/meetings")
def list_meetings(request: Request, success: str = Query(default=None)):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, meeting_name, meeting_date, created_at
            FROM meeting_summaries
            ORDER BY COALESCE(meeting_date, created_at) DESC
            """
        ).fetchall()

    formatted = []
    for row in rows:
        meeting = dict(row)
        date_str = meeting["meeting_date"] or meeting["created_at"]
        if date_str:
            try:
                if " " in date_str:
                    dt = datetime.strptime(date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    dt_utc = dt.replace(tzinfo=ZoneInfo("UTC"))
                    dt_central = dt_utc.astimezone(ZoneInfo("America/Chicago"))
                    meeting["display_date"] = dt_central.strftime("%Y-%m-%d %I:%M %p %Z")
                else:
                    meeting["display_date"] = date_str
            except Exception:
                meeting["display_date"] = date_str
        else:
            meeting["display_date"] = ""

        formatted.append(meeting)

    return templates.TemplateResponse(
        "list_meetings.html",
        {"request": request, "meetings": formatted, "success": success},
    )


@router.get("/meetings/{meeting_id}")
def view_meeting(meeting_id: int, request: Request):
    with connect() as conn:
        meeting = conn.execute(
            "SELECT * FROM meeting_summaries WHERE id = ?",
            (meeting_id,),
        ).fetchone()
    
    screenshots = get_meeting_screenshots(meeting_id)

    return templates.TemplateResponse(
        "view_meeting.html",
        {"request": request, "meeting": meeting, "screenshots": screenshots},
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
    # Clean the text (remove aside tags and markdown headers)
    cleaned_notes = clean_meeting_text(synthesized_notes)
    
    # Parse and extract structured signals
    parsed_sections = parse_meeting_summary(cleaned_notes)
    signals = extract_structured_signals(parsed_sections)
    
    with connect() as conn:
        conn.execute(
            """
            UPDATE meeting_summaries
            SET meeting_name = ?, synthesized_notes = ?, meeting_date = ?, signals_json = ?
            WHERE id = ?
            """,
            (meeting_name, cleaned_notes, meeting_date, json.dumps(signals), meeting_id),
        )

    # ---- VX.2b: embedding on update ----
    text_for_embedding = f"{meeting_name}\n{synthesized_notes}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("meeting", meeting_id, EMBED_MODEL, vector)

    return RedirectResponse(url="/meetings?success=meeting_updated", status_code=303)


@router.post("/meetings/{meeting_id}/delete")
def delete_meeting(meeting_id: int):
    with connect() as conn:
        conn.execute("DELETE FROM meeting_summaries WHERE id = ?", (meeting_id,))
        conn.execute(
            "DELETE FROM embeddings WHERE ref_type = 'meeting' AND ref_id = ?",
            (meeting_id,),
        )

    return RedirectResponse(url="/meetings?success=meeting_deleted", status_code=303)
