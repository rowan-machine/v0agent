# src/app/repositories/mindmap_repository.py
"""
Mindmap Repository - Data Access for Conversation Mindmaps and Syntheses

Handles all mindmap-related persistence:
- Conversation mindmaps (individual mindmap storage)
- Mindmap syntheses (aggregated AI-powered analysis)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json


@dataclass
class ConversationMindmap:
    """Conversation mindmap entity."""
    id: Optional[int] = None
    conversation_id: str = ""
    mindmap_json: str = "{}"
    hierarchy_levels: int = 0
    root_node_id: Optional[str] = None
    node_count: int = 0
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_mindmap_data(self) -> Dict[str, Any]:
        """Parse mindmap JSON to dictionary."""
        try:
            return json.loads(self.mindmap_json)
        except json.JSONDecodeError:
            return {}


@dataclass
class MindmapSynthesis:
    """Mindmap synthesis entity."""
    id: Optional[int] = None
    synthesis_text: str = ""
    synthesis_type: Optional[str] = None  # executive, technical, timeline, action_focus
    hierarchy_summary: Optional[str] = None
    source_mindmap_ids: Optional[str] = None
    source_conversation_ids: Optional[str] = None
    key_topics: Optional[str] = None
    relationships: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_key_topics_list(self) -> List[str]:
        """Parse key topics JSON to list."""
        try:
            return json.loads(self.key_topics or "[]")
        except json.JSONDecodeError:
            return []
    
    def get_source_mindmap_ids_list(self) -> List[int]:
        """Parse source mindmap IDs JSON to list."""
        try:
            return json.loads(self.source_mindmap_ids or "[]")
        except json.JSONDecodeError:
            return []


class MindmapRepository(ABC):
    """
    Abstract interface (Port) for mindmap data access.
    
    Defines all mindmap-related operations without implementation details.
    """
    
    # --- Conversation Mindmap Operations ---
    
    @abstractmethod
    def insert_conversation_mindmap(
        self,
        conversation_id: str,
        mindmap_json: str,
        hierarchy_levels: int = 0,
        root_node_id: Optional[str] = None,
        node_count: int = 0,
        title: Optional[str] = None,
    ) -> Optional[int]:
        """Insert a new conversation mindmap.
        
        Returns:
            ID of created mindmap or None on error
        """
        pass
    
    @abstractmethod
    def get_all_conversation_mindmaps(self) -> List[Dict[str, Any]]:
        """Get all stored mindmaps with metadata.
        
        Returns:
            List of mindmaps ordered by updated_at descending
        """
        pass
    
    @abstractmethod
    def get_conversation_mindmap_ids(self) -> List[int]:
        """Get all mindmap IDs for synthesis comparison.
        
        Returns:
            List of mindmap IDs
        """
        pass
    
    # --- Synthesis Operations ---
    
    @abstractmethod
    def get_recent_synthesis(self, hours: int = 1) -> Optional[Dict[str, Any]]:
        """Get synthesis created within recent hours.
        
        Args:
            hours: How many hours back to look
            
        Returns:
            Synthesis record or None
        """
        pass
    
    @abstractmethod
    def upsert_synthesis(
        self,
        synthesis_text: str,
        hierarchy_summary: str,
        source_mindmap_ids: str,
        source_conversation_ids: str,
        key_topics: str,
        relationships: str,
        synthesis_type: Optional[str] = None,
    ) -> Optional[int]:
        """Create or update a synthesis.
        
        Returns:
            Synthesis ID or None on error
        """
        pass
    
    @abstractmethod
    def insert_synthesis(
        self,
        synthesis_text: str,
        hierarchy_summary: str,
        source_mindmap_ids: str,
        source_conversation_ids: str,
        key_topics: str,
        relationships: str,
        synthesis_type: Optional[str] = None,
    ) -> Optional[int]:
        """Insert a new synthesis (no upsert).
        
        Returns:
            Synthesis ID or None on error
        """
        pass
    
    @abstractmethod
    def get_current_synthesis(self) -> Optional[Dict[str, Any]]:
        """Get the most recent synthesis (any type).
        
        Returns:
            Synthesis record or None
        """
        pass
    
    @abstractmethod
    def get_last_synthesis_source_ids(self) -> Optional[List[int]]:
        """Get source mindmap IDs from the last synthesis.
        
        Returns:
            List of mindmap IDs or None
        """
        pass
    
    @abstractmethod
    def get_recent_syntheses_by_type(self, limit: int = 4) -> Dict[str, int]:
        """Get recent syntheses grouped by type.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            Dict of synthesis_type -> synthesis_id
        """
        pass
    
    @abstractmethod
    def get_synthesis_by_type(
        self, 
        synthesis_type: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """Get most recent synthesis of a specific type.
        
        Args:
            synthesis_type: Type filter (default, executive, technical, etc.)
            
        Returns:
            Synthesis record or None
        """
        pass
    
    @abstractmethod
    def get_all_synthesis_types(self) -> List[str]:
        """Get list of all available synthesis types.
        
        Returns:
            Sorted list of unique synthesis types
        """
        pass


class SupabaseMindmapRepository(MindmapRepository):
    """
    Supabase implementation (Adapter) for mindmap data access.
    """
    
    def __init__(self):
        from ..infrastructure.supabase_client import get_supabase_client
        self._supabase = get_supabase_client()
    
    # --- Conversation Mindmap Operations ---
    
    def insert_conversation_mindmap(
        self,
        conversation_id: str,
        mindmap_json: str,
        hierarchy_levels: int = 0,
        root_node_id: Optional[str] = None,
        node_count: int = 0,
        title: Optional[str] = None,
    ) -> Optional[int]:
        """Insert a new conversation mindmap."""
        try:
            result = self._supabase.table("conversation_mindmaps").insert({
                "conversation_id": str(conversation_id),
                "mindmap_json": mindmap_json,
                "hierarchy_levels": hierarchy_levels,
                "root_node_id": root_node_id,
                "node_count": node_count,
                "title": title or str(conversation_id)
            }).execute()
            
            if result.data:
                return result.data[0].get("id")
            return None
        except Exception:
            return None
    
    def get_all_conversation_mindmaps(self) -> List[Dict[str, Any]]:
        """Get all stored mindmaps with metadata."""
        try:
            result = self._supabase.table("conversation_mindmaps")\
                .select("id, conversation_id, mindmap_json, hierarchy_levels, node_count, root_node_id, created_at")\
                .order("updated_at", desc=True)\
                .execute()
            return result.data or []
        except Exception:
            return []
    
    def get_conversation_mindmap_ids(self) -> List[int]:
        """Get all mindmap IDs for synthesis comparison."""
        try:
            result = self._supabase.table("conversation_mindmaps")\
                .select("id")\
                .order("id")\
                .execute()
            return [m["id"] for m in (result.data or [])]
        except Exception:
            return []
    
    # --- Synthesis Operations ---
    
    def get_recent_synthesis(self, hours: int = 1) -> Optional[Dict[str, Any]]:
        """Get synthesis created within recent hours."""
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            result = self._supabase.table("mindmap_syntheses")\
                .select("id")\
                .gte("updated_at", cutoff)\
                .limit(1)\
                .execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception:
            return None
    
    def upsert_synthesis(
        self,
        synthesis_text: str,
        hierarchy_summary: str,
        source_mindmap_ids: str,
        source_conversation_ids: str,
        key_topics: str,
        relationships: str,
        synthesis_type: Optional[str] = None,
    ) -> Optional[int]:
        """Create or update a synthesis."""
        try:
            data = {
                "synthesis_text": synthesis_text,
                "hierarchy_summary": hierarchy_summary,
                "source_mindmap_ids": source_mindmap_ids,
                "source_conversation_ids": source_conversation_ids,
                "key_topics": key_topics,
                "relationships": relationships,
            }
            if synthesis_type:
                data["synthesis_type"] = synthesis_type
            
            result = self._supabase.table("mindmap_syntheses")\
                .upsert(data)\
                .execute()
            
            if result.data:
                return result.data[0].get("id")
            return None
        except Exception:
            return None
    
    def insert_synthesis(
        self,
        synthesis_text: str,
        hierarchy_summary: str,
        source_mindmap_ids: str,
        source_conversation_ids: str,
        key_topics: str,
        relationships: str,
        synthesis_type: Optional[str] = None,
    ) -> Optional[int]:
        """Insert a new synthesis (no upsert)."""
        try:
            data = {
                "synthesis_text": synthesis_text,
                "hierarchy_summary": hierarchy_summary,
                "source_mindmap_ids": source_mindmap_ids,
                "source_conversation_ids": source_conversation_ids,
                "key_topics": key_topics,
                "relationships": relationships,
            }
            if synthesis_type:
                data["synthesis_type"] = synthesis_type
            
            result = self._supabase.table("mindmap_syntheses")\
                .insert(data)\
                .execute()
            
            if result.data:
                return result.data[0].get("id")
            return None
        except Exception:
            return None
    
    def get_current_synthesis(self) -> Optional[Dict[str, Any]]:
        """Get the most recent synthesis (any type)."""
        try:
            result = self._supabase.table("mindmap_syntheses")\
                .select("id, synthesis_text, hierarchy_summary, key_topics, relationships, source_mindmap_ids, source_conversation_ids, created_at, updated_at")\
                .order("updated_at", desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception:
            return None
    
    def get_last_synthesis_source_ids(self) -> Optional[List[int]]:
        """Get source mindmap IDs from the last synthesis."""
        try:
            result = self._supabase.table("mindmap_syntheses")\
                .select("source_mindmap_ids")\
                .order("updated_at", desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                try:
                    return json.loads(result.data[0]["source_mindmap_ids"])
                except (json.JSONDecodeError, TypeError):
                    return None
            return None
        except Exception:
            return None
    
    def get_recent_syntheses_by_type(self, limit: int = 4) -> Dict[str, int]:
        """Get recent syntheses grouped by type."""
        try:
            result = self._supabase.table("mindmap_syntheses")\
                .select("id, synthesis_type")\
                .order("updated_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return {
                row.get("synthesis_type") or "default": row["id"] 
                for row in (result.data or [])
            }
        except Exception:
            return {}
    
    def get_synthesis_by_type(
        self, 
        synthesis_type: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """Get most recent synthesis of a specific type."""
        try:
            if synthesis_type == "default":
                result = self._supabase.table("mindmap_syntheses")\
                    .select("id, synthesis_text, synthesis_type, hierarchy_summary, key_topics, relationships, source_mindmap_ids, source_conversation_ids, created_at, updated_at")\
                    .or_("synthesis_type.is.null,synthesis_type.eq.,synthesis_type.eq.default")\
                    .order("updated_at", desc=True)\
                    .limit(1)\
                    .execute()
            else:
                result = self._supabase.table("mindmap_syntheses")\
                    .select("id, synthesis_text, synthesis_type, hierarchy_summary, key_topics, relationships, source_mindmap_ids, source_conversation_ids, created_at, updated_at")\
                    .eq("synthesis_type", synthesis_type)\
                    .order("updated_at", desc=True)\
                    .limit(1)\
                    .execute()
            
            if result.data:
                synthesis = result.data[0]
                # Parse JSON fields
                for field_name in ["key_topics", "source_mindmap_ids", "source_conversation_ids", "relationships", "hierarchy_summary"]:
                    if synthesis.get(field_name) and isinstance(synthesis[field_name], str):
                        try:
                            synthesis[field_name] = json.loads(synthesis[field_name])
                        except json.JSONDecodeError:
                            pass
                return synthesis
            return None
        except Exception:
            return None
    
    def get_all_synthesis_types(self) -> List[str]:
        """Get list of all available synthesis types."""
        try:
            result = self._supabase.table("mindmap_syntheses")\
                .select("synthesis_type")\
                .execute()
            
            types = set()
            for row in (result.data or []):
                types.add(row.get("synthesis_type") or "default")
            return sorted(list(types))
        except Exception:
            return ["default"]


# Factory function
def get_mindmap_repository() -> MindmapRepository:
    """Get mindmap repository instance.
    
    Returns:
        MindmapRepository implementation
    """
    return SupabaseMindmapRepository()
