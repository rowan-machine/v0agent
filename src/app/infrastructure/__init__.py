# src/app/infrastructure/__init__.py
"""
Infrastructure components for SignalFlow - Phase 4.

Components:
- task_queue: Background task processing (RQ/Redis-based)
- mdns: Local network device discovery  
- cache: Redis caching layer
- rate_limiter: API rate limiting
- supabase_client: Supabase cloud database client
- supabase_agent: Supabase adapter for AI agents with write access

Usage:
    from .infrastructure import (
        TaskQueue, get_task_queue,
        MDNSDiscovery, get_mdns_discovery,
        CacheManager, get_cache,
        RateLimiter, get_rate_limiter,
        get_supabase_client, SupabaseSync, get_supabase_sync,
        get_supabase_agent_client, supabase_read, supabase_write,
    )
"""

from .task_queue import TaskQueue, get_task_queue
from .mdns import MDNSDiscovery, get_mdns_discovery
from .cache import CacheManager, get_cache
from .rate_limiter import RateLimiter, get_rate_limiter
from .supabase_client import get_supabase_client, SupabaseSync, get_supabase_sync
from .supabase_agent import (
    SupabaseAgentClient,
    get_supabase_agent_client,
    supabase_read,
    supabase_write,
    supabase_update,
    supabase_upsert,
    supabase_delete,
    supabase_search,
)

__all__ = [
    # Task Queue
    "TaskQueue",
    "get_task_queue",
    
    # mDNS Discovery
    "MDNSDiscovery", 
    "get_mdns_discovery",
    
    # Cache
    "CacheManager",
    "get_cache",
    
    # Rate Limiter
    "RateLimiter",
    "get_rate_limiter",
    
    # Supabase Sync
    "get_supabase_client",
    "SupabaseSync",
    "get_supabase_sync",
    
    # Supabase Agent Adapter
    "SupabaseAgentClient",
    "get_supabase_agent_client",
    "supabase_read",
    "supabase_write",
    "supabase_update",
    "supabase_upsert",
    "supabase_delete",
    "supabase_search",
]

