# src/app/domains/dikw/api/promotion.py
"""
DIKW Promotion API

Handles level promotion and merge operations in the DIKW pyramid.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_dikw_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/promotion")

# Level progression mapping
NEXT_LEVEL = {
    "data": "information",
    "information": "knowledge",
    "knowledge": "wisdom"
}


@router.post("/signal")
async def promote_signal_to_dikw(request: Request):
    """Promote a signal to the DIKW pyramid (starts as Data level)."""
    from ....agents.dikw_synthesizer import ai_summarize_dikw_adapter, generate_dikw_tags
    
    repo = get_dikw_repository()
    data = await request.json()
    
    signal_text = data.get("signal_text", "")
    signal_type = data.get("signal_type", "")
    meeting_id = data.get("meeting_id")
    target_level = data.get("level", "data")
    
    if not signal_text:
        return JSONResponse({"error": "Signal text is required"}, status_code=400)
    
    # AI summary generation
    try:
        summary = await ai_summarize_dikw_adapter(signal_text, target_level)
    except Exception:
        summary = signal_text[:200]
    
    tags = generate_dikw_tags(signal_text, target_level, signal_type)
    
    item = repo.create({
        "level": target_level,
        "content": signal_text,
        "summary": summary,
        "source_type": "signal",
        "original_signal_type": signal_type,
        "meeting_id": meeting_id,
        "validation_count": 1,
        "tags": tags
    })
    
    item_id = item.id if item else None
    
    return JSONResponse({
        "status": "ok", 
        "id": item_id, 
        "level": target_level, 
        "tags": tags
    })


@router.post("/item")
async def promote_dikw_item(request: Request):
    """Promote a DIKW item to the next level (with AI synthesis)."""
    from ....agents.dikw_synthesizer import ai_promote_dikw_adapter, generate_dikw_tags
    
    repo = get_dikw_repository()
    data = await request.json()
    
    item_id = data.get("item_id")
    to_level = data.get("to_level")
    promoted_content = data.get("promoted_content")
    provided_summary = data.get("summary")
    
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    item = repo.get_by_id(item_id)
    
    if not item:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    current_level = item.level
    
    if current_level == 'wisdom' and not to_level:
        return JSONResponse({"error": "Already at highest level"}, status_code=400)
    
    next_level = to_level if to_level else NEXT_LEVEL.get(current_level, 'wisdom')
    new_content = promoted_content if promoted_content else item.content
    
    # Generate AI synthesis
    if provided_summary:
        new_summary = provided_summary
    else:
        try:
            result = await ai_promote_dikw_adapter(new_content, current_level, next_level)
            new_summary = result.get('summary', f"Promoted from {current_level}: {item.summary or ''}")
        except Exception:
            new_summary = f"Promoted from {current_level}: {item.summary or ''}"
    
    # Normalize confidence
    current_confidence = item.confidence or 70
    if current_confidence <= 1:
        current_confidence = current_confidence * 100
    new_confidence = min(95, current_confidence + 5)
    
    existing_tags = item.tags or ''
    new_tags = generate_dikw_tags(new_content, next_level, existing_tags)
    
    # Create promoted item
    new_item = repo.create({
        "level": next_level,
        "content": new_content,
        "summary": new_summary,
        "source_type": "synthesis",
        "original_signal_type": item.original_signal_type,
        "meeting_id": item.meeting_id,
        "confidence": new_confidence,
        "validation_count": (item.validation_count or 0) + 1,
        "tags": new_tags
    })
    
    new_id = new_item.id if new_item else None
    
    # Record evolution
    repo.record_evolution({
        "item_id": new_id,
        "action": "promoted",
        "previous_level": current_level,
        "new_level": next_level,
        "previous_content": item.content
    })
    
    # Update original item
    repo.update(item_id, {"status": "promoted"})
    
    return JSONResponse({
        "status": "ok", 
        "new_id": new_id, 
        "from_level": current_level, 
        "to_level": next_level,
        "content": new_content,
        "summary": new_summary,
        "tags": new_tags
    })


@router.post("/merge")
async def merge_dikw_items(request: Request):
    """Merge multiple items at the same level into a synthesized higher-level item."""
    from ....agents.dikw_synthesizer import merge_dikw_items_adapter
    
    repo = get_dikw_repository()
    data = await request.json()
    
    item_ids = data.get("item_ids", [])
    
    if len(item_ids) < 2:
        return JSONResponse({"error": "Need at least 2 items to merge"}, status_code=400)
    
    items = repo.get_by_ids(item_ids)
    
    if len(items) < 2:
        return JSONResponse({"error": "Items not found"}, status_code=404)
    
    # All items must be at same level
    levels = set(item.level for item in items)
    if len(levels) > 1:
        return JSONResponse({"error": "All items must be at the same level"}, status_code=400)
    
    current_level = items[0].level
    next_level = 'wisdom' if current_level == 'wisdom' else NEXT_LEVEL[current_level]
    
    combined_content = "\n\n".join([f"- {item.content}" for item in items])
    
    # AI merge synthesis
    try:
        items_for_adapter = [item.__dict__ for item in items]
        result = await merge_dikw_items_adapter(items_for_adapter)
        merged_summary = result.get('merged_content', '') or result.get('summary', '')
        if not merged_summary:
            merged_summary = f"Merged {len(items)} items"
    except Exception:
        merged_summary = f"Merged {len(items)} items"
    
    avg_confidence = sum(item.confidence or 50 for item in items) / len(items)
    total_validations = sum(item.validation_count or 0 for item in items)
    
    new_item = repo.create({
        "level": next_level,
        "content": combined_content,
        "summary": merged_summary,
        "source_type": "synthesis",
        "confidence": min(100, avg_confidence + 15),
        "validation_count": total_validations
    })
    
    new_id = new_item.id if new_item else None
    
    # Mark source items as merged
    for iid in item_ids:
        repo.update(iid, {"status": "merged"})
    
    return JSONResponse({
        "status": "ok",
        "new_id": new_id,
        "merged_count": len(items),
        "to_level": next_level,
        "summary": merged_summary
    })


@router.post("/validate")
async def validate_dikw_item(request: Request):
    """Validate/upvote a DIKW item (increases confidence)."""
    repo = get_dikw_repository()
    data = await request.json()
    
    item_id = data.get("item_id")
    action = data.get("action", "validate")
    
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    if action == "validate":
        repo.validate(item_id)
    elif action == "invalidate":
        item = repo.get_by_id(item_id)
        if item:
            new_count = max(0, (item.validation_count or 0) - 1)
            new_confidence = max(0, (item.confidence or 50) - 10)
            repo.update(item_id, {
                "validation_count": new_count,
                "confidence": new_confidence
            })
    elif action == "archive":
        repo.delete(item_id, soft=True)
    
    return JSONResponse({"status": "ok", "action": action})


@router.post("/ai-promote")
async def ai_promote_dikw(request: Request):
    """AI-assisted promotion suggestion."""
    from ....agents.dikw_synthesizer import ai_promote_dikw_adapter
    
    data = await request.json()
    content = data.get("content", "")
    from_level = data.get("from_level", "data")
    to_level = data.get("to_level") or NEXT_LEVEL.get(from_level, "information")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    try:
        result = await ai_promote_dikw_adapter(content, from_level, to_level)
        return JSONResponse({"status": "ok", **result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/normalize-categories")
async def normalize_dikw_categories():
    """Normalize signal types across DIKW items."""
    from .items import normalize_signal_type
    
    repo = get_dikw_repository()
    
    items = repo.get_items()
    
    updated_count = 0
    for item in items:
        if item.original_signal_type:
            normalized = normalize_signal_type(item.original_signal_type)
            if normalized != item.original_signal_type:
                repo.update(item.id, {"original_signal_type": normalized})
                updated_count += 1
    
    return JSONResponse({
        "status": "ok",
        "processed": len(items),
        "updated": updated_count
    })
