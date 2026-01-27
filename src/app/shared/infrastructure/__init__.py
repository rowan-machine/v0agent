# src/app/shared/infrastructure/__init__.py
"""
Shared Infrastructure - Database clients, external service connections

Re-exports from legacy locations during migration.
"""

# Re-export Supabase client
from ...infrastructure.supabase_client import (
    get_supabase_client,
    get_supabase_url,
)

# Re-export storage
from ...services.storage_supabase import (
    upload_file,
    get_file_url,
    delete_file,
    list_files,
)

__all__ = [
    # Supabase
    "get_supabase_client",
    "get_supabase_url",
    # Storage
    "upload_file",
    "get_file_url", 
    "delete_file",
    "list_files",
]
