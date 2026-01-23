"""
Supabase Agent Adapter - Provides agents with Supabase read/write access.

This module bridges the gap between agents and Supabase MCP tools,
enabling agents to:
- Read and write to all Supabase tables
- Execute semantic search using pgvector embeddings
- Sync career data, suggestions, skills, and memories
- Use the service role key for bypassing RLS when needed

Usage:
    from src.app.infrastructure.supabase_agent import (
        supabase_read,
        supabase_write,
        supabase_upsert,
        supabase_search,
        get_supabase_agent_client,
    )
    
    # Read data
    meetings = await supabase_read("meetings", filters={"user_id": user_id})
    
    # Write data
    result = await supabase_write("career_suggestions", data={...})
    
    # Semantic search
    results = await supabase_search("meetings", query="sprint planning", limit=5)
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import Supabase client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None  # Define as None for type hints when not available
    create_client = None
    logger.warning("⚠️ supabase package not installed")


@dataclass
class SupabaseConfig:
    """Configuration for Supabase connection."""
    url: str
    anon_key: str
    service_role_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        """Load configuration from environment variables."""
        url = os.environ.get("SUPABASE_URL", "")
        anon_key = os.environ.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_KEY", ""))
        # Support both SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SECRET_KEY
        service_role_key = os.environ.get(
            "SUPABASE_SERVICE_ROLE_KEY", 
            os.environ.get("SUPABASE_SECRET_KEY", "")
        )
        
        return cls(url=url, anon_key=anon_key, service_role_key=service_role_key)
    
    @property
    def is_configured(self) -> bool:
        """Check if basic configuration is present."""
        return bool(self.url and (self.anon_key or self.service_role_key))


class SupabaseAgentClient:
    """
    Supabase client wrapper for agent operations.
    
    Provides both authenticated and service-role access modes.
    """
    
    def __init__(self, config: SupabaseConfig = None, use_service_role: bool = True):
        """
        Initialize Supabase agent client.
        
        Args:
            config: Supabase configuration (loads from env if not provided)
            use_service_role: Use service role key to bypass RLS
        """
        self.config = config or SupabaseConfig.from_env()
        self.use_service_role = use_service_role
        self._client: Optional[Client] = None
    
    @property
    def client(self) -> Optional[Client]:
        """Get or create Supabase client."""
        if not SUPABASE_AVAILABLE:
            return None
        
        if not self.config.is_configured:
            logger.warning("Supabase not configured - missing URL or key")
            return None
        
        if self._client is None:
            key = self.config.service_role_key if self.use_service_role else self.config.anon_key
            if not key:
                key = self.config.anon_key or self.config.service_role_key
            
            try:
                self._client = create_client(self.config.url, key)
            except Exception as e:
                logger.error(f"Failed to create Supabase client: {e}")
                return None
        
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.client is not None
    
    # ==========================================================================
    # Core CRUD Operations
    # ==========================================================================
    
    async def read(
        self,
        table: str,
        columns: str = "*",
        filters: Dict[str, Any] = None,
        order_by: str = None,
        order_desc: bool = True,
        limit: int = None,
        offset: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Read data from a Supabase table.
        
        Args:
            table: Table name
            columns: Columns to select (default: "*")
            filters: Dictionary of column=value filters
            order_by: Column to order by
            order_desc: Order descending if True
            limit: Maximum number of rows
            offset: Number of rows to skip
        
        Returns:
            List of matching rows as dictionaries
        """
        if not self.client:
            logger.warning(f"Supabase not available for read on {table}")
            return []
        
        try:
            query = self.client.table(table).select(columns)
            
            # Apply filters
            if filters:
                for col, val in filters.items():
                    if val is None:
                        query = query.is_(col, "null")
                    elif isinstance(val, list):
                        query = query.in_(col, val)
                    else:
                        query = query.eq(col, val)
            
            # Apply ordering
            if order_by:
                query = query.order(order_by, desc=order_desc)
            
            # Apply pagination
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Supabase read error on {table}: {e}")
            return []
    
    async def write(
        self,
        table: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Insert data into a Supabase table.
        
        Args:
            table: Table name
            data: Single row dict or list of row dicts
        
        Returns:
            Result with 'success', 'data', and optional 'error'
        """
        if not self.client:
            return {"success": False, "error": "Supabase not available", "data": None}
        
        try:
            result = self.client.table(table).insert(data).execute()
            return {"success": True, "data": result.data, "error": None}
            
        except Exception as e:
            logger.error(f"Supabase write error on {table}: {e}")
            return {"success": False, "error": str(e), "data": None}
    
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update data in a Supabase table.
        
        Args:
            table: Table name
            data: Column values to update
            filters: Filters to identify rows to update
        
        Returns:
            Result with 'success', 'data', and optional 'error'
        """
        if not self.client:
            return {"success": False, "error": "Supabase not available", "data": None}
        
        try:
            query = self.client.table(table).update(data)
            
            for col, val in filters.items():
                if val is None:
                    query = query.is_(col, "null")
                else:
                    query = query.eq(col, val)
            
            result = query.execute()
            return {"success": True, "data": result.data, "error": None}
            
        except Exception as e:
            logger.error(f"Supabase update error on {table}: {e}")
            return {"success": False, "error": str(e), "data": None}
    
    async def upsert(
        self,
        table: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        on_conflict: str = "id",
    ) -> Dict[str, Any]:
        """
        Upsert data into a Supabase table.
        
        Args:
            table: Table name
            data: Row data to upsert
            on_conflict: Column(s) to use for conflict detection
        
        Returns:
            Result with 'success', 'data', and optional 'error'
        """
        if not self.client:
            return {"success": False, "error": "Supabase not available", "data": None}
        
        try:
            result = self.client.table(table).upsert(
                data,
                on_conflict=on_conflict
            ).execute()
            return {"success": True, "data": result.data, "error": None}
            
        except Exception as e:
            logger.error(f"Supabase upsert error on {table}: {e}")
            return {"success": False, "error": str(e), "data": None}
    
    async def delete(
        self,
        table: str,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Delete data from a Supabase table.
        
        Args:
            table: Table name
            filters: Filters to identify rows to delete
        
        Returns:
            Result with 'success', 'deleted_count', and optional 'error'
        """
        if not self.client:
            return {"success": False, "error": "Supabase not available", "deleted_count": 0}
        
        try:
            query = self.client.table(table).delete()
            
            for col, val in filters.items():
                if val is None:
                    query = query.is_(col, "null")
                else:
                    query = query.eq(col, val)
            
            result = query.execute()
            return {
                "success": True,
                "deleted_count": len(result.data) if result.data else 0,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Supabase delete error on {table}: {e}")
            return {"success": False, "error": str(e), "deleted_count": 0}
    
    # ==========================================================================
    # Semantic Search (pgvector)
    # ==========================================================================
    
    async def semantic_search(
        self,
        query_embedding: List[float],
        ref_type: str = None,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using pgvector.
        
        Args:
            query_embedding: 1536-dimensional embedding vector
            ref_type: Filter by reference type ('meeting', 'document', etc.)
            limit: Maximum results to return
            similarity_threshold: Minimum cosine similarity (0-1)
        
        Returns:
            List of matching items with similarity scores
        """
        if not self.client:
            return []
        
        try:
            # Call the semantic search RPC function
            params = {
                "query_embedding": query_embedding,
                "match_count": limit,
                "similarity_threshold": similarity_threshold,
            }
            
            if ref_type:
                params["filter_ref_type"] = ref_type
            
            result = self.client.rpc("semantic_search", params).execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []
    
    # ==========================================================================
    # Career-Specific Operations
    # ==========================================================================
    
    async def save_career_suggestion(
        self,
        user_id: str,
        suggestion_type: str,
        title: str,
        description: str = None,
        rationale: str = None,
        difficulty: str = None,
        time_estimate: str = None,
        related_goal: str = None,
    ) -> Dict[str, Any]:
        """Save a career suggestion."""
        return await self.write("career_suggestions", {
            "user_id": user_id,
            "suggestion_type": suggestion_type,
            "title": title,
            "description": description,
            "rationale": rationale,
            "difficulty": difficulty,
            "time_estimate": time_estimate,
            "related_goal": related_goal,
            "status": "active",
            "source": "ai",
        })
    
    async def update_suggestion_status(
        self,
        suggestion_id: str,
        status: str,
    ) -> Dict[str, Any]:
        """Update a suggestion's status."""
        return await self.update(
            "career_suggestions",
            {"status": status, "updated_at": datetime.now().isoformat()},
            {"id": suggestion_id}
        )
    
    async def save_career_memory(
        self,
        user_id: str,
        memory_type: str,
        title: str,
        description: str = None,
        skills: List[str] = None,
        source_type: str = None,
        is_ai_work: bool = False,
    ) -> Dict[str, Any]:
        """Save a career memory (completed project, achievement, etc.)."""
        return await self.write("career_memories", {
            "user_id": user_id,
            "memory_type": memory_type,
            "title": title,
            "description": description,
            "skills": skills,
            "source_type": source_type,
            "is_ai_work": is_ai_work,
        })
    
    async def update_skill(
        self,
        user_id: str,
        skill_name: str,
        category: str = "general",
        proficiency_delta: int = 0,
        evidence: str = None,
    ) -> Dict[str, Any]:
        """Update or create a skill entry."""
        # Check if skill exists
        existing = await self.read(
            "skill_tracker",
            filters={"user_id": user_id, "skill_name": skill_name}
        )
        
        if existing:
            # Update existing
            current = existing[0]
            new_proficiency = min(100, max(0, current["proficiency_level"] + proficiency_delta))
            
            evidence_list = current.get("evidence") or []
            if evidence:
                evidence_list.append(evidence)
            
            return await self.update(
                "skill_tracker",
                {
                    "proficiency_level": new_proficiency,
                    "evidence": evidence_list,
                    "last_used_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                {"id": current["id"]}
            )
        else:
            # Create new
            return await self.write("skill_tracker", {
                "user_id": user_id,
                "skill_name": skill_name,
                "category": category,
                "proficiency_level": max(0, min(100, proficiency_delta)),
                "evidence": [evidence] if evidence else [],
                "last_used_at": datetime.now().isoformat(),
            })
    
    async def save_standup(
        self,
        user_id: str,
        content: str,
        sentiment: str = None,
        key_themes: List[str] = None,
        feedback: str = None,
        ai_analysis: Dict = None,
    ) -> Dict[str, Any]:
        """Save a standup update with AI analysis."""
        return await self.write("standup_updates", {
            "user_id": user_id,
            "content": content,
            "sentiment": sentiment,
            "key_themes": key_themes,
            "feedback": feedback,
            "ai_analysis": ai_analysis,
        })
    
    async def save_chat_update(
        self,
        user_id: str,
        message: str,
        response: str,
        summary: str = None,
        context: Dict = None,
    ) -> Dict[str, Any]:
        """Save a career chat exchange."""
        return await self.write("career_chat_updates", {
            "user_id": user_id,
            "message": message,
            "response": response,
            "summary": summary,
            "context": context,
        })
    
    async def update_career_profile(
        self,
        user_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update career profile."""
        updates["updated_at"] = datetime.now().isoformat()
        return await self.upsert(
            "career_profiles",
            {"user_id": user_id, **updates},
            on_conflict="user_id"
        )


# ==========================================================================
# Module-level singleton and convenience functions
# ==========================================================================

_agent_client: Optional[SupabaseAgentClient] = None


def get_supabase_agent_client(use_service_role: bool = True) -> SupabaseAgentClient:
    """Get the singleton Supabase agent client."""
    global _agent_client
    
    if _agent_client is None:
        _agent_client = SupabaseAgentClient(use_service_role=use_service_role)
    
    return _agent_client


# Convenience functions for direct use
async def supabase_read(
    table: str,
    columns: str = "*",
    filters: Dict[str, Any] = None,
    limit: int = None,
    order_by: str = None,
) -> List[Dict[str, Any]]:
    """Read from Supabase table."""
    client = get_supabase_agent_client()
    return await client.read(table, columns, filters, order_by, limit=limit)


async def supabase_write(
    table: str,
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Write to Supabase table."""
    client = get_supabase_agent_client()
    return await client.write(table, data)


async def supabase_update(
    table: str,
    data: Dict[str, Any],
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    """Update Supabase table."""
    client = get_supabase_agent_client()
    return await client.update(table, data, filters)


async def supabase_upsert(
    table: str,
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    on_conflict: str = "id",
) -> Dict[str, Any]:
    """Upsert to Supabase table."""
    client = get_supabase_agent_client()
    return await client.upsert(table, data, on_conflict)


async def supabase_delete(
    table: str,
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete from Supabase table."""
    client = get_supabase_agent_client()
    return await client.delete(table, filters)


async def supabase_search(
    query_embedding: List[float],
    ref_type: str = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Semantic search in Supabase."""
    client = get_supabase_agent_client()
    return await client.semantic_search(query_embedding, ref_type, limit)
