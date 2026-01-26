from fastapi import APIRouter, Form, Request, Query, UploadFile, File, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
import json
import base64
import logging

from .db import connect
from .memory.embed import embed_text, EMBED_MODEL
from .memory.vector_store import upsert_embedding
from .mcp.parser import parse_meeting_summary
from .mcp.extract import extract_structured_signals
from .mcp.cleaner import clean_meeting_text
from .services import meetings_supabase

logger = logging.getLogger(__name__)

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
    
    # Create meeting in Supabase (primary storage)
    import uuid
    meeting_data = {
        "id": str(uuid.uuid4()),
        "meeting_name": meeting_name,
        "synthesized_notes": cleaned_notes,
        "meeting_date": meeting_date,
        "signals_json": signals,  # Will be serialized by the service
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
    
    # ---- VX.2b: embedding on ingest ----
    # Include screenshot summaries in embedding for searchability
    screenshot_text = "\n\n".join([f"[Screenshot]: {s}" for s in screenshot_summaries]) if screenshot_summaries else ""
    text_for_embedding = f"{meeting_name}\n{synthesized_notes}\n{screenshot_text}"
    try:
        vector = embed_text(text_for_embedding)
        upsert_embedding("meeting", meeting_id, EMBED_MODEL, vector)
    except Exception as e:
        logger.warning(f"Failed to create embedding: {e}")

    # ---- Auto-sync to Neo4j knowledge graph ----
    if sync_single_meeting:
        try:
            sync_single_meeting(meeting_id, meeting_name, cleaned_notes, meeting_date, json.dumps(signals))
        except Exception:
            pass  # Neo4j sync is optional

    return RedirectResponse(url="/meetings?success=meeting_created", status_code=303)


@router.get("/meetings")
def list_meetings(request: Request, success: str = Query(default=None)):
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
                    dt = datetime.strptime(str(date_str).split(".")[0].split("+")[0], "%Y-%m-%d %H:%M:%S")
                    dt_utc = dt.replace(tzinfo=ZoneInfo("UTC"))
                    dt_central = dt_utc.astimezone(ZoneInfo("America/Chicago"))
                    meeting["display_date"] = dt_central.strftime("%Y-%m-%d %I:%M %p %Z")
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
    # Fetch from Supabase (primary source)
    meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    
    # Find linked transcript document
    linked_transcript = None
    documents = []
    if meeting:
        # Get documents from Supabase by meeting name
        from .services import documents_supabase
        all_docs = documents_supabase.get_all_documents(limit=100)
        meeting_name = meeting.get('meeting_name', '')
        documents = [d for d in all_docs if d.get('meeting_id') == meeting_id or (meeting_name and meeting_name in d.get('source', ''))]
        
        # Find transcript specifically for extract signals button
        for doc in documents:
            if doc.get('source', '').startswith(f"Transcript: {meeting_name}"):
                linked_transcript = doc
                break
    
    if not meeting:
        from fastapi.responses import RedirectResponse
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
    # Fetch from Supabase
    meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    
    # Find linked documents
    linked_transcript = None
    pocket_summary_doc = None
    if meeting:
        # Get documents from Supabase
        from .services import documents_supabase
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
    synthesized_notes: str = Form(...),
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
    
    # Also update linked transcript document if provided
    if linked_transcript_id and linked_transcript_content is not None:
        from .services import documents_supabase
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

    # ---- VX.2b: embedding on update ----
    try:
        text_for_embedding = f"{meeting_name}\n{synthesized_notes}"
        vector = embed_text(text_for_embedding)
        upsert_embedding("meeting", meeting_id, EMBED_MODEL, vector)
    except Exception as e:
        logger.warning(f"Failed to create embedding: {e}")
    
    # ---- AUTO-SYNTHESIS: trigger synthesis when mindmap is provided ----
    if pocket_mind_map and pocket_mind_map.strip():
        background_tasks.add_task(trigger_mindmap_synthesis, meeting_id, mindmap_level, pocket_mind_map)
        logger.info(f"Scheduled mindmap synthesis for meeting {meeting_id} at level {mindmap_level}")

    return RedirectResponse(url="/meetings?success=meeting_updated", status_code=303)


def trigger_mindmap_synthesis(meeting_id: str, level: int = 0, new_mindmap: str = None):
    """Background task to trigger mindmap synthesis after save.
    
    Only regenerates synthesis if the mindmap content has changed.
    """
    try:
        from .services.mindmap_synthesis import MindmapSynthesizer
        
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
    # Delete from Supabase
    success = meetings_supabase.delete_meeting(meeting_id)
    if not success:
        logger.error(f"Failed to delete meeting {meeting_id} from Supabase")
    
    # Note: Embeddings are stored in Supabase's vector table, deletion cascades

    return RedirectResponse(url="/meetings?success=meeting_deleted", status_code=303)


# ============================================
# ACTION ITEMS PAGE
# ============================================

@router.get("/action-items")
def list_action_items(
    request: Request,
    filter_status: str = Query(default="all"),
    filter_priority: str = Query(default="all"),
    sort_by: str = Query(default="date_desc"),
    group_by: str = Query(default="none")
):
    """Display all action items across all meetings."""
    
    all_action_items = []
    all_meetings = []
    
    # Keywords that suggest an action item should be a ticket
    ticket_keywords = ['implement', 'create', 'build', 'fix', 'refactor', 'deploy', 'migrate', 
                       'update', 'add', 'remove', 'investigate', 'research', 'design', 'test']
    
    with connect() as conn:
        # Get all meetings for the add form dropdown
        all_meetings = conn.execute(
            "SELECT id, meeting_name FROM meeting_summaries ORDER BY meeting_date DESC LIMIT 50"
        ).fetchall()
        
        meetings = conn.execute(
            """
            SELECT id, meeting_name, meeting_date, signals_json
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL AND signals_json != '{}'
            ORDER BY COALESCE(meeting_date, created_at) DESC
            """
        ).fetchall()
        
        for meeting in meetings:
            try:
                signals = json.loads(meeting['signals_json'] or '{}')
                raw_items = signals.get('action_items', [])
                
                for idx, item in enumerate(raw_items):
                    action_item = {
                        'meeting_id': meeting['id'],
                        'meeting_name': meeting['meeting_name'],
                        'meeting_date': meeting['meeting_date'],
                        'item_index': idx,
                        'completed': False,
                        'priority': 'medium',
                        'assignee': None,
                        'due_date': None,
                    }
                    
                    if isinstance(item, dict):
                        action_item['text'] = item.get('description') or item.get('text') or str(item)
                        action_item['assignee'] = item.get('assignee')
                        action_item['priority'] = item.get('priority', 'medium')
                        action_item['due_date'] = item.get('dueDate') or item.get('due_date')
                        action_item['completed'] = item.get('completed', False)
                        action_item['source'] = item.get('source', 'extracted')
                    else:
                        action_item['text'] = str(item)
                        action_item['source'] = 'extracted'
                    
                    # Check if item should suggest ticket creation
                    text_lower = action_item['text'].lower()
                    action_item['suggest_ticket'] = (
                        not action_item['completed'] and
                        action_item['priority'].lower() in ['high', 'medium'] and
                        any(kw in text_lower for kw in ticket_keywords)
                    )
                    
                    # Apply filters
                    if filter_status == 'completed' and not action_item['completed']:
                        continue
                    if filter_status == 'pending' and action_item['completed']:
                        continue
                    if filter_priority != 'all' and action_item['priority'].lower() != filter_priority.lower():
                        continue
                    
                    all_action_items.append(action_item)
            except (json.JSONDecodeError, TypeError):
                continue
    
    # Sort items
    if sort_by == 'date_desc':
        all_action_items.sort(key=lambda x: x['meeting_date'] or '', reverse=True)
    elif sort_by == 'date_asc':
        all_action_items.sort(key=lambda x: x['meeting_date'] or '')
    elif sort_by == 'priority':
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        all_action_items.sort(key=lambda x: priority_order.get(x['priority'].lower(), 1))
    elif sort_by == 'meeting':
        all_action_items.sort(key=lambda x: x['meeting_name'])
    
    # Group items if requested
    grouped_items = None
    if group_by == 'meeting':
        grouped_items = {}
        for item in all_action_items:
            meeting_name = item['meeting_name']
            if meeting_name not in grouped_items:
                grouped_items[meeting_name] = []
            grouped_items[meeting_name].append(item)
    elif group_by == 'priority':
        grouped_items = {'High': [], 'Medium': [], 'Low': []}
        for item in all_action_items:
            priority = item['priority'].capitalize()
            if priority not in grouped_items:
                grouped_items[priority] = []
            grouped_items[priority].append(item)
    
    # Calculate stats
    stats = {
        'total': len(all_action_items),
        'completed': sum(1 for i in all_action_items if i['completed']),
        'pending': sum(1 for i in all_action_items if not i['completed']),
        'high_priority': sum(1 for i in all_action_items if i['priority'].lower() == 'high'),
        'from_pocket': sum(1 for i in all_action_items if i.get('source') == 'pocket'),
    }
    
    return templates.TemplateResponse(
        "action_items.html",
        {
            "request": request,
            "action_items": all_action_items,
            "grouped_items": grouped_items,
            "all_meetings": [dict(m) for m in all_meetings],
            "stats": stats,
            "filter_status": filter_status,
            "filter_priority": filter_priority,
            "sort_by": sort_by,
            "group_by": group_by
        },
    )


@router.post("/api/action-items/{meeting_id}/{item_index}/toggle")
def toggle_action_item(meeting_id: int, item_index: int):
    """Toggle completion status of an action item."""
    
    with connect() as conn:
        meeting = conn.execute(
            "SELECT signals_json FROM meeting_summaries WHERE id = ?",
            (meeting_id,)
        ).fetchone()
        
        if not meeting or not meeting['signals_json']:
            return {"success": False, "error": "Meeting not found"}
        
        try:
            signals = json.loads(meeting['signals_json'])
            action_items = signals.get('action_items', [])
            
            if item_index < 0 or item_index >= len(action_items):
                return {"success": False, "error": "Invalid item index"}
            
            item = action_items[item_index]
            
            # Toggle completion
            if isinstance(item, dict):
                item['completed'] = not item.get('completed', False)
            else:
                # Convert string to dict
                action_items[item_index] = {
                    'text': item,
                    'description': item,
                    'completed': True
                }
            
            signals['action_items'] = action_items
            
            conn.execute(
                "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
                (json.dumps(signals), meeting_id)
            )
            
            return {"success": True, "completed": action_items[item_index].get('completed', True) if isinstance(action_items[item_index], dict) else True}
        except (json.JSONDecodeError, TypeError) as e:
            return {"success": False, "error": str(e)}


@router.post("/api/action-items/{meeting_id}/{item_index}/priority")
async def update_action_item_priority(meeting_id: int, item_index: int, request: Request):
    """Update the priority of an action item."""
    data = await request.json()
    new_priority = data.get('priority', 'medium')
    
    # Validate priority
    if new_priority not in ['low', 'medium', 'high']:
        return {"success": False, "error": "Invalid priority. Must be low, medium, or high"}
    
    with connect() as conn:
        meeting = conn.execute(
            "SELECT signals_json FROM meeting_summaries WHERE id = ?",
            (meeting_id,)
        ).fetchone()
        
        if not meeting or not meeting['signals_json']:
            return {"success": False, "error": "Meeting not found"}
        
        try:
            signals = json.loads(meeting['signals_json'])
            action_items = signals.get('action_items', [])
            
            if item_index < 0 or item_index >= len(action_items):
                return {"success": False, "error": "Invalid item index"}
            
            item = action_items[item_index]
            
            # Update priority
            if isinstance(item, dict):
                item['priority'] = new_priority
            else:
                # Convert string to dict
                action_items[item_index] = {
                    'text': item,
                    'description': item,
                    'priority': new_priority
                }
            
            signals['action_items'] = action_items
            
            conn.execute(
                "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
                (json.dumps(signals), meeting_id)
            )
            
            return {"success": True, "priority": new_priority}
        except (json.JSONDecodeError, TypeError) as e:
            return {"success": False, "error": str(e)}


@router.post("/api/action-items/add")
async def add_action_item(request: Request):
    """Add a custom action item."""
    data = await request.json()
    
    text = data.get('text')
    meeting_id = data.get('meeting_id')
    priority = data.get('priority', 'medium')
    assignee = data.get('assignee')
    due_date = data.get('due_date')
    
    if not text:
        return {"success": False, "error": "Text is required"}
    
    new_item = {
        'text': text,
        'description': text,
        'priority': priority,
        'assignee': assignee,
        'dueDate': due_date,
        'completed': False,
        'source': 'manual'
    }
    
    with connect() as conn:
        if meeting_id:
            # Add to existing meeting
            meeting = conn.execute(
                "SELECT signals_json FROM meeting_summaries WHERE id = ?",
                (meeting_id,)
            ).fetchone()
            
            if not meeting:
                return {"success": False, "error": "Meeting not found"}
            
            try:
                signals = json.loads(meeting['signals_json'] or '{}')
            except:
                signals = {}
            
            if 'action_items' not in signals:
                signals['action_items'] = []
            
            signals['action_items'].append(new_item)
            
            conn.execute(
                "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
                (json.dumps(signals), meeting_id)
            )
        else:
            # Create a "Personal Tasks" meeting if it doesn't exist
            personal_meeting = conn.execute(
                "SELECT id, signals_json FROM meeting_summaries WHERE meeting_name = 'Personal Action Items'"
            ).fetchone()
            
            if personal_meeting:
                try:
                    signals = json.loads(personal_meeting['signals_json'] or '{}')
                except:
                    signals = {}
                
                if 'action_items' not in signals:
                    signals['action_items'] = []
                
                signals['action_items'].append(new_item)
                
                conn.execute(
                    "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
                    (json.dumps(signals), personal_meeting['id'])
                )
            else:
                # Create new personal meeting
                from datetime import datetime
                signals = {'action_items': [new_item]}
                
                conn.execute(
                    """INSERT INTO meeting_summaries 
                       (meeting_name, meeting_date, signals_json, created_at)
                       VALUES (?, ?, ?, ?)""",
                    ('Personal Action Items', datetime.now().strftime('%Y-%m-%d'),
                     json.dumps(signals), datetime.now().isoformat())
                )
    
    return {"success": True}


@router.post("/api/action-items/create-ticket")
async def create_ticket_from_action_item(request: Request):
    """Create a ticket from an action item with context from meeting transcript."""
    data = await request.json()
    
    meeting_id = data.get('meeting_id')
    item_index = data.get('item_index')
    text = data.get('text')
    
    if not text:
        return {"success": False, "error": "Text is required"}
    
    with connect() as conn:
        # Create the ticket
        from datetime import datetime
        import uuid
        
        # Generate unique ticket_id
        ticket_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
        
        # Map priority
        priority_map = {'high': 1, 'medium': 2, 'low': 3}
        
        # Get action item details and meeting context
        priority = 2  # Default medium
        description_parts = []
        meeting_name = None
        meeting_date = None
        assignee = None
        
        if meeting_id is not None:
            meeting = conn.execute(
                """SELECT signals_json, meeting_name, meeting_date, raw_transcript, ai_summary, synthesized_notes 
                   FROM meeting_summaries WHERE id = ?""",
                (meeting_id,)
            ).fetchone()
            
            if meeting:
                meeting_name = meeting['meeting_name']
                meeting_date = meeting['meeting_date']
                
                try:
                    signals = json.loads(meeting['signals_json'] or '{}')
                    items = signals.get('action_items', [])
                    if 0 <= item_index < len(items):
                        item = items[item_index]
                        if isinstance(item, dict):
                            priority = priority_map.get(item.get('priority', 'medium').lower(), 2)
                            assignee = item.get('owner') or item.get('assignee')
                except:
                    pass
                
                # Build rich description from meeting context
                description_parts.append(f"## Source\n")
                description_parts.append(f"**Meeting:** {meeting_name or f'Meeting #{meeting_id}'}")
                if meeting_date:
                    description_parts.append(f"**Date:** {meeting_date}")
                if assignee:
                    description_parts.append(f"**Assignee:** {assignee}")
                description_parts.append("")
                
                # Add relevant decisions if available
                try:
                    signals = json.loads(meeting['signals_json'] or '{}')
                    decisions = signals.get('decisions', [])
                    if decisions:
                        description_parts.append("## Related Decisions")
                        for d in decisions[:3]:  # Limit to 3 most relevant
                            if isinstance(d, dict):
                                description_parts.append(f"- {d.get('text', d.get('description', str(d)))}")
                            else:
                                description_parts.append(f"- {d}")
                        description_parts.append("")
                except:
                    pass
                
                # Add context from synthesized notes or AI summary
                if meeting.get('synthesized_notes'):
                    # Extract a relevant section (first 500 chars)
                    notes = meeting['synthesized_notes'][:500]
                    if len(meeting['synthesized_notes']) > 500:
                        notes += "..."
                    description_parts.append("## Meeting Context")
                    description_parts.append(notes)
                    description_parts.append("")
                elif meeting.get('ai_summary'):
                    summary = meeting['ai_summary'][:500]
                    if len(meeting['ai_summary']) > 500:
                        summary += "..."
                    description_parts.append("## Meeting Summary")
                    description_parts.append(summary)
                    description_parts.append("")
                
                # Extract relevant transcript snippet if the action item text appears
                if meeting.get('raw_transcript'):
                    transcript = meeting['raw_transcript']
                    # Find where the action item text or keywords appear in transcript
                    keywords = text.lower().split()[:5]  # First 5 words
                    for keyword in keywords:
                        if len(keyword) > 4 and keyword in transcript.lower():
                            # Find the position and extract surrounding context
                            pos = transcript.lower().find(keyword)
                            start = max(0, pos - 200)
                            end = min(len(transcript), pos + 300)
                            snippet = transcript[start:end]
                            if start > 0:
                                snippet = "..." + snippet
                            if end < len(transcript):
                                snippet = snippet + "..."
                            description_parts.append("## Transcript Excerpt")
                            description_parts.append(f"```\n{snippet}\n```")
                            break
        
        # Fallback if no context was gathered
        if not description_parts:
            description_parts.append(f"Created from action item in meeting #{meeting_id}")
        
        description = "\n".join(description_parts)
        
        # Create ticket with rich description
        conn.execute(
            """INSERT INTO tickets 
               (ticket_id, title, description, priority, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticket_id, text, description, 
             priority, 'todo', datetime.now().isoformat())
        )
        
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Mark action item as converted to ticket AND completed
        if meeting_id is not None and item_index is not None:
            try:
                meeting = conn.execute(
                    "SELECT signals_json FROM meeting_summaries WHERE id = ?",
                    (meeting_id,)
                ).fetchone()
                
                if meeting:
                    signals = json.loads(meeting['signals_json'] or '{}')
                    items = signals.get('action_items', [])
                    if 0 <= item_index < len(items):
                        item = items[item_index]
                        if isinstance(item, dict):
                            item['converted_to_ticket'] = ticket_id
                            item['completed'] = True  # Auto-check the action item
                        else:
                            items[item_index] = {
                                'text': item,
                                'description': item,
                                'converted_to_ticket': ticket_id,
                                'completed': True  # Auto-check the action item
                            }
                        signals['action_items'] = items
                        conn.execute(
                            "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
                            (json.dumps(signals), meeting_id)
                        )
            except:
                pass  # Non-critical
    
    return {"success": True, "ticket_id": ticket_id, "row_id": row_id}


@router.post("/api/meetings/{meeting_id}/summarize-transcript")
async def summarize_meeting_transcript(meeting_id: str, request: Request):
    """
    Generate structured meeting summary from Teams transcript using GPT-4o.
    
    Uses the meeting notes template defined in config/templates/meeting_summary.md.
    Model: gpt-4o (configured in model_routing.yaml task_type: transcript_summarization)
    
    Body (optional):
        - transcript_text: Override transcript (otherwise uses meeting's teams_transcript)
        - focus_areas: List of areas to emphasize in extraction
    
    Returns:
        - draft_summary: Structured summary in template format
        - model_used: "gpt-4o"
        - sections: Parsed sections for programmatic access
    """
    from fastapi.responses import JSONResponse
    from .mcp.tools import draft_summary_from_transcript
    
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    transcript_text = body.get("transcript_text")
    focus_areas = body.get("focus_areas", [])
    
    # Get meeting from Supabase
    meeting = meetings_supabase.get_meeting_by_id(meeting_id)
    if not meeting:
        return JSONResponse({"success": False, "error": "Meeting not found"}, status_code=404)
    
    meeting_name = meeting.get("meeting_name") or meeting.get("title") or "Untitled Meeting"
    
    # Use provided transcript or extract from meeting's raw_text
    if not transcript_text:
        raw_text = meeting.get("raw_text") or ""
        
        # Try to extract Teams transcript from raw_text
        if "=== Teams Transcript ===" in raw_text:
            parts = raw_text.split("=== Teams Transcript ===")
            if len(parts) > 1:
                transcript_text = parts[1].strip()
        
        # Fallback to entire raw_text if no Teams section
        if not transcript_text:
            transcript_text = raw_text
    
    if not transcript_text or len(transcript_text) < 100:
        return JSONResponse({
            "success": False, 
            "error": "No transcript available. Paste Teams transcript in Edit Meeting first."
        }, status_code=400)
    
    # Call the MCP tool which uses GPT-4o
    result = draft_summary_from_transcript({
        "transcript": transcript_text,
        "meeting_name": meeting_name,
        "focus_areas": focus_areas
    })
    
    if result.get("status") == "error":
        return JSONResponse({
            "success": False,
            "error": result.get("error", "Unknown error during summarization")
        }, status_code=500)
    
    return JSONResponse({
        "success": True,
        "meeting_id": meeting_id,
        "meeting_name": meeting_name,
        "draft_summary": result.get("draft_summary"),
        "model_used": result.get("model_used", "gpt-4o"),
        "instructions": "Review and edit this summary, then save to the Summarized Notes field."
    })
