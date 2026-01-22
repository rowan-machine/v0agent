"""
Dual-Write Database Adapter - SQLite + Supabase

This module provides a dual-write pattern for the phased migration:
1. Reads from SQLite (local-first, fast) OR Supabase (cloud-first)
2. Writes to both SQLite and Supabase (eventual consistency)
3. Background sync handles Supabase failures gracefully

Usage:
    from src.app.db_adapter import DualWriteDB
    
    db = DualWriteDB(user_id="...")
    
    # Read from configured source (SQLite or Supabase based on config)
    profile = await db.get_career_profile()
    
    # Write to both
    await db.save_career_suggestion(data)
    
    # Explicit sync
    await db.sync_to_supabase()
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .db import connect
from .config import get_config

logger = logging.getLogger(__name__)

# Try to import Supabase agent client
try:
    from .infrastructure.supabase_agent import get_supabase_agent_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase agent client not available")


@dataclass
class SyncStatus:
    """Status of a sync operation."""
    success: bool
    sqlite_success: bool
    supabase_success: bool
    error: Optional[str] = None


class DualWriteDB:
    """
    Dual-write database adapter for SQLite + Supabase.
    
    Provides:
    - SQLite for local-first reads (fast, offline-capable)
    - Supabase reads when supabase_reads config is enabled
    - Supabase writes for cloud sync (eventual consistency)
    - Graceful degradation if Supabase is unavailable
    """
    
    def __init__(self, user_id: str = None, sync_enabled: bool = True):
        """
        Initialize dual-write adapter.
        
        Args:
            user_id: Supabase user ID for RLS filtering
            sync_enabled: Whether to sync to Supabase
        """
        self.user_id = user_id
        self.sync_enabled = sync_enabled and SUPABASE_AVAILABLE
        self._supabase = None
        self._pending_syncs: List[Dict] = []
    
    @property
    def supabase(self):
        """Get Supabase client lazily."""
        if self._supabase is None and SUPABASE_AVAILABLE:
            self._supabase = get_supabase_agent_client()
        return self._supabase
    
    @property
    def use_supabase_reads(self) -> bool:
        """Check if reads should come from Supabase."""
        try:
            config = get_config()
            return config.sync.supabase_reads and SUPABASE_AVAILABLE and self.supabase and self.supabase.is_connected
        except Exception:
            return False
    
    # ==========================================================================
    # Career Profile
    # ==========================================================================
    
    def get_career_profile(self) -> Optional[Dict]:
        """Get career profile from configured source (SQLite or Supabase)."""
        # Try Supabase if configured
        if self.use_supabase_reads:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If in async context, create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.supabase.read("career_profiles", filters={"id": self.user_id} if self.user_id else None, limit=1)
                        )
                        result = future.result(timeout=5)
                else:
                    result = asyncio.run(self.supabase.read("career_profiles", limit=1))
                if result:
                    logger.debug("Read career_profile from Supabase")
                    return result[0]
            except Exception as e:
                logger.warning(f"Supabase read failed, falling back to SQLite: {e}")
        
        # Fallback to SQLite
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM career_profile WHERE id = 1"
            ).fetchone()
            return dict(row) if row else None
    
    async def update_career_profile(self, updates: Dict[str, Any]) -> SyncStatus:
        """Update career profile in both databases."""
        sqlite_success = False
        supabase_success = False
        error = None
        
        # Write to SQLite
        try:
            with connect() as conn:
                # Build update query
                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                values = list(updates.values())
                
                conn.execute(
                    f"UPDATE career_profile SET {set_clause} WHERE id = 1",
                    values
                )
                conn.commit()
            sqlite_success = True
        except Exception as e:
            error = f"SQLite error: {e}"
            logger.error(error)
        
        # Write to Supabase
        if self.sync_enabled and self.supabase and self.supabase.is_connected:
            try:
                result = await self.supabase.update_career_profile(self.user_id, updates)
                supabase_success = result.get("success", False)
                if not supabase_success:
                    error = result.get("error", "Unknown Supabase error")
            except Exception as e:
                error = f"Supabase error: {e}"
                logger.error(error)
        
        return SyncStatus(
            success=sqlite_success,
            sqlite_success=sqlite_success,
            supabase_success=supabase_success,
            error=error
        )
    
    # ==========================================================================
    # Career Suggestions
    # ==========================================================================
    
    def get_suggestions(
        self,
        status: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get career suggestions from configured source."""
        # Try Supabase if configured
        if self.use_supabase_reads:
            try:
                import asyncio
                filters = {"status": status} if status else None
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.supabase.read("career_suggestions", filters=filters, order_by="id", order_desc=True, limit=limit)
                        )
                        result = future.result(timeout=5)
                else:
                    result = asyncio.run(self.supabase.read("career_suggestions", filters=filters, order_by="id", order_desc=True, limit=limit))
                if result is not None:
                    logger.debug(f"Read {len(result)} suggestions from Supabase")
                    return result
            except Exception as e:
                logger.warning(f"Supabase read failed, falling back to SQLite: {e}")
        
        # Fallback to SQLite
        with connect() as conn:
            query = "SELECT * FROM career_suggestions"
            params = []
            
            if status:
                query += " WHERE status = ?"
                params.append(status)
            
            query += " ORDER BY id DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    
    async def save_suggestion(self, data: Dict[str, Any]) -> SyncStatus:
        """Save career suggestion to both databases."""
        sqlite_success = False
        supabase_success = False
        error = None
        
        # Write to SQLite
        try:
            with connect() as conn:
                conn.execute("""
                    INSERT INTO career_suggestions 
                    (suggestion_type, title, description, rationale, difficulty, 
                     time_estimate, related_goal, status, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("suggestion_type", "learning"),
                    data.get("title"),
                    data.get("description"),
                    data.get("rationale"),
                    data.get("difficulty"),
                    data.get("time_estimate"),
                    data.get("related_goal"),
                    data.get("status", "active"),
                    data.get("source", "ai"),
                ))
                conn.commit()
            sqlite_success = True
        except Exception as e:
            error = f"SQLite error: {e}"
            logger.error(error)
        
        # Write to Supabase
        if self.sync_enabled and self.supabase and self.supabase.is_connected:
            try:
                result = await self.supabase.save_career_suggestion(
                    user_id=self.user_id,
                    suggestion_type=data.get("suggestion_type", "learning"),
                    title=data.get("title"),
                    description=data.get("description"),
                    rationale=data.get("rationale"),
                    difficulty=data.get("difficulty"),
                    time_estimate=data.get("time_estimate"),
                    related_goal=data.get("related_goal"),
                )
                supabase_success = result.get("success", False)
            except Exception as e:
                error = f"Supabase error: {e}"
                logger.error(error)
        
        return SyncStatus(
            success=sqlite_success,
            sqlite_success=sqlite_success,
            supabase_success=supabase_success,
            error=error
        )
    
    async def update_suggestion_status(
        self,
        suggestion_id: int,
        status: str
    ) -> SyncStatus:
        """Update suggestion status in both databases."""
        sqlite_success = False
        supabase_success = False
        error = None
        
        # Write to SQLite
        try:
            with connect() as conn:
                conn.execute(
                    "UPDATE career_suggestions SET status = ? WHERE id = ?",
                    (status, suggestion_id)
                )
                conn.commit()
            sqlite_success = True
        except Exception as e:
            error = f"SQLite error: {e}"
        
        # For Supabase, we'd need the UUID, which requires ID mapping
        # This is handled by sync process
        
        return SyncStatus(
            success=sqlite_success,
            sqlite_success=sqlite_success,
            supabase_success=supabase_success,
            error=error
        )
    
    # ==========================================================================
    # Career Memories
    # ==========================================================================
    
    def get_memories(
        self,
        memory_type: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get career memories from SQLite."""
        with connect() as conn:
            query = "SELECT * FROM career_memories"
            params = []
            
            if memory_type:
                query += " WHERE memory_type = ?"
                params.append(memory_type)
            
            query += " ORDER BY created_at DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    
    async def save_memory(self, data: Dict[str, Any]) -> SyncStatus:
        """Save career memory to both databases."""
        sqlite_success = False
        supabase_success = False
        error = None
        
        # Write to SQLite
        try:
            with connect() as conn:
                conn.execute("""
                    INSERT INTO career_memories 
                    (memory_type, title, description, skills, source_type, is_pinned, is_ai_work)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("memory_type", "learning"),
                    data.get("title"),
                    data.get("description"),
                    data.get("skills"),  # comma-separated in SQLite
                    data.get("source_type"),
                    data.get("is_pinned", False),
                    data.get("is_ai_work", False),
                ))
                conn.commit()
            sqlite_success = True
        except Exception as e:
            error = f"SQLite error: {e}"
            logger.error(error)
        
        # Write to Supabase (synchronously via loop)
        if self.sync_enabled and self.supabase and self.supabase.is_connected:
            try:
                # Convert skills to array
                skills = data.get("skills")
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",") if s.strip()]
                
                # Run async method synchronously
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule async task
                    future = asyncio.ensure_future(self.supabase.save_career_memory(
                        user_id=self.user_id,
                        memory_type=data.get("memory_type", "learning"),
                        title=data.get("title"),
                        description=data.get("description"),
                        skills=skills,
                        source_type=data.get("source_type"),
                        is_ai_work=data.get("is_ai_work", False),
                    ))
                    supabase_success = True  # Optimistic
                else:
                    result = loop.run_until_complete(self.supabase.save_career_memory(
                        user_id=self.user_id,
                        memory_type=data.get("memory_type", "learning"),
                        title=data.get("title"),
                        description=data.get("description"),
                        skills=skills,
                        source_type=data.get("source_type"),
                        is_ai_work=data.get("is_ai_work", False),
                    ))
                    supabase_success = result.get("success", False)
            except Exception as e:
                error = f"Supabase error: {e}"
                logger.error(error)
        
        return SyncStatus(
            success=sqlite_success,
            sqlite_success=sqlite_success,
            supabase_success=supabase_success,
            error=error
        )
    
    # ==========================================================================
    # Skills
    # ==========================================================================
    
    def get_skills(
        self,
        category: str = None,
        min_proficiency: int = 0,
        limit: int = 50
    ) -> List[Dict]:
        """Get skills from SQLite."""
        with connect() as conn:
            query = "SELECT * FROM skill_tracker WHERE proficiency_level >= ?"
            params = [min_proficiency]
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            query += " ORDER BY proficiency_level DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    
    async def update_skill(
        self,
        skill_name: str,
        category: str = "general",
        proficiency_delta: int = 0,
        evidence: str = None
    ) -> SyncStatus:
        """Update or create skill in both databases."""
        sqlite_success = False
        supabase_success = False
        error = None
        
        # Write to SQLite
        try:
            with connect() as conn:
                # Check if exists
                existing = conn.execute(
                    "SELECT * FROM skill_tracker WHERE skill_name = ?",
                    (skill_name,)
                ).fetchone()
                
                if existing:
                    new_prof = min(100, max(0, existing["proficiency_level"] + proficiency_delta))
                    
                    # Parse and update evidence
                    try:
                        current_evidence = json.loads(existing["evidence"] or "[]")
                    except:
                        current_evidence = []
                    
                    if evidence:
                        current_evidence.append(evidence)
                    
                    conn.execute("""
                        UPDATE skill_tracker 
                        SET proficiency_level = ?, 
                            evidence = ?,
                            last_used_at = datetime('now'),
                            updated_at = datetime('now')
                        WHERE skill_name = ?
                    """, (new_prof, json.dumps(current_evidence), skill_name))
                else:
                    conn.execute("""
                        INSERT INTO skill_tracker 
                        (skill_name, category, proficiency_level, evidence, last_used_at)
                        VALUES (?, ?, ?, ?, datetime('now'))
                    """, (
                        skill_name, 
                        category, 
                        max(0, min(100, proficiency_delta)),
                        json.dumps([evidence] if evidence else [])
                    ))
                
                conn.commit()
            sqlite_success = True
        except Exception as e:
            error = f"SQLite error: {e}"
            logger.error(error)
        
        # Write to Supabase
        if self.sync_enabled and self.supabase and self.supabase.is_connected:
            try:
                result = await self.supabase.update_skill(
                    user_id=self.user_id,
                    skill_name=skill_name,
                    category=category,
                    proficiency_delta=proficiency_delta,
                    evidence=evidence,
                )
                supabase_success = result.get("success", False)
            except Exception as e:
                error = f"Supabase error: {e}"
                logger.error(error)
        
        return SyncStatus(
            success=sqlite_success,
            sqlite_success=sqlite_success,
            supabase_success=supabase_success,
            error=error
        )
    
    # ==========================================================================
    # Standups
    # ==========================================================================
    
    def get_standups(self, limit: int = 10) -> List[Dict]:
        """Get standup updates from SQLite."""
        with connect() as conn:
            rows = conn.execute("""
                SELECT * FROM standup_updates 
                ORDER BY date DESC, id DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
    
    async def save_standup(
        self,
        content: str,
        sentiment: str = None,
        key_themes: List[str] = None,
        feedback: str = None,
        ai_analysis: Dict = None
    ) -> SyncStatus:
        """Save standup to both databases."""
        sqlite_success = False
        supabase_success = False
        error = None
        
        # Write to SQLite
        try:
            with connect() as conn:
                conn.execute("""
                    INSERT INTO standup_updates 
                    (content, sentiment, key_themes, feedback, date)
                    VALUES (?, ?, ?, ?, date('now'))
                """, (
                    content,
                    sentiment,
                    json.dumps(key_themes) if key_themes else None,
                    feedback,
                ))
                conn.commit()
            sqlite_success = True
        except Exception as e:
            error = f"SQLite error: {e}"
            logger.error(error)
        
        # Write to Supabase
        if self.sync_enabled and self.supabase and self.supabase.is_connected:
            try:
                result = await self.supabase.save_standup(
                    user_id=self.user_id,
                    content=content,
                    sentiment=sentiment,
                    key_themes=key_themes,
                    feedback=feedback,
                    ai_analysis=ai_analysis,
                )
                supabase_success = result.get("success", False)
            except Exception as e:
                error = f"Supabase error: {e}"
                logger.error(error)
        
        return SyncStatus(
            success=sqlite_success,
            sqlite_success=sqlite_success,
            supabase_success=supabase_success,
            error=error
        )
    
    # ==========================================================================
    # Chat History
    # ==========================================================================
    
    def get_chat_history(self, limit: int = 20) -> List[Dict]:
        """Get career chat history from SQLite."""
        with connect() as conn:
            rows = conn.execute("""
                SELECT * FROM career_chat_updates 
                ORDER BY id DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
    
    async def save_chat(
        self,
        message: str,
        response: str,
        summary: str = None,
        context: Dict = None
    ) -> SyncStatus:
        """Save chat exchange to both databases."""
        sqlite_success = False
        supabase_success = False
        error = None
        
        # Write to SQLite
        try:
            with connect() as conn:
                conn.execute("""
                    INSERT INTO career_chat_updates 
                    (message, response, summary)
                    VALUES (?, ?, ?)
                """, (message, response, summary))
                conn.commit()
            sqlite_success = True
        except Exception as e:
            error = f"SQLite error: {e}"
            logger.error(error)
        
        # Write to Supabase
        if self.sync_enabled and self.supabase and self.supabase.is_connected:
            try:
                result = await self.supabase.save_chat_update(
                    user_id=self.user_id,
                    message=message,
                    response=response,
                    summary=summary,
                    context=context,
                )
                supabase_success = result.get("success", False)
            except Exception as e:
                error = f"Supabase error: {e}"
                logger.error(error)
        
        return SyncStatus(
            success=sqlite_success,
            sqlite_success=sqlite_success,
            supabase_success=supabase_success,
            error=error
        )


# ==========================================================================
# Singleton instance
# ==========================================================================

_dual_db: Optional[DualWriteDB] = None


def get_dual_db(user_id: str = None) -> DualWriteDB:
    """Get or create dual-write database instance."""
    global _dual_db
    
    if _dual_db is None or (user_id and _dual_db.user_id != user_id):
        _dual_db = DualWriteDB(user_id=user_id)
    
    return _dual_db
