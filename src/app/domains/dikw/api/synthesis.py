# src/app/domains/dikw/api/synthesis.py
"""
DIKW Synthesis API

AI-assisted operations for synthesizing and refining knowledge.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

from ....repositories import get_dikw_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/synthesis")


@router.post("/ai-review")
async def ai_review_dikw(request: Request):
    """AI review of a DIKW item with suggestions."""
    from ....llm import ask as ask_llm
    
    repo = get_dikw_repository()
    data = await request.json()
    
    item_id = data.get("item_id")
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    item = repo.get_by_id(item_id)
    if not item:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    prompt = f"""Review this DIKW knowledge item and suggest improvements:

Level: {item.level}
Content: {item.content}
Summary: {item.summary or 'N/A'}
Tags: {item.tags or 'N/A'}

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


@router.post("/ai-refine")
async def ai_refine_dikw(request: Request):
    """AI refinement of DIKW item content."""
    from ....llm import ask as ask_llm
    
    repo = get_dikw_repository()
    data = await request.json()
    
    item_id = data.get("item_id")
    if not item_id:
        return JSONResponse({"error": "Item ID is required"}, status_code=400)
    
    item = repo.get_by_id(item_id)
    if not item:
        return JSONResponse({"error": "Item not found"}, status_code=404)
    
    prompt = f"""Refine this {item.level}-level knowledge item to be clearer and more actionable:

Original: {item.content}

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


@router.post("/ai-summarize")
async def ai_summarize_dikw(request: Request):
    """AI summary generation for DIKW item."""
    from ....agents.dikw_synthesizer import ai_summarize_dikw_adapter
    
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


@router.post("/generate-tags")
async def generate_tags_endpoint(request: Request):
    """Generate tags for DIKW content."""
    from ....agents.dikw_synthesizer import generate_dikw_tags
    
    data = await request.json()
    content = data.get("content", "")
    level = data.get("level", "data")
    existing_tags = data.get("existing_tags", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    tags = generate_dikw_tags(content, level, existing_tags)
    return JSONResponse({"status": "ok", "tags": tags})


@router.post("/backfill-tags")
async def backfill_dikw_tags():
    """Backfill tags for all DIKW items without tags."""
    from ....agents.dikw_synthesizer import generate_dikw_tags
    
    repo = get_dikw_repository()
    
    # Get items without tags
    items_no_tags = repo.get_items_without_tags()
    
    updated_count = 0
    for item in items_no_tags:
        tags = generate_dikw_tags(
            item.content or '', 
            item.level or 'data',
            item.original_signal_type or ''
        )
        if tags:
            repo.update_tags(item.id, tags)
            updated_count += 1
    
    return JSONResponse({
        "status": "ok",
        "processed": len(items_no_tags),
        "updated": updated_count
    })
