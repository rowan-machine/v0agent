# src/app/core/ports/__init__.py
"""
Port interfaces for the application.

Ports define the contracts that adapters must implement.
This allows swapping implementations (e.g., Supabase ↔ SQLite ↔ Postgres)
without changing business logic.
"""

from .database import DatabasePort
from .embedding import EmbeddingPort
from .storage import StoragePort

__all__ = [
    "DatabasePort",
    "EmbeddingPort",
    "StoragePort",
]
