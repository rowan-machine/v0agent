# src/app/domains/meetings/api/load_bundle.py
"""
Meeting Bundle Loading API

Handles loading complete meeting bundles with:
- Structured summary (canonical format)
- Optional Pocket AI summary
- Optional Pocket Mind Map
- Optional Pocket Action Items
- Optional transcripts
- Optional screenshots

Extracted from main.py for cleaner architecture.
"""

import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse

from ....services import meeting_service
from ....mcp.registry import TOOL_REGISTRY
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

# Upload directory for fallback local storage
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/meetings/load")
async def load_meeting_bundle_ui(
    request: Request,
    background_tasks: BackgroundTasks,
    meeting_name: str = Form(...),
    meeting_date: str = Form(None),
    summary_text: str = Form(...),
    pocket_recording_id: str = Form(None),
    pocket_ai_summary: str = Form(None),
    pocket_mind_map: str = Form(None),
    mindmap_level: int = Form(0),
    pocket_action_items: str = Form(None),
    pocket_transcript: str = Form(None),
    teams_transcript: str = Form(None),
):
    """
    Load a complete meeting bundle with:
    - Structured summary (canonical format)
    - Optional Pocket AI summary (creates document for signal extraction)
    - Optional Pocket Mind Map (triggers synthesis)
    - Optional Pocket Action Items (merged into signals_json)
    - Optional transcripts (merged into searchable document)
    - Optional screenshots (attached to meeting)
    """
    tool = TOOL_REGISTRY["load_meeting_bundle"]
    
    # Merge transcripts if provided
    transcript_parts = []
    if pocket_transcript and pocket_transcript.strip():
        transcript_parts.append(f"=== Pocket Transcript ===\n{pocket_transcript.strip()}")
    if teams_transcript and teams_transcript.strip():
        transcript_parts.append(f"=== Teams Transcript ===\n{teams_transcript.strip()}")
    
    merged_transcript = "\n\n".join(transcript_parts) if transcript_parts else None

    result = tool({
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "summary_text": summary_text,
        "transcript_text": merged_transcript,
        "pocket_ai_summary": pocket_ai_summary,
        "pocket_mind_map": pocket_mind_map,
        "pocket_recording_id": pocket_recording_id,
        "format": "plain",
    })
    
    meeting_id = result.get("meeting_id")
    
    # Store Pocket action items in signals if provided
    if meeting_id and pocket_action_items and pocket_action_items.strip():
        await _store_pocket_action_items(meeting_id, pocket_action_items)
    
    # Handle screenshot uploads if meeting was created successfully
    if meeting_id:
        await _handle_screenshot_uploads(request, meeting_id)
        
        # Auto-trigger synthesis if mindmap was provided
        if pocket_mind_map and pocket_mind_map.strip():
            _schedule_mindmap_synthesis(
                background_tasks, meeting_id, meeting_name, 
                pocket_mind_map, mindmap_level
            )

    return RedirectResponse(
        url="/meetings?success=meeting_loaded",
        status_code=303,
    )


async def _store_pocket_action_items(meeting_id: int, pocket_action_items: str) -> None:
    """Store Pocket action items in meeting signals."""
    try:
        # Parse JSON from hidden field (contains array of action item objects)
        pocket_items = json.loads(pocket_action_items.strip())
        
        # Add source marker to each item
        for item in pocket_items:
            item["source"] = "pocket"
        
        if pocket_items:
            # Get current meeting signals from Supabase
            meeting = meeting_service.get_meeting_by_id(meeting_id)
            if meeting:
                signals = meeting.get("signals", {})
                
                # Merge Pocket action items (preserve existing)
                existing_items = signals.get("action_items", [])
                signals["action_items"] = existing_items + pocket_items
                
                # Update in Supabase
                meeting_service.update_meeting(meeting_id, {"signals": signals})
                
            logger.info(f"Added {len(pocket_items)} Pocket action items to meeting {meeting_id}")
    except Exception as e:
        logger.warning(f"Failed to parse/store Pocket action items: {e}")


async def _handle_screenshot_uploads(request: Request, meeting_id: int) -> None:
    """Handle screenshot file uploads for a meeting."""
    supabase = get_supabase_client()
    if not supabase:
        logger.warning("Supabase not available for screenshot uploads")
        return
    
    form = await request.form()
    screenshots = form.getlist("screenshots")
    
    for screenshot in screenshots:
        if hasattr(screenshot, 'file') and screenshot.filename:
            try:
                content = await screenshot.read()
                mime_type = screenshot.content_type or 'image/png'
                
                # Try Supabase Storage first
                supabase_url = None
                supabase_path = None
                local_path = None
                
                try:
                    from ....services.storage_supabase import upload_file_to_supabase
                    supabase_url, supabase_path = await upload_file_to_supabase(
                        content=content,
                        filename=screenshot.filename,
                        meeting_id=meeting_id,
                        content_type=mime_type
                    )
                except Exception as e:
                    logger.warning(f"Supabase upload failed, using local: {e}")
                
                # Fallback to local storage if Supabase fails
                if not supabase_url:
                    ext = os.path.splitext(screenshot.filename)[1] or '.png'
                    unique_name = f"{uuid.uuid4().hex}{ext}"
                    file_path = os.path.join(UPLOAD_DIR, unique_name)
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    local_path = f"uploads/{unique_name}"
                
                # Record in Supabase attachments table
                supabase.table("attachments").insert({
                    "ref_type": "meeting",
                    "ref_id": meeting_id,
                    "filename": screenshot.filename,
                    "file_path": local_path or "",
                    "mime_type": mime_type,
                    "file_size": len(content),
                    "supabase_url": supabase_url,
                    "supabase_path": supabase_path
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to upload screenshot: {e}")


def _schedule_mindmap_synthesis(
    background_tasks: BackgroundTasks,
    meeting_id: int,
    meeting_name: str,
    pocket_mind_map: str,
    mindmap_level: int
) -> None:
    """Schedule background mindmap synthesis task."""
    def trigger_synthesis():
        try:
            from ....services.mindmap_synthesis import MindmapSynthesizer
            
            # Store the mindmap for this conversation
            MindmapSynthesizer.store_conversation_mindmap(
                conversation_id=f"meeting_{meeting_id}",
                title=meeting_name,
                mindmap_data=pocket_mind_map,
                hierarchy_level=mindmap_level
            )
            
            # Regenerate synthesis
            MindmapSynthesizer.generate_synthesis(force=True)
            logger.info(f"✅ Mindmap synthesis triggered for new meeting {meeting_id}")
        except Exception as e:
            logger.error(f"Failed to trigger mindmap synthesis: {e}")
    
    background_tasks.add_task(trigger_synthesis)
    logger.info(f"Scheduled mindmap synthesis for meeting {meeting_id} at level {mindmap_level}")
