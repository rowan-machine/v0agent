# src/app/api/mindmap.py
"""
Mindmap Visualization API Routes

Handles mindmap operations:
- DIKW visualization data
- Hierarchical mindmap data
- Tag clusters
- Mindmap synthesis
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mindmap", tags=["mindmap"])

# DIKW level constants
DIKW_LEVELS = ["data", "information", "knowledge", "wisdom"]


def _get_supabase():
    """Get Supabase client (lazy import for compatibility)."""
    from ..db_supabase import supabase
    return supabase


@router.get("/data")
async def get_mindmap_data():
    """Get mindmap data for visualization.
    
    Returns both DIKW pyramid structure and hierarchical mindmaps from conversations.
    """
    supabase = _get_supabase()
    
    # Get DIKW items from Supabase
    items_result = supabase.table("dikw_items").select("*").eq("status", "active").order("created_at", desc=True).execute()
    items = items_result.data or []
    
    # Get hierarchical mindmaps from conversations
    mindmaps_result = supabase.table("conversation_mindmaps").select(
        "id, conversation_id, mindmap_json, hierarchy_levels, node_count, root_node_id"
    ).order("updated_at", desc=True).limit(5).execute()
    mindmaps = mindmaps_result.data or []
    
    # Build DIKW tree structure for mindmap
    tree = {
        "name": "Knowledge",
        "type": "root",
        "children": []
    }
    
    # Group by level
    levels = {level: [] for level in DIKW_LEVELS}
    for item in items:
        levels[item['level']].append(dict(item))
    
    # Build hierarchical tree structure
    for level in DIKW_LEVELS:
        level_node = {
            "name": level.capitalize(),
            "type": "level",
            "level": level,
            "children": []
        }
        for item in levels[level][:20]:  # Limit per level
            level_node["children"].append({
                "id": item['id'],
                "name": (item['content'] or '')[:40] + ('...' if len(item.get('content', '')) > 40 else ''),
                "type": "item",
                "level": level,
                "summary": item.get('summary', ''),
                "tags": item.get('tags', '')
            })
        tree["children"].append(level_node)
    
    # Build flat nodes and links for force graph
    nodes = [{"id": "root", "name": "Knowledge", "type": "root", "level": "root"}]
    links = []
    
    for level in DIKW_LEVELS:
        level_id = f"level_{level}"
        nodes.append({"id": level_id, "name": level.capitalize(), "type": "level", "level": level})
        links.append({"source": "root", "target": level_id})
        
        for item in levels[level][:15]:
            item_id = f"item_{item['id']}"
            nodes.append({
                "id": item_id,
                "name": (item['content'] or '')[:30] + ('...' if len(item['content'] or '') > 30 else ''),
                "type": "item",
                "level": level,
                "summary": item.get('summary', '') if 'summary' in item else ''
            })
            links.append({"source": level_id, "target": item_id})
    
    # Add hierarchical mindmap nodes
    hierarchical_mindmaps = []
    for mindmap in mindmaps:
        try:
            mindmap_json = json.loads(mindmap['mindmap_json'])
            hierarchical_mindmaps.append({
                "id": mindmap['id'],
                "conversation_id": mindmap['conversation_id'],
                "hierarchy_levels": mindmap['hierarchy_levels'],
                "node_count": mindmap['node_count'],
                "root_node_id": mindmap['root_node_id'],
                "nodes": mindmap_json.get('nodes', []),
                "edges": mindmap_json.get('edges', [])
            })
        except Exception as e:
            logger.warning(f"Error processing mindmap {mindmap['id']}: {e}")
    
    # Build tag clusters
    tag_clusters = {}
    for item in items:
        tags = (item['tags'] or '').split(',') if item['tags'] else []
        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                if tag not in tag_clusters:
                    tag_clusters[tag] = []
                tag_clusters[tag].append({
                    "id": item['id'],
                    "level": item['level'],
                    "content": (item['content'] or '')[:50]
                })
    
    # Count stats
    counts = {
        "data": len(levels['data']),
        "information": len(levels['information']),
        "knowledge": len(levels['knowledge']),
        "wisdom": len(levels['wisdom']),
        "tags": len(tag_clusters),
        "connections": len(links),
        "hierarchical_mindmaps": len(hierarchical_mindmaps),
        "total_mindmap_nodes": sum(m.get('node_count', 0) for m in hierarchical_mindmaps)
    }
    
    return JSONResponse({
        "tree": tree,
        "nodes": nodes,
        "links": links,
        "tagClusters": tag_clusters,
        "hierarchicalMindmaps": hierarchical_mindmaps,
        "counts": counts
    })


@router.get("/data-hierarchical")
async def get_mindmap_data_hierarchical():
    """Get all hierarchical mindmaps with full hierarchy information."""
    from ..services.mindmap_synthesis import MindmapSynthesizer
    
    supabase = _get_supabase()
    
    mindmaps_result = supabase.table("conversation_mindmaps").select(
        "id, conversation_id, mindmap_json, hierarchy_levels, node_count, root_node_id, created_at, updated_at"
    ).order("updated_at", desc=True).execute()
    mindmaps = mindmaps_result.data or []
    
    hierarchical_data = []
    for mindmap in mindmaps:
        try:
            mindmap_json = json.loads(mindmap['mindmap_json'])
            hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_json)
            
            enhanced_nodes = []
            for node in mindmap_json.get('nodes', []):
                enhanced_node = dict(node)
                enhanced_node['conversation_id'] = mindmap['conversation_id']
                enhanced_node['mindmap_id'] = mindmap['id']
                enhanced_node['level'] = node.get('level', 0)
                enhanced_nodes.append(enhanced_node)
            
            hierarchical_data.append({
                "id": mindmap['id'],
                "conversation_id": mindmap['conversation_id'],
                "nodes": enhanced_nodes,
                "edges": mindmap_json.get('edges', []),
                "hierarchy": {
                    "levels": hierarchy.get('levels'),
                    "max_depth": hierarchy.get('max_depth'),
                    "root_id": hierarchy.get('root_id')
                },
                "created_at": mindmap['created_at'],
                "updated_at": mindmap['updated_at']
            })
        except Exception as e:
            logger.warning(f"Error processing hierarchical mindmap {mindmap['id']}: {e}")
    
    return JSONResponse({
        "mindmaps": hierarchical_data,
        "count": len(hierarchical_data)
    })


@router.get("/nodes-by-level/{level}")
async def get_mindmap_nodes_by_level(level: int):
    """Get all mindmap nodes at a specific hierarchy level."""
    supabase = _get_supabase()
    
    mindmaps_result = supabase.table("conversation_mindmaps").select("mindmap_json").execute()
    mindmaps = mindmaps_result.data or []
    
    nodes_at_level = []
    for mindmap in mindmaps:
        try:
            mindmap_json = json.loads(mindmap['mindmap_json'])
            for node in mindmap_json.get('nodes', []):
                if node.get('level') == level:
                    nodes_at_level.append(node)
        except Exception:
            pass
    
    return JSONResponse({
        "level": level,
        "nodes": nodes_at_level,
        "count": len(nodes_at_level)
    })


@router.get("/conversations")
async def get_aggregated_conversation_mindmaps():
    """Get aggregated view of all conversation mindmaps."""
    supabase = _get_supabase()
    
    mindmaps_result = supabase.table("conversation_mindmaps").select(
        "id, conversation_id, hierarchy_levels, node_count, root_node_id, created_at"
    ).order("created_at", desc=True).execute()
    mindmaps = mindmaps_result.data or []
    
    # Get conversation titles
    conv_ids = [m['conversation_id'] for m in mindmaps if m.get('conversation_id')]
    conversations_map = {}
    if conv_ids:
        convs_result = supabase.table("conversations").select("id, title").in_("id", conv_ids).execute()
        conversations_map = {c['id']: c.get('title', 'Untitled') for c in convs_result.data or []}
    
    # Enrich mindmap data
    enriched = []
    for mindmap in mindmaps:
        enriched.append({
            **mindmap,
            "conversation_title": conversations_map.get(mindmap['conversation_id'], 'Untitled')
        })
    
    return JSONResponse({
        "mindmaps": enriched,
        "total_conversations": len(set(m['conversation_id'] for m in mindmaps if m.get('conversation_id'))),
        "total_nodes": sum(m.get('node_count', 0) for m in mindmaps)
    })


@router.post("/synthesize")
async def synthesize_mindmaps(request: Request):
    """Synthesize mindmaps from a conversation."""
    from ..services.mindmap_synthesis import MindmapSynthesizer
    
    supabase = _get_supabase()
    data = await request.json()
    
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return JSONResponse({"error": "conversation_id is required"}, status_code=400)
    
    # Get conversation messages
    messages_result = supabase.table("messages").select("*").eq(
        "conversation_id", conversation_id
    ).order("created_at").execute()
    messages = messages_result.data or []
    
    if not messages:
        return JSONResponse({"error": "No messages found for conversation"}, status_code=404)
    
    # Synthesize mindmap
    try:
        synthesizer = MindmapSynthesizer()
        mindmap = await synthesizer.synthesize_from_messages(messages)
        
        # Store the mindmap
        result = supabase.table("conversation_mindmaps").upsert({
            "conversation_id": conversation_id,
            "mindmap_json": json.dumps(mindmap),
            "hierarchy_levels": mindmap.get('max_depth', 3),
            "node_count": len(mindmap.get('nodes', [])),
            "root_node_id": mindmap.get('root_id')
        }, on_conflict="conversation_id").execute()
        
        return JSONResponse({
            "status": "ok",
            "mindmap_id": result.data[0]['id'] if result.data else None,
            "node_count": len(mindmap.get('nodes', [])),
            "hierarchy_levels": mindmap.get('max_depth', 3)
        })
    except Exception as e:
        logger.error(f"Error synthesizing mindmap: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/synthesis")
async def get_mindmap_synthesis(type: str = None):
    """Get mindmap synthesis results."""
    supabase = _get_supabase()
    
    query = supabase.table("mindmap_syntheses").select("*")
    if type:
        query = query.eq("synthesis_type", type)
    
    result = query.order("created_at", desc=True).limit(20).execute()
    
    return JSONResponse({
        "syntheses": result.data or [],
        "count": len(result.data or [])
    })


@router.post("/synthesize-all")
async def generate_all_syntheses(force: str = "false"):
    """Generate syntheses for all conversations without mindmaps."""
    from ..services.mindmap_synthesis import MindmapSynthesizer
    
    supabase = _get_supabase()
    
    # Get conversations without mindmaps (or all if force)
    if force.lower() == "true":
        convs_result = supabase.table("conversations").select("id").execute()
    else:
        existing_result = supabase.table("conversation_mindmaps").select("conversation_id").execute()
        existing_ids = [m['conversation_id'] for m in existing_result.data or []]
        
        convs_result = supabase.table("conversations").select("id").execute()
        convs_result.data = [c for c in (convs_result.data or []) if c['id'] not in existing_ids]
    
    conversations = convs_result.data or []
    
    synthesized_count = 0
    errors = []
    
    synthesizer = MindmapSynthesizer()
    for conv in conversations[:10]:  # Limit to 10 at a time
        try:
            messages_result = supabase.table("messages").select("*").eq(
                "conversation_id", conv['id']
            ).order("created_at").execute()
            messages = messages_result.data or []
            
            if len(messages) >= 3:  # Only synthesize conversations with 3+ messages
                mindmap = await synthesizer.synthesize_from_messages(messages)
                
                supabase.table("conversation_mindmaps").upsert({
                    "conversation_id": conv['id'],
                    "mindmap_json": json.dumps(mindmap),
                    "hierarchy_levels": mindmap.get('max_depth', 3),
                    "node_count": len(mindmap.get('nodes', [])),
                    "root_node_id": mindmap.get('root_id')
                }, on_conflict="conversation_id").execute()
                
                synthesized_count += 1
        except Exception as e:
            errors.append({"conversation_id": conv['id'], "error": str(e)})
    
    return JSONResponse({
        "status": "ok",
        "synthesized": synthesized_count,
        "errors": errors[:5]  # Limit error output
    })


@router.post("/generate")
async def generate_mindmap(request: Request):
    """Generate a mindmap from arbitrary text content."""
    from ..llm import ask as ask_llm
    
    data = await request.json()
    content = data.get("content", "")
    
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)
    
    prompt = f"""Analyze this content and generate a hierarchical mindmap structure in JSON format:

Content: {content[:2000]}

Return a JSON object with:
- nodes: array of {{id, label, level, type}}
- edges: array of {{source, target}}
- root_id: the root node id
- max_depth: maximum hierarchy depth

Keep it focused on key concepts and relationships."""

    try:
        result = await ask_llm(prompt)
        # Try to parse as JSON
        try:
            mindmap = json.loads(result)
        except:
            mindmap = {"nodes": [], "edges": [], "raw": result}
        
        return JSONResponse({"status": "ok", "mindmap": mindmap})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/tags")
async def get_mindmap_tags():
    """Get all unique tags with counts from DIKW items."""
    supabase = _get_supabase()
    
    result = supabase.table("dikw_items").select("tags").eq("status", "active").execute()
    items = result.data or []
    
    tag_counts = {}
    for item in items:
        tags = (item['tags'] or '').split(',')
        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Sort by count
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    
    return JSONResponse({
        "tags": [{"name": t[0], "count": t[1]} for t in sorted_tags],
        "total_unique": len(tag_counts)
    })


@router.get("/status")
async def get_mindmap_status():
    """Get overall mindmap system status."""
    supabase = _get_supabase()
    
    dikw_count = supabase.table("dikw_items").select("id", count="exact").eq("status", "active").execute()
    mindmap_count = supabase.table("conversation_mindmaps").select("id", count="exact").execute()
    
    return JSONResponse({
        "dikw_items": dikw_count.count or 0,
        "conversation_mindmaps": mindmap_count.count or 0,
        "status": "healthy"
    })
