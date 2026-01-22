# src/app/infrastructure/rate_limiter.py
"""
API Rate Limiter - Phase 4.5

Provides rate limiting for API endpoints using token bucket algorithm.
Supports Redis for distributed rate limiting with memory fallback.

Features:
- Per-endpoint rate limits
- Per-user rate limits
- Token bucket algorithm
- Burst allowance
- Graceful degradation

Usage:
    from fastapi import Request, Depends
    from .rate_limiter import get_rate_limiter, rate_limit
    
    # As dependency
    @app.get("/api/data")
    async def get_data(request: Request, _=Depends(rate_limit("10/minute"))):
        ...
    
    # Programmatic
    limiter = get_rate_limiter()
    allowed, info = await limiter.check("user:123", "api:data", limit=10, window=60)
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """Rate limit check result."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after:
            headers["Retry-After"] = str(int(self.retry_after))
        return headers


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    tokens: float
    last_update: float
    
    def refill(self, rate: float, max_tokens: int) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(max_tokens, self.tokens + elapsed * rate)
        self.last_update = now
    
    def consume(self, count: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False


class RateLimiter:
    """
    Token bucket rate limiter with Redis support.
    
    Uses token bucket algorithm for smooth rate limiting with burst allowance.
    """
    
    _instance: Optional['RateLimiter'] = None
    
    # Default limits by endpoint type
    DEFAULT_LIMITS = {
        "default": (100, 60),      # 100 requests per minute
        "auth": (5, 60),           # 5 login attempts per minute
        "ai": (20, 60),            # 20 AI calls per minute
        "search": (30, 60),        # 30 searches per minute
        "upload": (10, 60),        # 10 uploads per minute
        "webhook": (1000, 60),     # 1000 webhooks per minute
    }
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_limit: int = 100,
        default_window: int = 60,
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_url: Redis connection URL
            default_limit: Default requests per window
            default_window: Default window in seconds
        """
        self._redis_url = redis_url
        self._default_limit = default_limit
        self._default_window = default_window
        
        self._redis_client = None
        self._fallback_mode = True
        self._buckets: Dict[str, TokenBucket] = {}
        
        # Try to connect to Redis
        self._connect_redis()
    
    def _connect_redis(self) -> bool:
        """Attempt to connect to Redis."""
        if not self._redis_url:
            logger.info("📦 Rate limiter running in fallback mode (no Redis)")
            return False
        
        try:
            import redis.asyncio as aioredis
            
            self._redis_client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
            self._fallback_mode = False
            logger.info("✅ Rate limiter connected to Redis")
            return True
        except ImportError:
            logger.warning("⚠️ redis.asyncio not installed, using fallback mode")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}, using fallback mode")
        
        return False
    
    def _make_key(self, *parts: str) -> str:
        """Create rate limit key."""
        return f"ratelimit:{':'.join(parts)}"
    
    async def check(
        self,
        identifier: str,
        endpoint: str = "default",
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> Tuple[bool, RateLimitInfo]:
        """
        Check if request is allowed.
        
        Args:
            identifier: Unique identifier (user ID, IP, etc.)
            endpoint: Endpoint name for limit lookup
            limit: Override limit
            window: Override window
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        # Get limits
        if limit is None or window is None:
            default = self.DEFAULT_LIMITS.get(endpoint, self.DEFAULT_LIMITS["default"])
            limit = limit or default[0]
            window = window or default[1]
        
        key = self._make_key(identifier, endpoint)
        now = time.time()
        reset_at = now + window
        
        if self._fallback_mode:
            return await self._check_memory(key, limit, window, now)
        else:
            return await self._check_redis(key, limit, window, now)
    
    async def _check_memory(
        self,
        key: str,
        limit: int,
        window: int,
        now: float,
    ) -> Tuple[bool, RateLimitInfo]:
        """Check rate limit using memory."""
        # Get or create bucket
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(tokens=limit, last_update=now)
            self._buckets[key] = bucket
        
        # Refill tokens
        rate = limit / window  # tokens per second
        bucket.refill(rate, limit)
        
        # Try to consume
        allowed = bucket.consume(1)
        remaining = int(bucket.tokens)
        reset_at = now + window
        
        info = RateLimitInfo(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=(window - bucket.tokens / rate) if not allowed else None,
        )
        
        return allowed, info
    
    async def _check_redis(
        self,
        key: str,
        limit: int,
        window: int,
        now: float,
    ) -> Tuple[bool, RateLimitInfo]:
        """Check rate limit using Redis."""
        try:
            # Sliding window log algorithm
            pipe = self._redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, now - window)
            
            # Count current entries
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiry
            pipe.expire(key, window)
            
            results = await pipe.execute()
            count = results[1]
            
            allowed = count < limit
            remaining = max(0, limit - count - 1)
            reset_at = now + window
            
            # If not allowed, remove the entry we just added
            if not allowed:
                await self._redis_client.zrem(key, str(now))
                remaining = 0
            
            info = RateLimitInfo(
                allowed=allowed,
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=window if not allowed else None,
            )
            
            return allowed, info
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open
            return True, RateLimitInfo(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_at=now + window,
            )
    
    async def get_usage(self, identifier: str, endpoint: str = "default") -> Dict[str, Any]:
        """Get current usage for an identifier."""
        key = self._make_key(identifier, endpoint)
        default = self.DEFAULT_LIMITS.get(endpoint, self.DEFAULT_LIMITS["default"])
        limit, window = default
        
        if self._fallback_mode:
            bucket = self._buckets.get(key)
            if bucket:
                return {
                    "identifier": identifier,
                    "endpoint": endpoint,
                    "used": limit - int(bucket.tokens),
                    "limit": limit,
                    "window": window,
                }
            return {
                "identifier": identifier,
                "endpoint": endpoint,
                "used": 0,
                "limit": limit,
                "window": window,
            }
        
        try:
            now = time.time()
            count = await self._redis_client.zcount(key, now - window, now)
            return {
                "identifier": identifier,
                "endpoint": endpoint,
                "used": count,
                "limit": limit,
                "window": window,
            }
        except Exception as e:
            logger.error(f"Error getting usage: {e}")
            return {
                "identifier": identifier,
                "endpoint": endpoint,
                "used": 0,
                "limit": limit,
                "window": window,
            }
    
    async def reset(self, identifier: str, endpoint: str = "default") -> bool:
        """Reset rate limit for an identifier."""
        key = self._make_key(identifier, endpoint)
        
        if self._fallback_mode:
            self._buckets.pop(key, None)
            return True
        
        try:
            await self._redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False
    
    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is connected."""
        return not self._fallback_mode


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    redis_url: Optional[str] = None,
    default_limit: int = 100,
    default_window: int = 60,
) -> RateLimiter:
    """
    Get the rate limiter singleton.
    
    Args:
        redis_url: Redis URL (only used on first call)
        default_limit: Default limit (only used on first call)
        default_window: Default window (only used on first call)
        
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        import os
        url = redis_url or os.environ.get("REDIS_URL")
        _rate_limiter = RateLimiter(
            redis_url=url,
            default_limit=default_limit,
            default_window=default_window,
        )
    return _rate_limiter


def parse_rate_limit(limit_str: str) -> Tuple[int, int]:
    """
    Parse rate limit string.
    
    Formats:
    - "10/minute" -> (10, 60)
    - "100/hour" -> (100, 3600)
    - "5/second" -> (5, 1)
    - "1000/day" -> (1000, 86400)
    """
    parts = limit_str.lower().split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid rate limit format: {limit_str}")
    
    count = int(parts[0])
    unit = parts[1].strip()
    
    windows = {
        "second": 1,
        "seconds": 1,
        "sec": 1,
        "s": 1,
        "minute": 60,
        "minutes": 60,
        "min": 60,
        "m": 60,
        "hour": 3600,
        "hours": 3600,
        "hr": 3600,
        "h": 3600,
        "day": 86400,
        "days": 86400,
        "d": 86400,
    }
    
    window = windows.get(unit)
    if window is None:
        raise ValueError(f"Unknown time unit: {unit}")
    
    return count, window


def rate_limit(
    limit_str: str = "100/minute",
    key_func: Optional[Callable[[Request], str]] = None,
    endpoint: str = "default",
):
    """
    FastAPI dependency for rate limiting.
    
    Usage:
        @app.get("/api/data")
        async def get_data(request: Request, _=Depends(rate_limit("10/minute"))):
            ...
    """
    limit, window = parse_rate_limit(limit_str)
    
    async def dependency(request: Request):
        # Get identifier
        if key_func:
            identifier = key_func(request)
        else:
            # Default: use IP + user ID if authenticated
            identifier = request.client.host if request.client else "unknown"
            
            # Add user ID if available
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                identifier = f"{identifier}:{user_id}"
        
        # Check rate limit
        limiter = get_rate_limiter()
        allowed, info = await limiter.check(
            identifier=identifier,
            endpoint=endpoint,
            limit=limit,
            window=window,
        )
        
        # Add headers to response (via state)
        request.state.rate_limit_headers = info.to_headers()
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": info.retry_after,
                    "limit": info.limit,
                    "window": window,
                },
                headers=info.to_headers(),
            )
        
        return info
    
    return dependency


# Middleware for adding rate limit headers
async def rate_limit_middleware(request: Request, call_next):
    """Middleware to add rate limit headers to responses."""
    response = await call_next(request)
    
    # Add rate limit headers if available
    headers = getattr(request.state, "rate_limit_headers", None)
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    
    return response
