# src/app/api/dikw.py
"""
DIKW (Data-Information-Knowledge-Wisdom) API Routes

Handles knowledge pyramid operations:
- CRUD for DIKW items
- Promotion between levels
- Merge and synthesis
- AI-assisted refinement
- Mindmap visualization
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dikw"])

# DIKW level constants
DIKW_LEVELS = ["data", "information", "knowledge", "wisdom"]
DIKW_NEXT_LEVEL = {
    "data": "information",
    "information": "knowledge", 
    "knowledge": "wisdom"
}


def _get_supabase():
    """Get Supabase client (lazy import for compatibility)."""
    from ..infrastructure.supabase_client import get_supabase_client
    return get_supabase_client()


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


# =============================================================================
# DIKW CRUD OPERATIONS
# =============================================================================

@router.get("/dikw")
async def get_dikw_items(level: str = None, status: str = "active"):
    """Get DIKW items, optionally filtered by level."""
    supabase = _get_supabase()
    
    query = supabase.table("dikw_items").select("*").eq("status", status)
    if level:
        query = query.eq("level", level)
    
    result = query.order("created_at", desc=True).execute()
    items = result.data or []
    
    # Get meeting names for items with meeting_id
    meeting_ids = [i["meeting_id"] for i in items if i.get("meeting_id")]
    meetings_map = {}
    if meeting_ids:
        meetings_result = supabase.table("meetings").select("id, meeting_name, meeting_date").in_("id", meeting_ids).execute()
        meetings_map = {m["id"]: m for m in meetings_result.data or []}
    
    # Group by level for pyramid view
    pyramid = {lvl: [] for lvl in DIKW_LEVELS}
    for item in items:
        item_dict = dict(item)
        if item.get("meeting_id") and item["meeting_id"] in meetings_map:
            item_dict["meeting_name"] = meetings_map[item["meeting_id"]].get("meeting_name")
            item_dict["meeting_date"] = meetings_map[item["meeting_id"]].get("meeting_date")
        if item_dict.get('original_signal_type'):
            item_dict['original_signal_type'] = normalize_signal_type(item_dict['original_signal_type'])
        pyramid[item['level']].append(item_dict)
    
    return JSONResponse({
        "pyramid": pyramid,
        "counts": {lvl: len(pyramid[lvl]) for lvl in DIKW_LEVELS}
    })


@router.post("/dikw")
async def create_dikw_item(request: Request):
    """Create a new DIKW item directly."""
    from ..agents.dikw_synthesizer import generate_dikw_tags
    
    supabase = _get_supabase()
    data = await request.json()
    
    level = data.get("level", "data")
    content = data.get("content", "")
    summary = data.get("summary", "")
    meeting_id = data.get("meeting_id")
    tags = data.get("tags") or generate_dikw_tags(content, level, "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    result = supabase.table("dikw_items").insert({
        "level": level,
        "content": content,
        "summary": summary or content[:200],
        "meeting_id": meeting_id,
        "source_type": "manual",
        "tags": tags,
        "validation_count": 1,
        "confidence": 70
    }).execute()
    
    return JSONResponse({
        "status": "ok", 
        "id": result.data[0]["id"] if result.data else None
    })


@router.put("/dikw/{item_id}")
async def update_dikw_item(item_id: int, request: Request):
    """Update an existing DIKW item."""
    from ..agents.dikw_synthesizer import generate_dikw_tags
    
    supabase = _get_supabase()
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
    
    result = supabase.table("dikw_items").update(update_data).eq("id", item_id).execute()
    
    if not result.data:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    return JSONResponse({"status": "ok", "item": result.data[0]})


@router.delete("/dikw/{item_id}")
async def delete_dikw_item(item_id: int):
    """Delete a DIKW item (soft delete - sets status to archived)."""
    supabase = _get_supabase()
    
    result = supabase.table("dikw_items").update({
        "status": "archived"
    }).eq("id", item_id).execute()
    
    return JSONResponse({"status": "ok"})


@router.get("/dikw/{item_id}/history")
async def get_dikw_item_history(item_id: int):
    """Get evolution history for a DIKW item."""
    supabase = _get_supabase()
    
    result = supabase.table("dikw_evolution").select("*").eq("item_id", item_id).order("created_at", desc=True).execute()
    
    return JSONResponse({
        "status": "ok",
        "history": result.data or []
    })


# =============================================================================
# PROMOTION & SYNTHESIS OPERATIONS
# =============================================================================

@router.post("/dikw/promote-signal")
async def promote_signal_to_dikw(request: Request):
    """Promote a signal to the DIKW pyramid (starts as Data level)."""
    from ..agents.dikw_synthesizer import ai_summarize_dikw_adapter, generate_dikw_tags
    
    supabase = _get_supabase()
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
    
    result = supabase.table("dikw_items").insert({
        "level": target_level,
        "content": signal_text,
        "summary": summary,
        "source_type": "signal",
        "original_signal_type": signal_type,
        "meeting_id": meeting_id,
        "validation_count": 1,
        "tags": tags
    }).execute()
    
    item_id = result.data[0]["id"] if result.data else None
    
    # Mark signal as promoted
    if meeting_id and signal_type and signal_text:
        supabase.table("signal_status").upsert({
            "meeting_id": meeting_id,
            "signal_type": signal_type,
            "signal_text": signal_text,
            "status": "approved",
            "converted_to": "dikw",
            "converted_ref_id": item_id
        }, on_conflict="meeting_id,signal_type,signal_text").execute()
    
    return JSONResponse({"status": "ok", "id": item_id, "level": target_level, "tags": tags})


@router.post("/dikw/promote")
async def promote_dikw_item(request: Request):
    """Promote a DIKW item to the next level (with AI synthesis)."""
    from ..agents.dikw_synthesizer import ai_promote_dikw_adapter, generate_dikw_tags
    
    supabase = _get_supabase()
    data = await request.json()
    
    item_id = data.get("item_id")
    to_level = data.get("to_level")
    promoted_content = data.get("promoted_content")
    provided_summary = data.get("summary")
    
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    item_result = supabase.table("dikw_items").select("*").eq("id", item_id).execute()
    
    if not item_result.data:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    item = item_result.data[0]
    current_level = item['level']
    
    if current_level == 'wisdom' and not to_level:
        return JSONResponse({"error": "Already at highest level"}, status_code=400)
    
    next_level = to_level if to_level else DIKW_NEXT_LEVEL.get(current_level, 'wisdom')
    new_content = promoted_content if promoted_content else item['content']
    
    # Generate AI synthesis
    if provided_summary:
        new_summary = provided_summary
    else:
        try:
            result = await ai_promote_dikw_adapter(new_content, current_level, next_level)
            new_summary = result.get('summary', f"Promoted from {current_level}: {item.get('summary') or ''}")
        except Exception:
            new_summary = f"Promoted from {current_level}: {item.get('summary') or ''}"
    
    # Normalize confidence
    current_confidence = item.get('confidence') or 70
    if current_confidence <= 1:
        current_confidence = current_confidence * 100
    new_confidence = min(95, current_confidence + 5)
    
    existing_tags = item.get('tags') or ''
    new_tags = generate_dikw_tags(new_content, next_level, existing_tags)
    
    # Create promoted item
    new_item_result = supabase.table("dikw_items").insert({
        "level": next_level,
        "content": new_content,
        "summary": new_summary,
        "source_type": "synthesis",
        "source_ref_ids": json.dumps([item_id]),
        "original_signal_type": item.get('original_signal_type'),
        "meeting_id": item.get('meeting_id'),
        "confidence": new_confidence,
        "validation_count": (item.get('validation_count') or 0) + 1,
        "tags": new_tags
    }).execute()
    
    new_id = new_item_result.data[0]["id"] if new_item_result.data else None
    
    # Record evolution
    supabase.table("dikw_evolution").insert({
        "item_id": new_id,
        "event_type": "promoted",
        "from_level": current_level,
        "to_level": next_level,
        "source_item_ids": json.dumps([item_id]),
        "content_snapshot": item['content']
    }).execute()
    
    # Update original item
    supabase.table("dikw_items").update({
        "promoted_to": new_id,
        "promoted_at": datetime.now().isoformat()
    }).eq("id", item_id).execute()
    
    return JSONResponse({
        "status": "ok", 
        "new_id": new_id, 
        "from_level": current_level, 
        "to_level": next_level,
        "content": new_content,
        "summary": new_summary,
        "tags": new_tags
    })


@router.post("/dikw/merge")
async def merge_dikw_items(request: Request):
    """Merge multiple items at the same level into a synthesized higher-level item."""
    from ..agents.dikw_synthesizer import merge_dikw_items_adapter
    
    supabase = _get_supabase()
    data = await request.json()
    
    item_ids = data.get("item_ids", [])
    
    if len(item_ids) < 2:
        return JSONResponse({"error": "Need at least 2 items to merge"}, status_code=400)
    
    items_result = supabase.table("dikw_items").select("*").in_("id", item_ids).execute()
    items = items_result.data or []
    
    if len(items) < 2:
        return JSONResponse({"error": "Items not found"}, status_code=404)
    
    # All items must be at same level
    levels = set(item['level'] for item in items)
    if len(levels) > 1:
        return JSONResponse({"error": "All items must be at the same level"}, status_code=400)
    
    current_level = items[0]['level']
    next_level = 'wisdom' if current_level == 'wisdom' else DIKW_NEXT_LEVEL[current_level]
    
    combined_content = "\n\n".join([f"- {item['content']}" for item in items])
    
    # AI merge synthesis
    try:
        items_for_adapter = [dict(item) for item in items]
        result = await merge_dikw_items_adapter(items_for_adapter)
        merged_summary = result.get('merged_content', '') or result.get('summary', '')
        if not merged_summary:
            merged_summary = f"Merged {len(items)} items: " + "; ".join([i.get('summary', '')[:50] for i in items if i.get('summary')])
    except Exception:
        merged_summary = f"Merged {len(items)} items: " + "; ".join([i.get('summary', '')[:50] for i in items if i.get('summary')])
    
    avg_confidence = sum(item.get('confidence') or 0.5 for item in items) / len(items)
    total_validations = sum(item.get('validation_count') or 0 for item in items)
    
    new_item_result = supabase.table("dikw_items").insert({
        "level": next_level,
        "content": combined_content,
        "summary": merged_summary,
        "source_type": "synthesis",
        "source_ref_ids": json.dumps(item_ids),
        "confidence": min(1.0, avg_confidence + 0.15),
        "validation_count": total_validations
    }).execute()
    
    new_id = new_item_result.data[0]["id"] if new_item_result.data else None
    
    # Mark source items as merged
    for item_id in item_ids:
        supabase.table("dikw_items").update({
            "status": "merged",
            "promoted_to": new_id,
            "promoted_at": datetime.now().isoformat()
        }).eq("id", item_id).execute()
    
    return JSONResponse({
        "status": "ok",
        "new_id": new_id,
        "merged_count": len(items),
        "to_level": next_level,
        "summary": merged_summary
    })


@router.post("/dikw/validate")
async def validate_dikw_item(request: Request):
    """Validate/upvote a DIKW item (increases confidence)."""
    supabase = _get_supabase()
    data = await request.json()
    
    item_id = data.get("item_id")
    action = data.get("action", "validate")  # 'validate' | 'invalidate' | 'archive'
    
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    item_result = supabase.table("dikw_items").select("validation_count, confidence").eq("id", item_id).execute()
    
    if action == "validate":
        current = item_result.data[0] if item_result.data else {"validation_count": 0, "confidence": 0.5}
        supabase.table("dikw_items").update({
            "validation_count": (current.get("validation_count") or 0) + 1,
            "confidence": min(1.0, (current.get("confidence") or 0.5) + 0.1)
        }).eq("id", item_id).execute()
    elif action == "invalidate":
        current = item_result.data[0] if item_result.data else {"validation_count": 0, "confidence": 0.5}
        supabase.table("dikw_items").update({
            "validation_count": max(0, (current.get("validation_count") or 0) - 1),
            "confidence": max(0.0, (current.get("confidence") or 0.5) - 0.1)
        }).eq("id", item_id).execute()
    elif action == "archive":
        supabase.table("dikw_items").update({
            "status": "archived"
        }).eq("id", item_id).execute()
    
    return JSONResponse({"status": "ok", "action": action})


@router.post("/dikw/generate-tags")
async def generate_tags_endpoint(request: Request):
    """Generate tags for DIKW content."""
    from ..agents.dikw_synthesizer import generate_dikw_tags
    
    data = await request.json()
    content = data.get("content", "")
    level = data.get("level", "data")
    existing_tags = data.get("existing_tags", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    tags = generate_dikw_tags(content, level, existing_tags)
    return JSONResponse({"status": "ok", "tags": tags})


# =============================================================================
# AI-ASSISTED OPERATIONS
# =============================================================================

@router.post("/dikw/ai-review")
async def ai_review_dikw(request: Request):
    """AI review of a DIKW item with suggestions."""
    from ..llm import ask as ask_llm
    
    supabase = _get_supabase()
    data = await request.json()
    
    item_id = data.get("item_id")
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    item_result = supabase.table("dikw_items").select("*").eq("id", item_id).execute()
    if not item_result.data:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    item = item_result.data[0]
    
    prompt = f"""Review this DIKW knowledge item and suggest improvements:

Level: {item['level']}
Content: {item['content']}
Summary: {item.get('summary', 'N/A')}
Tags: {item.get('tags', 'N/A')}

Provide:
1. Quality assessment (1-10)
2. Suggested improvements to content clarity
3. Better summary if needed
4. Additional tags to add
5. Whether it's ready for promotion to next level"""

    try:
        review = await ask_llm(prompt)
        return JSONResponse({"status": "ok", "review": review})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/dikw/ai-refine")
async def ai_refine_dikw(request: Request):
    """AI refinement of DIKW item content."""
    from ..llm import ask as ask_llm
    
    supabase = _get_supabase()
    data = await request.json()
    
    item_id = data.get("item_id")
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    item_result = supabase.table("dikw_items").select("*").eq("id", item_id).execute()
    if not item_result.data:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    item = item_result.data[0]
    
    prompt = f"""Refine this {item['level']}-level knowledge item to be clearer and more actionable:

Original: {item['content']}

Provide a refined version that is:
- More concise and clear
- Actionable if applicable
- Properly contextualized

Just provide the refined text, no explanations."""

    try:
        refined = await ask_llm(prompt)
        return JSONResponse({"status": "ok", "refined_content": refined.strip()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/dikw/ai-summarize")
async def ai_summarize_dikw(request: Request):
    """AI summary generation for DIKW item."""
    from ..agents.dikw_synthesizer import ai_summarize_dikw_adapter
    
    data = await request.json()
    content = data.get("content", "")
    level = data.get("level", "data")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    try:
        summary = await ai_summarize_dikw_adapter(content, level)
        return JSONResponse({"status": "ok", "summary": summary})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/dikw/ai-promote")
async def ai_promote_dikw(request: Request):
    """AI-assisted promotion suggestion."""
    from ..agents.dikw_synthesizer import ai_promote_dikw_adapter
    
    data = await request.json()
    content = data.get("content", "")
    from_level = data.get("from_level", "data")
    to_level = data.get("to_level") or DIKW_NEXT_LEVEL.get(from_level, "information")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    try:
        result = await ai_promote_dikw_adapter(content, from_level, to_level)
        return JSONResponse({"status": "ok", **result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

@router.post("/dikw/backfill-tags")
async def backfill_dikw_tags():
    """Backfill tags for all DIKW items without tags."""
    from ..agents.dikw_synthesizer import generate_dikw_tags
    
    supabase = _get_supabase()
    
    # Get items without tags
    result = supabase.table("dikw_items").select("id, content, level, original_signal_type").is_("tags", "null").execute()
    items = result.data or []
    
    # Also get items with empty tags
    result2 = supabase.table("dikw_items").select("id, content, level, original_signal_type").eq("tags", "").execute()
    items.extend(result2.data or [])
    
    updated_count = 0
    for item in items:
        tags = generate_dikw_tags(
            item.get('content', ''), 
            item.get('level', 'data'),
            item.get('original_signal_type', '')
        )
        if tags:
            supabase.table("dikw_items").update({"tags": tags}).eq("id", item['id']).execute()
            updated_count += 1
    
    return JSONResponse({
        "status": "ok",
        "processed": len(items),
        "updated": updated_count
    })


@router.post("/dikw/normalize-categories")
async def normalize_dikw_categories():
    """Normalize signal types across DIKW items."""
    supabase = _get_supabase()
    
    result = supabase.table("dikw_items").select("id, original_signal_type").execute()
    items = result.data or []
    
    updated_count = 0
    for item in items:
        if item.get('original_signal_type'):
            normalized = normalize_signal_type(item['original_signal_type'])
            if normalized != item['original_signal_type']:
                supabase.table("dikw_items").update({
                    "original_signal_type": normalized
                }).eq("id", item['id']).execute()
                updated_count += 1
    
    return JSONResponse({
        "status": "ok",
        "processed": len(items),
        "updated": updated_count
    })
