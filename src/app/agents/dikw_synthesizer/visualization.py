# src/app/agents/dikw_synthesizer/visualization.py
"""
DIKW Visualization Utilities

Functions for building mindmap, graph, and tag cluster visualizations.
"""

from typing import Any, Dict, List, Tuple

from .constants import DIKW_LEVELS


def build_mindmap_tree(items: List[Dict]) -> Dict[str, Any]:
    """Build hierarchical tree structure for mindmap visualization."""
    tree = {
        "name": "Knowledge",
        "type": "root",
        "children": []
    }
    
    # Group by level
    levels = {level: [] for level in DIKW_LEVELS}
    for item in items:
        level = item.get('level', 'data')
        if level in levels:
            levels[level].append(item)
    
    # Build tree
    for level in DIKW_LEVELS:
        level_node = {
            "name": level.capitalize(),
            "type": "level",
            "level": level,
            "children": []
        }
        for item in levels[level][:20]:  # Limit per level
            content = item.get('content', '')
            level_node["children"].append({
                "id": item.get('id'),
                "name": content[:40] + ('...' if len(content) > 40 else ''),
                "type": "item",
                "level": level,
                "summary": item.get('summary', ''),
                "tags": item.get('tags', '')
            })
        tree["children"].append(level_node)
    
    return tree


def build_graph_data(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Build nodes and links for force-directed graph visualization."""
    nodes = [{"id": "root", "name": "Knowledge", "type": "root", "level": "root"}]
    links = []
    
    # Group by level
    levels = {level: [] for level in DIKW_LEVELS}
    for item in items:
        level = item.get('level', 'data')
        if level in levels:
            levels[level].append(item)
    
    for level in DIKW_LEVELS:
        level_id = f"level_{level}"
        nodes.append({
            "id": level_id, 
            "name": level.capitalize(), 
            "type": "level", 
            "level": level
        })
        links.append({"source": "root", "target": level_id})
        
        for item in levels[level][:15]:
            item_id = f"item_{item.get('id')}"
            content = item.get('content', '')
            nodes.append({
                "id": item_id,
                "name": content[:30] + ('...' if len(content) > 30 else ''),
                "type": "item",
                "level": level,
                "summary": item.get('summary', '')
            })
            links.append({"source": level_id, "target": item_id})
    
    return nodes, links


def build_tag_clusters(items: List[Dict]) -> Dict[str, List[Dict]]:
    """Build tag clusters from items."""
    tag_clusters = {}
    for item in items:
        tags = (item.get('tags') or '').split(',') if item.get('tags') else []
        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                if tag not in tag_clusters:
                    tag_clusters[tag] = []
                tag_clusters[tag].append({
                    "id": item.get('id'),
                    "level": item.get('level'),
                    "content": (item.get('content') or '')[:50]
                })
    return tag_clusters


def get_mindmap_data(items: List[Dict]) -> Dict[str, Any]:
    """
    Get complete mindmap visualization data.
    
    Returns:
        Dict with tree, nodes, links, tagClusters, and counts
    """
    tree = build_mindmap_tree(items)
    nodes, links = build_graph_data(items)
    tag_clusters = build_tag_clusters(items)
    
    # Count stats
    levels = {level: [] for level in DIKW_LEVELS}
    for item in items:
        level = item.get('level', 'data')
        if level in levels:
            levels[level].append(item)
    
    counts = {
        "data": len(levels['data']),
        "information": len(levels['information']),
        "knowledge": len(levels['knowledge']),
        "wisdom": len(levels['wisdom']),
        "tags": len(tag_clusters),
        "connections": len(links)
    }
    
    return {
        "tree": tree,
        "nodes": nodes,
        "links": links,
        "tagClusters": tag_clusters,
        "counts": counts
    }


__all__ = [
    "build_mindmap_tree",
    "build_graph_data",
    "build_tag_clusters",
    "get_mindmap_data",
]
