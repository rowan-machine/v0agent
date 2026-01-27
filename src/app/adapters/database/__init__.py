# src/app/adapters/database/__init__.py
"""
Database adapters package.

Contains concrete implementations of DatabasePort for different backends.
"""

from .supabase import SupabaseDatabaseAdapter
from .sqlite import SQLiteDatabaseAdapter

__all__ = [
    "SupabaseDatabaseAdapter",
    "SQLiteDatabaseAdapter",
]
