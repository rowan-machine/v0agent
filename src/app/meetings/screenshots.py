# src/app/meetings/screenshots.py
"""
Meeting screenshot processing module.

Handles:
- Processing uploaded screenshots with vision API
- Storing screenshot summaries
- Retrieving screenshots for meetings
"""

from typing import List
from fastapi import UploadFile
import base64
import logging

from ..infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def process_screenshots(meeting_id: int, screenshots: List[UploadFile]) -> List[str]:
    """
    Process uploaded screenshots with vision API and store summaries.
    
    Args:
        meeting_id: The meeting ID to associate screenshots with
        screenshots: List of uploaded screenshot files
        
    Returns:
        List of screenshot summary texts
    """
    # Lazy import VisionAgent for checkpoint compatibility
    from ..agents.vision import VisionAgent
    
    supabase = get_supabase_client()
    summaries = []
    
    for screenshot in screenshots:
        try:
            # Read and encode image
            image_data = screenshot.file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Analyze with vision agent
            vision = VisionAgent()
            result = vision.analyze_meeting_screenshot(
                base64_image, 
                format="jpeg" if screenshot.filename.lower().endswith(('.jpg', '.jpeg')) else "png"
            )
            
            if result.get("success"):
                summary = result.get("analysis", "")
                summaries.append(summary)
                
                # Store in Supabase
                supabase.table("meeting_screenshots").insert({
                    "meeting_id": meeting_id,
                    "filename": screenshot.filename,
                    "image_summary": summary
                }).execute()
                
        except Exception as e:
            logger.warning(f"Failed to process screenshot {screenshot.filename}: {e}")
            
    return summaries


def get_meeting_screenshots(meeting_id: int) -> List[dict]:
    """
    Get all screenshot summaries for a meeting.
    
    Args:
        meeting_id: The meeting ID to get screenshots for
        
    Returns:
        List of screenshot records with id, filename, image_summary, created_at
    """
    supabase = get_supabase_client()
    result = supabase.table("meeting_screenshots").select(
        "id, filename, image_summary, created_at"
    ).eq("meeting_id", meeting_id).order("created_at").execute()
    return result.data or []
