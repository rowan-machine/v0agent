# src/app/adapters/__init__.py
"""
Adapters package - concrete implementations of port interfaces.

This package contains all adapter implementations:
- database/supabase.py - Supabase database adapter
- database/sqlite.py - SQLite database adapter (for local/privacy)
- embedding/openai.py - OpenAI embedding adapter
- embedding/local.py - Local embedding adapter (sentence-transformers)
- storage/supabase.py - Supabase storage adapter
- storage/local.py - Local filesystem storage adapter
"""

from .database.supabase import SupabaseDatabaseAdapter
from .database.sqlite import SQLiteDatabaseAdapter

__all__ = [
    "SupabaseDatabaseAdapter",
    "SQLiteDatabaseAdapter",
]
