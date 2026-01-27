# src/app/meetings/routes.py
"""
Meeting CRUD routes.

Handles:
- Meeting creation (synthesize)
- Meeting listing
- Meeting viewing
- Meeting editing and updating
- Meeting deletion
- Mindmap synthesis triggering
"""

from fastapi import APIRouter, Form, Request, Query, UploadFile, File, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import List
import json
import logging

from ..infrastructure.supabase_client import get_supabase_client
from ..memory.embed import embed_text, EMBED_MODEL
from ..memory.vector_store import upsert_embedding
from ..mcp.parser import parse_meeting_summary
from ..mcp.extract import extract_structured_signals
from ..mcp.cleaner import clean_meeting_text
from ..services import meetings_supabase
from .screenshots import process_screenshots, get_meeting_screenshots

logger = logging.getLogger(__name__)

# Neo4j sync (optional - fails silently if unavailable)
try:
    from ..api.neo4j_graph import sync_single_meeting
except ImportError:
    sync_single_meeting = None

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


@router.post("/meetings/synthesize")
async def store_meeting(
    meeting_name: str = Form(...),
    synthesized_notes: str = Form(...),
    meeting_date: str = Form(...),
    screenshots: List[UploadFile] = File(default=[])
):
    """Create a new meeting with synthesized notes."""
    # Clean the text (remove aside tags and markdown headers)
    cleaned_notes = clean_meeting_text(synthesized_notes)
    
    # Parse and extract structured signals
    parsed_sections = parse_meeting_summary(cleaned_notes)
    signals = extract_structured_signals(parsed_sections)
    
    # Create meeting in Supabase (primary storage)
    import uuid
    meeting_data = {
        "id": str(uuid.uuid4()),
        "meeting_name": meeting_name,
        "synthesized_notes": cleaned_notes,
        "meeting_date": meeting_date,
        "signals_json": signals,
    }
    
    created = meetings_supabase.create_meeting(meeting_data)
    if not created:
        logger.error("Failed to create meeting in Supabase")
        return RedirectResponse(url="/meetings?error=create_failed", status_code=303)
    
    meeting_id = created.get("id")
    logger.info(f"Created meeting {meeting_id} in Supabase")

    # Process screenshots with vision API
    screenshot_summaries = []
    if screenshots:
        screenshot_summaries = process_screenshots(meeting_id, screenshots)
    
    # Embedding on ingest - include screenshot summaries for searchability
    screenshot_text = "\n\n".join([f"[Screenshot]: {s}" for s in screenshot_summaries]) if screenshot_summaries else ""
    text_for_embedding = f"{meeting_name}\n{synthesized_notes}\n{screenshot_text}"
    try:
        vector = embed_text(text_for_embedding)
        upsert_embedding("meeting", meeting_id, EMBED_MODEL, vector)
    except Exception as e:
        logger.warning(f"Failed to create embedding: {e}")

    # Auto-sync to Neo4j knowledge graph
    if sync_single_meeting:
        try:
            sync_single_meeting(meeting_id, meeting_name, cleaned_notes, meeting_date, json.dumps(signals))
        except Exception:
            pass  # Neo4j sync is optional

    return RedirectResponse(url="/meetings?success=meeting_created", status_code=303)


@router.get("/meetings")
def list_meetings(request: Request, success: str = Query(default=None)):
    """List all meetings."""
    # Use Supabase as primary source
    meetings_list = meetings_supabase.get_all_meetings(limit=500)
    
    formatted = []
    for meeting in meetings_list:
        # Ensure meeting is a proper dict
        if not isinstance(meeting, dict):
            meeting = dict(meeting) if hasattr(meeting, '__iter__') else {}
        
        date_str = meeting.get("meeting_date") or meeting.get("created_at")
        if date_str:
            try:
                # Handle ISO format from Supabase
                if "T" in str(date_str):
                    date_str = str(date_str).split("T")[0]
                    meeting["display_date"] = date_str
                elif " " in str(date_str):
                    # Just extract the date part, no time
                    meeting["display_date"] = str(date_str).split(" ")[0]
                else:
                    meeting["display_date"] = str(date_str)
            except Exception:
                meeting["display_date"] = str(date_str) if date_str else ""
        else:
            meeting["display_date"] = ""
        
        # Ensure meeting_name exists
        if "meeting_name" not in meeting or not meeting.get("meeting_name"):
            meeting["meeting_name"] = "Untitled Meeting"

        formatted.append(meeting)

    return templates.TemplateResponse(
        "list_meetings.html",
        {"request": request, "meetings": formatted, "success": success},
    )


@router.get("/meetings/{meeting_id}")
def view_meeting(meeting_id: str, request: Request):
    """View a single meeting."""
    # Fetch from Supabase (primary source)
    meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    
    # Find linked transcript document
    linked_transcript = None
    documents = []
    if meeting:
        # Get documents from Supabase linked to THIS meeting only (by meeting_id)
        from ..services import documents_supabase
        all_docs = documents_supabase.get_all_documents(limit=100)
        meeting_name = meeting.get('meeting_name', '')
        # Only include documents that are explicitly linked to this meeting by ID
        documents = [d for d in all_docs if d.get('meeting_id') == meeting_id]
        
        # Find transcript specifically for extract signals button
        for doc in documents:
            if doc.get('source', '').startswith(f"Transcript: {meeting_name}"):
                linked_transcript = doc
                break
    
    if not meeting:
        return RedirectResponse(url="/meetings?error=meeting_not_found", status_code=303)
    
    # Convert to dict for template
    meeting_dict = dict(meeting)
    
    # Parse signals from signals_json
    signals = {}
    action_items = []
    if meeting_dict.get('signals_json'):
        try:
            signals = json.loads(meeting_dict['signals_json'])
            # Extract action items from signals - handle both string and dict formats
            raw_items = signals.get('action_items', [])
            for item in raw_items:
                if isinstance(item, dict):
                    action_items.append(item)
                elif isinstance(item, str):
                    action_items.append({'text': item, 'description': item})
        except (json.JSONDecodeError, TypeError):
            pass
    
    screenshots = get_meeting_screenshots(meeting_id)

    return templates.TemplateResponse(
        "view_meeting.html",
        {
            "request": request, 
            "meeting": meeting_dict, 
            "screenshots": screenshots, 
            "linked_transcript": linked_transcript,
            "documents": documents,
            "signals": signals,
            "action_items": action_items
        },
    )


@router.get("/meetings/{meeting_id}/edit")
def edit_meeting(meeting_id: str, request: Request, from_transcript: str = None):
    """Edit a meeting."""
    # Fetch from Supabase
    meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    
    # Find linked documents
    linked_transcript = None
    pocket_summary_doc = None
    if meeting:
        # Get documents from Supabase
        from ..services import documents_supabase
        all_docs = documents_supabase.get_all_documents(limit=100)
        meeting_name = meeting.get('meeting_name', '')
        
        # Find transcript doc
        for doc in all_docs:
            source = doc.get('source', '')
            if doc.get('meeting_id') == meeting_id and source.startswith('Transcript:'):
                linked_transcript = doc
            elif meeting_name and source.startswith(f"Transcript: {meeting_name}"):
                linked_transcript = doc
            
            # Also check for Pocket summary doc
            if doc.get('meeting_id') == meeting_id and source.startswith('Pocket Summary'):
                pocket_summary_doc = doc
    
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
    meeting_id: str,
    background_tasks: BackgroundTasks,
    meeting_name: str = Form(...),
    synthesized_notes: str = Form(""),
    meeting_date: str = Form(...),
    raw_text: str = Form(None),
    signals_json: str = Form(None),
    linked_transcript_id: str = Form(None),
    linked_transcript_content: str = Form(None),
    pocket_transcript: str = Form(None),
    teams_transcript: str = Form(None),
    pocket_ai_summary: str = Form(None),
    pocket_mind_map: str = Form(None),
    mindmap_level: int = Form(0)
):
    """Update a meeting."""
    import re
    
    # Preserve notes as-is (don't strip markdown formatting)
    # Only clean aside tags that might interfere with display
    cleaned_notes = synthesized_notes
    if cleaned_notes:
        # Only remove aside tags, preserve markdown headers and formatting
        cleaned_notes = re.sub(r'<aside[^>]*>', '', cleaned_notes)
        cleaned_notes = re.sub(r'</aside>', '', cleaned_notes)
    
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
    
    logger.info(f"Updating meeting {meeting_id}: date={meeting_date}, name={meeting_name[:30] if meeting_name else 'N/A'}")
    
    # Update meeting in Supabase
    update_data = {
        "meeting_name": meeting_name,
        "synthesized_notes": cleaned_notes,
        "meeting_date": meeting_date,
        "signals_json": signals,
        "raw_text": merged_raw_text,
        "pocket_ai_summary": pocket_ai_summary or "",
        "pocket_mind_map": pocket_mind_map or "",
    }
    
    updated = meetings_supabase.update_meeting(meeting_id, update_data)
    if not updated:
        logger.error(f"Failed to update meeting {meeting_id} in Supabase")
    else:
        logger.info(f"Successfully updated meeting {meeting_id}")
    
    # Also update linked transcript document if provided
    if linked_transcript_id and linked_transcript_content is not None:
        from ..services import documents_supabase
        documents_supabase.update_document(linked_transcript_id, {"content": linked_transcript_content})
        
        # Update document embedding
        doc = documents_supabase.get_document_by_id(linked_transcript_id)
        if doc:
            try:
                doc_embed_text = f"{doc.get('source', '')}\n{linked_transcript_content}"
                doc_vector = embed_text(doc_embed_text)
                upsert_embedding("doc", linked_transcript_id, EMBED_MODEL, doc_vector)
            except Exception as e:
                logger.warning(f"Failed to update document embedding: {e}")

    # Embedding on update
    try:
        text_for_embedding = f"{meeting_name}\n{synthesized_notes}"
        vector = embed_text(text_for_embedding)
        upsert_embedding("meeting", meeting_id, EMBED_MODEL, vector)
    except Exception as e:
        logger.warning(f"Failed to create embedding: {e}")
    
    # AUTO-SYNTHESIS: trigger synthesis when mindmap is provided
    if pocket_mind_map and pocket_mind_map.strip():
        background_tasks.add_task(trigger_mindmap_synthesis, meeting_id, mindmap_level, pocket_mind_map)
        logger.info(f"Scheduled mindmap synthesis for meeting {meeting_id} at level {mindmap_level}")

    return RedirectResponse(url="/meetings?success=meeting_updated", status_code=303)


def trigger_mindmap_synthesis(meeting_id: str, level: int = 0, new_mindmap: str = None):
    """Background task to trigger mindmap synthesis after save.
    
    Only regenerates synthesis if the mindmap content has changed.
    """
    try:
        from ..services.mindmap_synthesis import MindmapSynthesizer
        
        # Get meeting from Supabase
        meeting = meetings_supabase.get_meeting_by_id(meeting_id)
        
        if not meeting or not meeting.get('pocket_mind_map'):
            return
        
        mindmap_changed = True  # Assume changed for now, synthesis will handle dedup
        
        if mindmap_changed:
            # Store/update the mindmap for this conversation
            MindmapSynthesizer.store_conversation_mindmap(
                conversation_id=f"meeting_{meeting_id}",
                title=meeting.get('meeting_name', ''),
                mindmap_data=meeting.get('pocket_mind_map', ''),
                hierarchy_level=level
            )
            
            # Only regenerate synthesis if mindmaps changed
            if MindmapSynthesizer.needs_synthesis():
                MindmapSynthesizer.generate_synthesis(force=True)
                logger.info(f"✅ Mindmap synthesis completed for meeting {meeting_id}")
            else:
                logger.info(f"No synthesis needed for meeting {meeting_id}")
            
    except Exception as e:
        logger.error(f"Failed to trigger mindmap synthesis: {e}")


@router.post("/meetings/{meeting_id}/delete")
def delete_meeting(meeting_id: str):
    """Delete a meeting."""
    # Delete from Supabase
    success = meetings_supabase.delete_meeting(meeting_id)
    if not success:
        logger.error(f"Failed to delete meeting {meeting_id} from Supabase")
    
    # Note: Embeddings are stored in Supabase's vector table, deletion cascades

    return RedirectResponse(url="/meetings?success=meeting_deleted", status_code=303)
