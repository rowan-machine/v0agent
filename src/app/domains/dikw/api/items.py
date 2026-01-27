# src/app/domains/dikw/api/items.py
"""
DIKW Items API - CRUD Operations

Handles basic CRUD for DIKW pyramid items.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

from ....repositories import get_dikw_repository
from ..constants import TIERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items")


def normalize_signal_type(signal_type: str) -> str:
    """Normalize signal type to standard format."""
    if not signal_type:
        return signal_type
    
    mapping = {
        "action_items": "action_item",
        "action-items": "action_item",
        "actions": "action_item",
        "decisions": "decision",
        "blockers": "blocker",
        "risks": "risk",
        "ideas": "idea",
        "insights": "insight",
    }
    return mapping.get(signal_type.lower(), signal_type)


@router.get("")
async def get_dikw_items(level: str = None, status: str = "active"):
    """Get DIKW items, optionally filtered by level."""
    repo = get_dikw_repository()
    
    items = repo.get_items(level=level, status=status)
    
    # Group by level for pyramid view
    pyramid = {lvl: [] for lvl in TIERS}
    for item in items:
        item_dict = item.__dict__ if hasattr(item, '__dict__') else dict(item)
        if item_dict.get('original_signal_type'):
            item_dict['original_signal_type'] = normalize_signal_type(item_dict['original_signal_type'])
        level_key = item_dict.get('level', 'data')
        if level_key in pyramid:
            pyramid[level_key].append(item_dict)
    
    return JSONResponse({
        "pyramid": pyramid,
        "counts": {lvl: len(pyramid[lvl]) for lvl in TIERS}
    })


@router.post("")
async def create_dikw_item(request: Request):
    """Create a new DIKW item directly."""
    from ....agents.dikw_synthesizer import generate_dikw_tags
    
    repo = get_dikw_repository()
    data = await request.json()
    
    level = data.get("level", "data")
    content = data.get("content", "")
    summary = data.get("summary", "")
    meeting_id = data.get("meeting_id")
    tags = data.get("tags") or generate_dikw_tags(content, level, "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    item = repo.create({
        "level": level,
        "content": content,
        "summary": summary or content[:200],
        "meeting_id": meeting_id,
        "source_type": "manual",
        "tags": tags,
        "validation_count": 1,
        "confidence": 70
    })
    
    return JSONResponse({
        "status": "ok", 
        "id": item.id if item else None
    })


@router.put("/{item_id}")
async def update_dikw_item(item_id: int, request: Request):
    """Update an existing DIKW item."""
    from ....agents.dikw_synthesizer import generate_dikw_tags
    
    repo = get_dikw_repository()
    data = await request.json()
    
    # Build update data
    update_data = {}
    
    if "level" in data:
        update_data["level"] = data["level"]
    if "content" in data:
        update_data["content"] = data["content"]
    if "summary" in data:
        update_data["summary"] = data["summary"]
    if "tags" in data:
        update_data["tags"] = data["tags"]
    if "status" in data:
        update_data["status"] = data["status"]
    if "confidence" in data:
        update_data["confidence"] = data["confidence"]
    
    # Auto-regenerate tags if content changed and tags not provided
    if "content" in data and "tags" not in data:
        level = data.get("level", "data")
        update_data["tags"] = generate_dikw_tags(data["content"], level, "")
    
    if not update_data:
        return JSONResponse({"error": "No update fields provided"}, status_code=400)
    
    update_data["updated_at"] = datetime.now().isoformat()
    
    item = repo.update(item_id, update_data)
    
    if not item:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    return JSONResponse({"status": "ok", "item": item.__dict__ if hasattr(item, '__dict__') else item})


@router.delete("/{item_id}")
async def delete_dikw_item(item_id: int):
    """Delete a DIKW item (soft delete - sets status to archived)."""
    repo = get_dikw_repository()
    
    repo.delete(item_id, soft=True)
    
    return JSONResponse({"status": "ok"})


@router.get("/{item_id}/history")
async def get_dikw_item_history(item_id: int):
    """Get evolution history for a DIKW item."""
    repo = get_dikw_repository()
    
    history = repo.get_history(item_id)
    
    return JSONResponse({
        "status": "ok",
        "history": [h.__dict__ if hasattr(h, '__dict__') else h for h in history] if history else []
    })
