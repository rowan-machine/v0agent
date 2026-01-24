"""
Mindmap Synthesis Service

Aggregates mindmap data from all conversations and generates AI-powered
synthesis with hierarchy preservation for knowledge graph integration.
"""

import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
import sqlite3

from ..db import connect
from ..llm import ask as ask_llm

logger = logging.getLogger(__name__)


class MindmapSynthesizer:
    """Synthesize mindmap data from conversations."""
    
    @staticmethod
    def extract_hierarchy_from_mindmap(mindmap_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract hierarchy information from mindmap structure.
        
        Returns:
            {
                'levels': 3,
                'root_node': {...},
                'nodes_by_level': {0: [...], 1: [...], 2: [...]},
                'node_count': 15
            }
        """
        nodes = mindmap_data.get('nodes', [])
        if not nodes:
            return {'levels': 0, 'root_node': None, 'nodes_by_level': {}, 'node_count': 0}
        
        # Build level map based on node hierarchy
        nodes_by_level = {}
        root_node = None
        max_level = 0
        
        for node in nodes:
            level = node.get('level', 0)
            
            # Track maximum level
            if level > max_level:
                max_level = level
            
            # Group by level
            if level not in nodes_by_level:
                nodes_by_level[level] = []
            nodes_by_level[level].append(node)
            
            # Find root
            if level == 0 and node.get('parent_id') is None:
                root_node = node
        
        return {
            'levels': max_level + 1,
            'root_node': root_node,
            'nodes_by_level': nodes_by_level,
            'node_count': len(nodes),
            'max_depth': max_level
        }
    
    @staticmethod
    def store_conversation_mindmap(
        conversation_id: int,
        mindmap_data: Dict[str, Any]
    ) -> Optional[int]:
        """Store mindmap data from a conversation.
        
        Args:
            conversation_id: ID of the conversation
            mindmap_data: Raw mindmap structure with nodes and edges
            
        Returns:
            ID of the stored mindmap or None on error
        """
        try:
            hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_data)
            root_node_id = hierarchy.get('root_node', {}).get('id')
            
            with connect() as conn:
                conn.execute("""
                    INSERT INTO conversation_mindmaps 
                    (conversation_id, mindmap_json, hierarchy_levels, root_node_id, node_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    conversation_id,
                    json.dumps(mindmap_data),
                    hierarchy.get('levels', 0),
                    root_node_id,
                    hierarchy.get('node_count', 0)
                ))
                conn.commit()
                return conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        except Exception as e:
            logger.error(f"Error storing conversation mindmap: {e}")
            return None
    
    @staticmethod
    def get_all_mindmaps() -> List[Dict[str, Any]]:
        """Get all stored mindmaps with hierarchy information.
        
        Returns:
            List of mindmaps with metadata and hierarchy info
        """
        with connect() as conn:
            mindmaps = conn.execute("""
                SELECT id, conversation_id, mindmap_json, hierarchy_levels, 
                       node_count, root_node_id, created_at
                FROM conversation_mindmaps
                ORDER BY updated_at DESC
            """).fetchall()
        
        return [dict(m) for m in mindmaps]
    
    @staticmethod
    def extract_key_topics_and_relationships(mindmap_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key topics and relationships from mindmap.
        
        Returns:
            {
                'key_topics': ['Topic 1', 'Topic 2', ...],
                'relationships': [
                    {'source': 'Topic 1', 'target': 'Topic 2', 'relationship': 'causes'}
                ],
                'themes': ['Theme A', 'Theme B']
            }
        """
        nodes = mindmap_data.get('nodes', [])
        edges = mindmap_data.get('edges', [])
        
        # Extract topics from top-level nodes
        key_topics = []
        for node in nodes:
            if node.get('level', 0) <= 1 and node.get('title'):
                key_topics.append(node['title'])
        
        # Extract relationships from edges
        relationships = []
        for edge in edges[:15]:  # Limit to top 15 relationships
            source_id = edge.get('source')
            target_id = edge.get('target')
            
            # Find node titles
            source_title = None
            target_title = None
            for node in nodes:
                if node.get('id') == source_id:
                    source_title = node.get('title')
                if node.get('id') == target_id:
                    target_title = node.get('title')
            
            if source_title and target_title:
                relationships.append({
                    'source': source_title,
                    'target': target_title,
                    'relationship': 'connects to'
                })
        
        # Infer themes from common topics
        themes = []
        if key_topics:
            # Take first 5 topics as themes
            themes = key_topics[:5]
        
        return {
            'key_topics': key_topics[:10],
            'relationships': relationships,
            'themes': themes
        }
    
    @staticmethod
    async def generate_synthesis(force: bool = False) -> Optional[int]:
        """Generate AI-powered synthesis of all mindmaps.
        
        This function:
        1. Collects all mindmaps from conversations
        2. Extracts hierarchy and key information
        3. Uses AI to synthesize into coherent knowledge structure
        4. Stores synthesis with metadata
        
        Args:
            force: Force regeneration even if recent synthesis exists
            
        Returns:
            ID of the generated synthesis or None on error
        """
        try:
            # Check if recent synthesis exists (within last hour)
            if not force:
                with connect() as conn:
                    recent = conn.execute("""
                        SELECT id FROM mindmap_syntheses
                        WHERE datetime(updated_at) > datetime('now', '-1 hour')
                        LIMIT 1
                    """).fetchone()
                    if recent:
                        logger.info("Recent synthesis exists, skipping generation")
                        return recent['id']
            
            # Get all mindmaps
            mindmaps = MindmapSynthesizer.get_all_mindmaps()
            if not mindmaps:
                logger.warning("No mindmaps to synthesize")
                return None
            
            # Extract information from all mindmaps
            all_topics = []
            all_relationships = []
            all_hierarchies = []
            source_mindmap_ids = []
            source_conversation_ids = []
            
            for mindmap in mindmaps:
                try:
                    mindmap_json = json.loads(mindmap['mindmap_json'])
                    hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_json)
                    extracted = MindmapSynthesizer.extract_key_topics_and_relationships(mindmap_json)
                    
                    all_topics.extend(extracted.get('key_topics', []))
                    all_relationships.extend(extracted.get('relationships', []))
                    all_hierarchies.append({
                        'levels': hierarchy.get('levels'),
                        'topics': extracted.get('key_topics', [])
                    })
                    source_mindmap_ids.append(mindmap['id'])
                    source_conversation_ids.append(mindmap['conversation_id'])
                except Exception as e:
                    logger.warning(f"Error processing mindmap {mindmap['id']}: {e}")
            
            # Prepare prompt for AI synthesis
            synthesis_prompt = f"""
            Synthesize the following mindmap data across {len(mindmaps)} conversations into a coherent knowledge structure.
            
            Key Topics Across All Mindmaps:
            {json.dumps(list(set(all_topics[:30]))[:20], indent=2)}
            
            Major Relationships:
            {json.dumps(all_relationships[:20], indent=2)}
            
            Hierarchy Summary:
            {json.dumps(all_hierarchies[:10], indent=2)}
            
            Please provide:
            1. A synthesized overview of the knowledge structure (2-3 paragraphs)
            2. Major themes and categories
            3. Key relationships and dependencies
            4. Areas of intersection between different conversations
            5. Gaps or areas for further exploration
            
            Format as structured JSON with fields: overview, themes, key_relationships, intersections, gaps
            """
            
            # Generate synthesis using AI
            response = await ask_llm(synthesis_prompt, model="gpt-4o-mini")
            
            if not response or "error" in response.lower():
                logger.error(f"AI synthesis failed: {response}")
                return None
            
            # Parse response
            try:
                # Extract JSON from response
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    synthesis_json = json.loads(response[start:end])
                else:
                    synthesis_json = {}
            except:
                synthesis_json = {'overview': response}
            
            # Store synthesis
            with connect() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO mindmap_syntheses
                    (synthesis_text, hierarchy_summary, source_mindmap_ids, source_conversation_ids,
                     key_topics, relationships)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    response,
                    json.dumps(all_hierarchies),
                    json.dumps(source_mindmap_ids),
                    json.dumps(source_conversation_ids),
                    json.dumps(list(set(all_topics[:50]))),  # Unique topics
                    json.dumps(all_relationships[:50])
                ))
                conn.commit()
                synthesis_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']
            
            logger.info(f"Generated synthesis {synthesis_id} from {len(mindmaps)} mindmaps")
            return synthesis_id
            
        except Exception as e:
            logger.error(f"Error generating synthesis: {e}")
            return None
    
    @staticmethod
    def get_current_synthesis() -> Optional[Dict[str, Any]]:
        """Get the most recent synthesis."""
        with connect() as conn:
            synthesis = conn.execute("""
                SELECT id, synthesis_text, hierarchy_summary, key_topics,
                       relationships, source_mindmap_ids, source_conversation_ids,
                       created_at, updated_at
                FROM mindmap_syntheses
                ORDER BY updated_at DESC
                LIMIT 1
            """).fetchone()
        
        if synthesis:
            return dict(synthesis)
        return None
    
    @staticmethod
    def get_mindmap_by_hierarchy_level(level: int) -> List[Dict[str, Any]]:
        """Get all mindmap nodes at a specific hierarchy level.
        
        Args:
            level: Hierarchy level (0 = root, 1 = first level, etc.)
            
        Returns:
            List of nodes at that level across all mindmaps
        """
        all_mindmaps = MindmapSynthesizer.get_all_mindmaps()
        nodes_at_level = []
        
        for mindmap in all_mindmaps:
            try:
                mindmap_json = json.loads(mindmap['mindmap_json'])
                hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_json)
                
                nodes = hierarchy.get('nodes_by_level', {}).get(level, [])
                for node in nodes:
                    node['conversation_id'] = mindmap['conversation_id']
                    node['mindmap_id'] = mindmap['id']
                nodes_at_level.extend(nodes)
            except Exception as e:
                logger.warning(f"Error extracting level {level} from mindmap {mindmap['id']}: {e}")
        
        return nodes_at_level
    
    @staticmethod
    def get_hierarchy_summary() -> Dict[str, Any]:
        """Get summary of all mindmap hierarchies.
        
        Returns:
            {
                'total_mindmaps': 5,
                'total_nodes': 127,
                'avg_depth': 2.4,
                'levels_distribution': {0: 5, 1: 45, 2: 60, 3: 17},
                'conversation_count': 5
            }
        """
        mindmaps = MindmapSynthesizer.get_all_mindmaps()
        
        total_nodes = 0
        total_depth = 0
        levels_dist = {}
        conversation_ids = set()
        
        for mindmap in mindmaps:
            try:
                mindmap_json = json.loads(mindmap['mindmap_json'])
                hierarchy = MindmapSynthesizer.extract_hierarchy_from_mindmap(mindmap_json)
                
                total_nodes += hierarchy.get('node_count', 0)
                total_depth += hierarchy.get('max_depth', 0)
                conversation_ids.add(mindmap['conversation_id'])
                
                # Count nodes by level
                for level, nodes in hierarchy.get('nodes_by_level', {}).items():
                    levels_dist[level] = levels_dist.get(level, 0) + len(nodes)
            except Exception as e:
                logger.warning(f"Error processing mindmap {mindmap['id']}: {e}")
        
        avg_depth = total_depth / len(mindmaps) if mindmaps else 0
        
        return {
            'total_mindmaps': len(mindmaps),
            'total_nodes': total_nodes,
            'avg_depth': round(avg_depth, 2),
            'levels_distribution': levels_dist,
            'conversation_count': len(conversation_ids)
        }
