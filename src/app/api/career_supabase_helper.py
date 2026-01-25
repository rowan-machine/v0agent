"""
Career Supabase Integration Helper

Provides helper functions to sync career data to Supabase alongside SQLite writes.
This module can be imported into career.py for dual-write functionality.

Uses single Supabase backend configured via SUPABASE_URL/SUPABASE_KEY:
- Staging/Dev: Share same Supabase database
- Production: Separate Supabase database

Usage in career.py:
    from ..career_supabase_helper import sync_suggestion_to_supabase
    
    # After SQLite insert:
    sync_suggestion_to_supabase(suggestion_data)
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Try to import Supabase infrastructure
try:
    from ..infrastructure.supabase_client import get_supabase_client as get_infra_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# Fallback to agent client
if not SUPABASE_AVAILABLE:
    try:
        from ..infrastructure.supabase_agent import (
            get_supabase_agent_client,
            SupabaseAgentClient,
        )
        SUPABASE_AVAILABLE = True
    except ImportError:
        SUPABASE_AVAILABLE = False
        logger.warning("Supabase not available - writes will be SQLite-only")


def get_supabase_client() -> Optional[Any]:
    """
    Get Supabase client for career operations.
    
    Uses the same Supabase backend as the rest of the app.
    """
    # Try infrastructure client first
    try:
        from ..infrastructure.supabase_client import get_supabase_client as get_infra_client
        client = get_infra_client()
        if client:
            return client
    except ImportError:
        pass
    
    # Fall back to agent client
    if not SUPABASE_AVAILABLE:
        return None
    try:
        return get_supabase_agent_client()
    except Exception as e:
        logger.warning(f"Could not get Supabase client: {e}")
        return None


def sync_suggestion_to_supabase(
    suggestion_data: Dict[str, Any],
    user_id: str = None,
) -> bool:
    """
    Sync a career suggestion to Supabase (fire-and-forget).
    
    Args:
        suggestion_data: Dict with suggestion fields
        user_id: Optional Supabase user ID
    
    Returns:
        True if sync initiated, False otherwise
    """
    client = get_supabase_client()
    if not client:
        return False
    
    # Check if it's the agent client (async) or direct client
    if hasattr(client, 'is_connected') and not client.is_connected:
        return False
    
    try:
        # If using direct Supabase client (from multi-backend)
        if hasattr(client, 'table'):
            # Direct sync using raw client
            client.table("career_suggestions").insert({
                "user_id": user_id,
                "suggestion_type": suggestion_data.get('suggestion_type', 'skill_building'),
                "title": suggestion_data.get('title'),
                "description": suggestion_data.get('description'),
                "rationale": suggestion_data.get('rationale'),
                "difficulty": suggestion_data.get('difficulty'),
                "time_estimate": suggestion_data.get('time_estimate'),
                "related_goal": suggestion_data.get('related_goal'),
            }).execute()
            return True
        
        # Create async task for background sync (agent client)
        async def _sync():
            return await client.save_career_suggestion(
                user_id=user_id,
                suggestion_type=suggestion_data.get('suggestion_type', 'skill_building'),
                title=suggestion_data.get('title'),
                description=suggestion_data.get('description'),
                rationale=suggestion_data.get('rationale'),
                difficulty=suggestion_data.get('difficulty'),
                time_estimate=suggestion_data.get('time_estimate'),
                related_goal=suggestion_data.get('related_goal'),
            )
        
        # Schedule async task
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_sync())
        except RuntimeError:
            # No running loop - run synchronously
            asyncio.run(_sync())
        
        return True
    except Exception as e:
        logger.error(f"Supabase suggestion sync failed: {e}")
        return False


def sync_skill_to_supabase(
    skill_name: str,
    category: str = "general",
    proficiency_delta: int = 0,
    evidence: str = None,
    user_id: str = None,
) -> bool:
    """
    Sync a skill update to Supabase (fire-and-forget).
    """
    client = get_supabase_client()
    if not client or not client.is_connected:
        return False
    
    try:
        async def _sync():
            return await client.update_skill(
                user_id=user_id,
                skill_name=skill_name,
                category=category,
                proficiency_delta=proficiency_delta,
                evidence=evidence,
            )
        
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_sync())
        except RuntimeError:
            asyncio.run(_sync())
        
        return True
    except Exception as e:
        logger.error(f"Supabase skill sync failed: {e}")
        return False


def sync_memory_to_supabase(
    memory_data: Dict[str, Any],
    user_id: str = None,
) -> bool:
    """
    Sync a career memory to Supabase (fire-and-forget).
    """
    client = get_supabase_client()
    if not client or not client.is_connected:
        return False
    
    try:
        async def _sync():
            skills = memory_data.get('skills', [])
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(',') if s.strip()]
            
            return await client.save_career_memory(
                user_id=user_id,
                memory_type=memory_data.get('memory_type', 'learning'),
                title=memory_data.get('title'),
                description=memory_data.get('description'),
                skills=skills,
                source_type=memory_data.get('source_type'),
                is_ai_work=memory_data.get('is_ai_work', False),
            )
        
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_sync())
        except RuntimeError:
            asyncio.run(_sync())
        
        return True
    except Exception as e:
        logger.error(f"Supabase memory sync failed: {e}")
        return False


def sync_standup_to_supabase(
    content: str,
    sentiment: str = None,
    key_themes: List[str] = None,
    feedback: str = None,
    ai_analysis: Dict = None,
    user_id: str = None,
) -> bool:
    """
    Sync a standup update to Supabase (fire-and-forget).
    """
    client = get_supabase_client()
    if not client or not client.is_connected:
        return False
    
    try:
        async def _sync():
            return await client.save_standup(
                user_id=user_id,
                content=content,
                sentiment=sentiment,
                key_themes=key_themes,
                feedback=feedback,
                ai_analysis=ai_analysis,
            )
        
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_sync())
        except RuntimeError:
            asyncio.run(_sync())
        
        return True
    except Exception as e:
        logger.error(f"Supabase standup sync failed: {e}")
        return False


def sync_chat_to_supabase(
    message: str,
    response: str,
    summary: str = None,
    context: Dict = None,
    user_id: str = None,
) -> bool:
    """
    Sync a career chat exchange to Supabase (fire-and-forget).
    """
    client = get_supabase_client()
    if not client or not client.is_connected:
        return False
    
    try:
        async def _sync():
            return await client.save_chat_update(
                user_id=user_id,
                message=message,
                response=response,
                summary=summary,
                context=context,
            )
        
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_sync())
        except RuntimeError:
            asyncio.run(_sync())
        
        return True
    except Exception as e:
        logger.error(f"Supabase chat sync failed: {e}")
        return False


# Decorator for automatic Supabase sync
def with_supabase_sync(sync_func):
    """
    Decorator that calls a Supabase sync function after the wrapped function.
    
    Usage:
        @with_supabase_sync(sync_suggestion_to_supabase)
        async def create_suggestion(...):
            # Creates in SQLite
            return suggestion_data
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            if result:
                sync_func(result)
            return result
        return wrapper
    return decorator
