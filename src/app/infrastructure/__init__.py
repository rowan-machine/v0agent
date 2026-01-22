# src/app/infrastructure/__init__.py
"""
Infrastructure components for SignalFlow - Phase 4.

Components:
- task_queue: Background task processing (RQ/Redis-based)
- mdns: Local network device discovery  
- cache: Redis caching layer
- rate_limiter: API rate limiting
- supabase_client: Supabase cloud database client

Usage:
    from .infrastructure import (
        TaskQueue, get_task_queue,
        MDNSDiscovery, get_mdns_discovery,
        CacheManager, get_cache,
        RateLimiter, get_rate_limiter,
        get_supabase_client, SupabaseSync, get_supabase_sync,
    )
"""

from .task_queue import TaskQueue, get_task_queue
from .mdns import MDNSDiscovery, get_mdns_discovery
from .cache import CacheManager, get_cache
from .rate_limiter import RateLimiter, get_rate_limiter
from .supabase_client import get_supabase_client, SupabaseSync, get_supabase_sync

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
    
    # Supabase
    "get_supabase_client",
    "SupabaseSync",
    "get_supabase_sync",
]
