# src/app/infrastructure/cache.py
"""
Redis Cache Manager - Phase 4.4

Provides caching layer using Redis with automatic fallback to in-memory cache.

Features:
- Key-value storage with TTL
- JSON serialization
- Namespace support
- Cache invalidation patterns
- Graceful fallback to memory cache

Usage:
    from .cache import get_cache
    
    cache = get_cache()
    
    # Set with TTL (60 seconds)
    await cache.set("user:123", {"name": "John"}, ttl=60)
    
    # Get
    user = await cache.get("user:123")
    
    # Delete
    await cache.delete("user:123")
    
    # Invalidate pattern
    await cache.invalidate_pattern("user:*")
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    created_at: float
    ttl: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class CacheManager:
    """
    Redis-backed cache with memory fallback.
    
    When Redis is available, uses it for distributed caching.
    When Redis is unavailable, uses in-memory dict with TTL support.
    """
    
    _instance: Optional['CacheManager'] = None
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = 300,  # 5 minutes
        namespace: str = "signalflow",
    ):
        """
        Initialize cache manager.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
            namespace: Key namespace prefix
        """
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._namespace = namespace
        
        self._redis_client = None
        self._fallback_mode = True
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }
        self._cleanup_task = None
        
        # Try to connect to Redis
        self._connect_redis()
    
    def start_cleanup_task(self) -> None:
        """Start the background cleanup task for memory cache."""
        if self._fallback_mode and self._cleanup_task is None:
            try:
                self._cleanup_task = asyncio.create_task(self._cleanup_expired())
            except RuntimeError:
                # No event loop running, skip cleanup task
                pass
    
    def _connect_redis(self) -> bool:
        """Attempt to connect to Redis."""
        if not self._redis_url:
            logger.info("📦 Cache running in fallback mode (no Redis)")
            return False
        
        try:
            import redis.asyncio as aioredis
            
            self._redis_client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
            self._fallback_mode = False
            logger.info("✅ Cache connected to Redis")
            return True
        except ImportError:
            logger.warning("⚠️ redis.asyncio not installed, using fallback mode")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}, using fallback mode")
        
        return False
    
    def _make_key(self, key: str) -> str:
        """Create namespaced key."""
        return f"{self._namespace}:{key}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        full_key = self._make_key(key)
        
        if self._fallback_mode:
            entry = self._memory_cache.get(full_key)
            if entry and not entry.is_expired:
                self._cache_stats["hits"] += 1
                return entry.value
            if entry and entry.is_expired:
                del self._memory_cache[full_key]
            self._cache_stats["misses"] += 1
            return default
        
        try:
            value = await self._redis_client.get(full_key)
            if value is not None:
                self._cache_stats["hits"] += 1
                return json.loads(value)
            self._cache_stats["misses"] += 1
            return default
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (None = default TTL)
            
        Returns:
            True if successful
        """
        full_key = self._make_key(key)
        ttl = ttl if ttl is not None else self._default_ttl
        
        self._cache_stats["sets"] += 1
        
        if self._fallback_mode:
            self._memory_cache[full_key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl,
            )
            return True
        
        try:
            await self._redis_client.setex(
                full_key,
                ttl,
                json.dumps(value),
            )
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key existed
        """
        full_key = self._make_key(key)
        self._cache_stats["deletes"] += 1
        
        if self._fallback_mode:
            return self._memory_cache.pop(full_key, None) is not None
        
        try:
            result = await self._redis_client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        full_key = self._make_key(key)
        
        if self._fallback_mode:
            entry = self._memory_cache.get(full_key)
            return entry is not None and not entry.is_expired
        
        try:
            return await self._redis_client.exists(full_key) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Key pattern with wildcards (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        full_pattern = self._make_key(pattern)
        
        if self._fallback_mode:
            # Simple pattern matching for memory cache
            import fnmatch
            keys_to_delete = [
                k for k in self._memory_cache.keys()
                if fnmatch.fnmatch(k, full_pattern)
            ]
            for key in keys_to_delete:
                del self._memory_cache[key]
            return len(keys_to_delete)
        
        try:
            keys = []
            async for key in self._redis_client.scan_iter(full_pattern):
                keys.append(key)
            
            if keys:
                return await self._redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")
            return 0
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values at once.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict of key -> value for found keys
        """
        result = {}
        
        if self._fallback_mode:
            for key in keys:
                value = await self.get(key)
                if value is not None:
                    result[key] = value
            return result
        
        try:
            full_keys = [self._make_key(k) for k in keys]
            values = await self._redis_client.mget(full_keys)
            
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = json.loads(value)
            return result
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}
    
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set multiple values at once.
        
        Args:
            items: Dict of key -> value
            ttl: TTL for all items
            
        Returns:
            True if successful
        """
        for key, value in items.items():
            await self.set(key, value, ttl)
        return True
    
    async def _cleanup_expired(self) -> None:
        """Periodically clean up expired entries in memory cache."""
        while True:
            await asyncio.sleep(60)  # Every minute
            
            expired = [
                key for key, entry in self._memory_cache.items()
                if entry.is_expired
            ]
            
            for key in expired:
                del self._memory_cache[key]
            
            if expired:
                logger.debug(f"Cleaned up {len(expired)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = self._cache_stats["hits"] / total if total > 0 else 0
        
        return {
            **self._cache_stats,
            "hit_rate": hit_rate,
            "size": len(self._memory_cache) if self._fallback_mode else "N/A (Redis)",
            "mode": "memory" if self._fallback_mode else "redis",
        }
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        if self._fallback_mode:
            self._memory_cache.clear()
        else:
            # Clear namespace
            await self.invalidate_pattern("*")
        
        logger.info("🗑️ Cache cleared")
    
    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is connected."""
        return not self._fallback_mode


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache(
    redis_url: Optional[str] = None,
    default_ttl: int = 300,
    namespace: str = "signalflow",
) -> CacheManager:
    """
    Get the cache manager singleton.
    
    Args:
        redis_url: Redis URL (only used on first call)
        default_ttl: Default TTL (only used on first call)
        namespace: Key namespace (only used on first call)
        
    Returns:
        CacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        import os
        url = redis_url or os.environ.get("REDIS_URL")
        _cache_manager = CacheManager(
            redis_url=url,
            default_ttl=default_ttl,
            namespace=namespace,
        )
    return _cache_manager


# Cache decorator
def cached(
    key_template: str,
    ttl: Optional[int] = None,
):
    """
    Decorator to cache function results.
    
    Usage:
        @cached("user:{user_id}", ttl=60)
        async def get_user(user_id: int):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Build cache key from template
            cache_key = key_template.format(**kwargs)
            
            # Try cache
            cache = get_cache()
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator
