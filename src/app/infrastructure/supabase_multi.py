# src/app/infrastructure/supabase_multi.py
"""
Multi-Backend Supabase Client - Supports multiple Supabase projects.

This module enables different features to use separate Supabase backends:
- Default: Main v0agent data (meetings, documents, signals)
- Career: Skill tracking, AI implementation memories
- Analytics: Usage metrics, performance data (future)

Usage:
    from .supabase_multi import get_supabase_backend
    
    # Get default backend
    client = get_supabase_backend()
    
    # Get career backend (separate project)
    career_client = get_supabase_backend("career")
    
Environment Variables:
    Default:
        SUPABASE_URL, SUPABASE_KEY
    
    Career (optional, falls back to default):
        SUPABASE_CAREER_URL, SUPABASE_CAREER_KEY
"""

import logging
import os
from typing import Dict, Optional, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Cache for backend clients
_backend_clients: Dict[str, Any] = {}


class SupabaseBackend:
    """Wrapper for a Supabase backend with metadata."""
    
    def __init__(self, name: str, url: str, key: str, description: str = ""):
        self.name = name
        self.url = url
        self.key = key
        self.description = description
        self._client = None
    
    @property
    def client(self):
        """Lazy-load the client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _create_client(self):
        """Create the Supabase client."""
        try:
            from supabase import create_client
            from supabase.lib.client_options import ClientOptions
            
            options = ClientOptions(
                postgrest_client_timeout=30,
                storage_client_timeout=30,
            )
            client = create_client(self.url, self.key, options=options)
            logger.info(f"✅ Connected to Supabase backend '{self.name}': {self.url}")
            return client
        except TypeError as e:
            # Handle version incompatibility
            if "proxy" in str(e) or "unexpected keyword argument" in str(e):
                from supabase import create_client
                client = create_client(self.url, self.key)
                logger.info(f"✅ Connected to Supabase backend '{self.name}' (fallback): {self.url}")
                return client
            raise
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase backend '{self.name}': {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if the backend is available."""
        return self.client is not None


# Backend configurations
BACKEND_CONFIGS = {
    "default": {
        "url_env": "SUPABASE_URL",
        "key_env": "SUPABASE_KEY",
        "key_env_alt": "SUPABASE_ANON_KEY",
        "description": "Main v0agent data (meetings, documents, signals)",
    },
    "career": {
        "url_env": "SUPABASE_CAREER_URL",
        "key_env": "SUPABASE_CAREER_KEY",
        "fallback": "default",
        "description": "Career development data (skills, AI memories)",
    },
    "analytics": {
        "url_env": "SUPABASE_ANALYTICS_URL",
        "key_env": "SUPABASE_ANALYTICS_KEY",
        "fallback": "default",
        "description": "Usage metrics and performance data",
    },
}


def get_supabase_backend(name: str = "default") -> Optional[Any]:
    """
    Get a Supabase backend client by name.
    
    Args:
        name: Backend name ("default", "career", "analytics")
    
    Returns:
        Supabase client or None if not configured
    """
    global _backend_clients
    
    # Return cached client
    if name in _backend_clients:
        backend = _backend_clients[name]
        return backend.client if backend else None
    
    # Get config
    config = BACKEND_CONFIGS.get(name)
    if not config:
        logger.warning(f"⚠️ Unknown Supabase backend: {name}")
        return get_supabase_backend("default") if name != "default" else None
    
    # Get credentials from environment
    url = os.environ.get(config["url_env"])
    key = os.environ.get(config["key_env"]) or os.environ.get(config.get("key_env_alt", ""))
    
    # If not configured, try fallback
    if not url or not key:
        fallback = config.get("fallback")
        if fallback:
            logger.info(f"⚠️ Backend '{name}' not configured, using fallback '{fallback}'")
            return get_supabase_backend(fallback)
        logger.warning(f"⚠️ Backend '{name}' not configured (missing {config['url_env']} or {config['key_env']})")
        _backend_clients[name] = None
        return None
    
    # Create backend
    backend = SupabaseBackend(name, url, key, config.get("description", ""))
    _backend_clients[name] = backend
    
    return backend.client


def list_backends() -> Dict[str, Dict[str, Any]]:
    """
    List all configured backends and their status.
    
    Returns:
        Dict with backend names and their configuration/status
    """
    result = {}
    for name, config in BACKEND_CONFIGS.items():
        url = os.environ.get(config["url_env"])
        key = os.environ.get(config["key_env"]) or os.environ.get(config.get("key_env_alt", ""))
        
        result[name] = {
            "configured": bool(url and key),
            "url": url[:30] + "..." if url else None,
            "description": config.get("description", ""),
            "fallback": config.get("fallback"),
        }
    
    return result


def reset_backends():
    """Reset all backend clients (useful for testing)."""
    global _backend_clients
    _backend_clients = {}


# Convenience functions for specific backends

def get_default_client():
    """Get the default Supabase client."""
    return get_supabase_backend("default")


def get_career_client():
    """Get the career Supabase client (may fall back to default)."""
    return get_supabase_backend("career")


def get_analytics_client():
    """Get the analytics Supabase client (may fall back to default)."""
    return get_supabase_backend("analytics")
