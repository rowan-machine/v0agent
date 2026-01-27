# src/app/adapters/storage/__init__.py
"""
Storage adapters package.

Contains concrete implementations of StoragePort for different providers:
- Supabase: Cloud storage using Supabase Storage
- Local: Local filesystem storage for privacy-focused deployments
"""

from .supabase import SupabaseStorageAdapter
from .local import LocalStorageAdapter

__all__ = [
    "SupabaseStorageAdapter",
    "LocalStorageAdapter",
]
