# src/app/api/v1/imports/mindmap.py
"""
API v1 - Mindmap screenshot ingestion with Vision AI.

Extracts structure, patterns, and insights from mindmap images.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import json
import logging
import base64

from ....infrastructure.supabase_client import get_supabase_client
from ....llm import analyze_image
from .models import MindmapNode, MindmapAnalysis, MindmapIngestResult

router = APIRouter()
logger = logging.getLogger(__name__)


MINDMAP_ANALYSIS_PROMPT = """Analyze this mindmap screenshot and extract its structure and meaning.

Return a JSON response with:
1. "root_topic": The central topic of the mindmap
2. "structure": Nested structure with {text, children, node_type} where node_type is 'root', 'category', 'item', or 'detail'
3. "entities": List of specific entities mentioned (people names, systems, tools, processes)
4. "relationships": List of relationships between entities as {from, to, type} where type could be 'collaborates_with', 'depends_on', 'owns', 'manages', etc.
5. "patterns": List of patterns you observe (e.g., "cross-functional collaboration", "technical migration", "stakeholder alignment")
6. "insights": List of 3-5 actionable insights derived from the mindmap structure and content
7. "dikw_candidates": List of items suitable for knowledge management with {content, level, category} where:
   - level is 'data', 'information', 'knowledge', or 'wisdom'
   - category is 'decision', 'process', 'relationship', 'insight', or 'principle'

Focus on extracting meaningful patterns and relationships, not just transcribing text.
The goal is to build intelligence from the visual structure.

Return ONLY valid JSON, no markdown formatting."""


def parse_mindmap_analysis(vision_response: str) -> dict:
    """
    Parse the vision API response into structured mindmap analysis.
    
    Handles both clean JSON and markdown-wrapped JSON.
    """
    # Try to extract JSON from response
    response = vision_response.strip()
    
    # Remove markdown code blocks if present
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    
    response = response.strip()
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse mindmap analysis as JSON: {e}")
        # Return a minimal structure
        return {
            "root_topic": "Unknown",
            "structure": {"text": "Parse error", "children": [], "node_type": "root"},
            "entities": [],
            "relationships": [],
            "patterns": [],
            "insights": [vision_response[:500]],  # Include raw response as insight
            "dikw_candidates": []
        }


def create_dikw_items_from_mindmap(supabase, meeting_id: int, analysis: dict) -> int:
    """
    Create DIKW items from mindmap analysis.
    
    Returns the count of items created.
    """
    created_count = 0
    candidates = analysis.get("dikw_candidates", [])
    
    for candidate in candidates:
        content = candidate.get("content", "")
        level = candidate.get("level", "information")
        category = candidate.get("category", "insight")
        
        if not content:
            continue
        
        # Validate level
        if level not in ['data', 'information', 'knowledge', 'wisdom']:
            level = 'information'
        
        try:
            supabase.table("dikw_items").insert({
                "level": level,
                "content": content,
                "source_type": "mindmap",
                "meeting_id": meeting_id,
                "tags": category,
                "confidence": 0.6,
                "status": "active"
            }).execute()
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create DIKW item: {e}")
    
    return created_count


@router.post("/mindmap/{meeting_id}")
async def ingest_mindmap(
    meeting_id: int,
    mindmap: UploadFile = File(...),
    source: str = Form("pocket")
):
    """
    F1c: Ingest a mindmap screenshot and extract structure/patterns.
    
    This endpoint:
    1. Uses GPT-4 Vision to analyze the mindmap screenshot
    2. Extracts hierarchical structure, entities, and relationships
    3. Identifies patterns and generates insights
    4. Creates DIKW items for knowledge building
    5. Stores the analysis linked to the meeting
    
    **Parameters:**
    - meeting_id: ID of the meeting to link the mindmap to
    - mindmap: Image file (PNG, JPG, JPEG, WEBP)
    - source: Source identifier (default: 'pocket')
    
    **Use case:**
    Pocket generates mindmaps that visually summarize meeting discussions.
    This endpoint extracts that visual intelligence for pattern recognition
    and knowledge graph building.
    """
    warnings = []
    
    # Validate file type
    if not mindmap.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_ext = mindmap.filename.split('.')[-1].lower() if '.' in mindmap.filename else ''
    allowed_image_types = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    
    if file_ext not in allowed_image_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: .{file_ext}. Allowed: {', '.join(allowed_image_types)}"
        )
    
    # Verify meeting exists
    supabase = get_supabase_client()
    
    meeting_result = supabase.table("meetings").select("id, meeting_name").eq("id", meeting_id).execute()
    if not meeting_result.data:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    
    meeting_name = meeting_result.data[0]['meeting_name']
    
    # Read and encode image
    try:
        image_bytes = await mindmap.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read image: {e}")
    
    # Analyze with vision API
    try:
        vision_response = analyze_image(image_base64, MINDMAP_ANALYSIS_PROMPT)
        analysis = parse_mindmap_analysis(vision_response)
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")
    
    # Store document and create DIKW items
    # Store mindmap as a document
    result = supabase.table("meeting_documents").insert({
        "meeting_id": meeting_id,
        "doc_type": "mindmap",
        "source": source,
        "content": f"[Mindmap Image: {mindmap.filename}]",
        "format": "image",
        "signals_json": None,
        "metadata_json": json.dumps({
            "filename": mindmap.filename,
            "file_size": len(image_bytes),
            "analysis": analysis
        }),
        "is_primary": 0
    }).execute()
    
    document_id = result.data[0]["id"] if result.data else None
    
    # Create DIKW items
    dikw_count = create_dikw_items_from_mindmap(supabase, meeting_id, analysis)
    
    logger.info(f"Ingested mindmap for meeting '{meeting_name}' (id={meeting_id}): "
                f"{len(analysis.get('insights', []))} insights, {dikw_count} DIKW items")
    
    # Build response
    try:
        mindmap_analysis = MindmapAnalysis(
            root_topic=analysis.get("root_topic", "Unknown"),
            structure=analysis.get("structure", {"text": "Unknown", "children": [], "node_type": "root"}),
            entities=analysis.get("entities", []),
            relationships=analysis.get("relationships", []),
            patterns=analysis.get("patterns", []),
            insights=analysis.get("insights", []),
            dikw_candidates=analysis.get("dikw_candidates", [])
        )
    except Exception as e:
        logger.warning(f"Failed to structure analysis response: {e}")
        mindmap_analysis = MindmapAnalysis(
            root_topic=analysis.get("root_topic", "Unknown"),
            structure={"text": "Parse error", "children": [], "node_type": "root"},
            entities=[],
            relationships=[],
            patterns=[],
            insights=analysis.get("insights", []),
            dikw_candidates=[]
        )
        warnings.append(f"Analysis structure incomplete: {str(e)}")
    
    return MindmapIngestResult(
        meeting_id=meeting_id,
        document_id=document_id,
        analysis=mindmap_analysis,
        dikw_items_created=dikw_count,
        warnings=warnings
    )


@router.get("/meetings/{meeting_id}/mindmaps")
async def list_meeting_mindmaps(meeting_id: int):
    """
    List all mindmap analyses linked to a meeting.
    """
    supabase = get_supabase_client()
    
    meeting = supabase.table("meetings").select("id").eq("id", meeting_id).execute()
    if not meeting.data:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    
    rows = supabase.table("meeting_documents").select(
        "id, source, metadata_json, created_at"
    ).eq("meeting_id", meeting_id).eq("doc_type", "mindmap").order(
        "created_at", desc=True
    ).execute()
    
    results = []
    for row in (rows.data or []):
        metadata = json.loads(row['metadata_json']) if row.get('metadata_json') else {}
        analysis = metadata.get('analysis', {})
        
        results.append({
            "id": row['id'],
            "source": row['source'],
            "filename": metadata.get('filename'),
            "root_topic": analysis.get('root_topic', 'Unknown'),
            "pattern_count": len(analysis.get('patterns', [])),
            "insight_count": len(analysis.get('insights', [])),
            "entity_count": len(analysis.get('entities', [])),
            "created_at": row['created_at']
        })
    
    return results
