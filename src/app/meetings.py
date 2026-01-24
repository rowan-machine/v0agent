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

# Neo4j sync (optional - fails silently if unavailable)
try:
    from .api.neo4j_graph import sync_single_meeting
except ImportError:
    sync_single_meeting = None
# llm.analyze_image removed - use VisionAgent adapter with lazy import (Checkpoint 1.x)

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


def process_screenshots(meeting_id: int, screenshots: List[UploadFile]) -> List[str]:
    """
    Process uploaded screenshots with vision API and store summaries.
    
    Delegates to VisionAgent.analyze() for AI-powered image analysis.
    """
    # Lazy import for backward compatibility (Checkpoint 1.x pattern)
    from .agents.vision import analyze_image_adapter
    
    summaries = []
    
    for screenshot in screenshots:
        if not screenshot.filename or screenshot.size == 0:
            continue
            
        try:
            # Read image data
            image_data = screenshot.file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Analyze with VisionAgent adapter
            summary = analyze_image_adapter(image_base64)
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

    # ---- Auto-sync to Neo4j knowledge graph ----
    if sync_single_meeting:
        try:
            sync_single_meeting(meeting_id, meeting_name, cleaned_notes, meeting_date, json.dumps(signals))
        except Exception:
            pass  # Neo4j sync is optional

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
        
        # Find linked transcript document
        linked_transcript = None
        if meeting:
            transcript = conn.execute(
                "SELECT id, source FROM docs WHERE source LIKE ?",
                (f"Transcript: {meeting['meeting_name']}%",)
            ).fetchone()
            if transcript:
                linked_transcript = dict(transcript)
    
    screenshots = get_meeting_screenshots(meeting_id)

    return templates.TemplateResponse(
        "view_meeting.html",
        {"request": request, "meeting": meeting, "screenshots": screenshots, "linked_transcript": linked_transcript},
    )


@router.get("/meetings/{meeting_id}/edit")
def edit_meeting(meeting_id: int, request: Request, from_transcript: int = None):
    with connect() as conn:
        meeting = conn.execute(
            "SELECT * FROM meeting_summaries WHERE id = ?",
            (meeting_id,),
        ).fetchone()
        
        # If coming from a transcript edit, also load the transcript content
        linked_transcript = None
        pocket_summary_doc = None
        if meeting:
            # Check for transcript docs linked by meeting_id
            transcript = conn.execute(
                "SELECT id, source, content FROM docs WHERE meeting_id = ? AND source LIKE 'Transcript:%'",
                (meeting_id,)
            ).fetchone()
            # Fallback to name matching if no meeting_id link
            if not transcript:
                transcript = conn.execute(
                    "SELECT id, source, content FROM docs WHERE source LIKE ?",
                    (f"Transcript: {meeting['meeting_name']}%",)
                ).fetchone()
            if transcript:
                linked_transcript = dict(transcript)
            
            # Also check for Pocket summary doc linked by meeting_id
            pocket_doc = conn.execute(
                "SELECT id, source, content FROM docs WHERE meeting_id = ? AND source LIKE 'Pocket Summary%'",
                (meeting_id,)
            ).fetchone()
            if pocket_doc:
                pocket_summary_doc = dict(pocket_doc)
    
    # Convert to dict and parse out pocket/teams transcripts from raw_text
    meeting_dict = dict(meeting) if meeting else {}
    raw_text = meeting_dict.get('raw_text', '') or ''
    
    # Parse pocket and teams transcripts from raw_text
    pocket_transcript = ''
    teams_transcript = ''
    
    if '=== Pocket Transcript ===' in raw_text:
        parts = raw_text.split('=== Pocket Transcript ===')
        if len(parts) > 1:
            pocket_part = parts[1]
            if '=== Teams Transcript ===' in pocket_part:
                pocket_transcript = pocket_part.split('=== Teams Transcript ===')[0].strip()
            else:
                pocket_transcript = pocket_part.strip()
    
    if '=== Teams Transcript ===' in raw_text:
        parts = raw_text.split('=== Teams Transcript ===')
        if len(parts) > 1:
            teams_transcript = parts[1].strip()
    
    # If raw_text doesn't have section markers, use it as the transcript
    if raw_text and not pocket_transcript and not teams_transcript and '===' not in raw_text:
        teams_transcript = raw_text
    
    # If we have a linked transcript and no teams_transcript yet, use it
    if linked_transcript and not teams_transcript:
        teams_transcript = linked_transcript.get('content', '')
    
    meeting_dict['pocket_transcript'] = pocket_transcript
    meeting_dict['teams_transcript'] = teams_transcript
    
    # If pocket_ai_summary is empty but we found a Pocket doc, use that
    if not meeting_dict.get('pocket_ai_summary') and pocket_summary_doc:
        meeting_dict['pocket_ai_summary'] = pocket_summary_doc.get('content', '')

    return templates.TemplateResponse(
        "edit_meeting.html",
        {"request": request, "meeting": meeting_dict, "linked_transcript": linked_transcript, "from_transcript": from_transcript},
    )


@router.post("/meetings/{meeting_id}/edit")
def update_meeting(
    meeting_id: int,
    meeting_name: str = Form(...),
    synthesized_notes: str = Form(...),
    meeting_date: str = Form(...),
    raw_text: str = Form(None),
    signals_json: str = Form(None),
    linked_transcript_id: int = Form(None),
    linked_transcript_content: str = Form(None),
    pocket_transcript: str = Form(None),
    teams_transcript: str = Form(None),
    pocket_ai_summary: str = Form(None),
    pocket_mind_map: str = Form(None)
):
    # Clean the text (remove aside tags and markdown headers)
    cleaned_notes = clean_meeting_text(synthesized_notes)
    
    # Merge pocket and teams transcripts into raw_text
    transcript_parts = []
    if pocket_transcript and pocket_transcript.strip():
        transcript_parts.append(f"=== Pocket Transcript ===\n{pocket_transcript.strip()}")
    if teams_transcript and teams_transcript.strip():
        transcript_parts.append(f"=== Teams Transcript ===\n{teams_transcript.strip()}")
    
    # If we have transcript parts, use them; otherwise keep existing raw_text
    if transcript_parts:
        merged_raw_text = "\n\n".join(transcript_parts)
    else:
        merged_raw_text = raw_text or ""
    
    # If signals_json was provided by user, use it; otherwise extract from notes
    if signals_json and signals_json.strip():
        try:
            signals = json.loads(signals_json)
        except json.JSONDecodeError:
            # Fall back to extraction if JSON is invalid
            parsed_sections = parse_meeting_summary(cleaned_notes)
            signals = extract_structured_signals(parsed_sections)
    else:
        # Parse and extract structured signals
        parsed_sections = parse_meeting_summary(cleaned_notes)
        signals = extract_structured_signals(parsed_sections)
    
    with connect() as conn:
        conn.execute(
            """
            UPDATE meeting_summaries
            SET meeting_name = ?, synthesized_notes = ?, meeting_date = ?, signals_json = ?, raw_text = ?, pocket_ai_summary = ?, pocket_mind_map = ?
            WHERE id = ?
            """,
            (meeting_name, cleaned_notes, meeting_date, json.dumps(signals), merged_raw_text, pocket_ai_summary or "", pocket_mind_map or "", meeting_id),
        )
        
        # Also update linked transcript document if provided
        if linked_transcript_id and linked_transcript_content is not None:
            conn.execute(
                "UPDATE docs SET content = ? WHERE id = ?",
                (linked_transcript_content, linked_transcript_id)
            )
            # Update document embedding
            doc = conn.execute("SELECT source FROM docs WHERE id = ?", (linked_transcript_id,)).fetchone()
            if doc:
                doc_embed_text = f"{doc['source']}\n{linked_transcript_content}"
                doc_vector = embed_text(doc_embed_text)
                upsert_embedding("doc", linked_transcript_id, EMBED_MODEL, doc_vector)

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
