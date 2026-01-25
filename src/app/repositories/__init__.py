# src/app/repositories/__init__.py
"""
Repository Layer - Ports and Adapters Pattern

This module provides a clean abstraction over data access, allowing:
- Easy switching between SQLite and Supabase backends
- Consistent interface across all data sources
- Better testability with mock repositories
- Future-proofing for additional backends

Usage:
    from src.app.repositories import get_meeting_repository, get_ticket_repository
    
    # Get the configured repository (defaults to Supabase)
    meetings_repo = get_meeting_repository()
    tickets_repo = get_ticket_repository()
    
    # Use consistent interface
    all_meetings = meetings_repo.get_all(limit=50)
    meeting = meetings_repo.get_by_id("uuid")
    meetings_repo.create({"meeting_name": "Standup", ...})
"""

from .base import BaseRepository
from .meetings import MeetingRepository, SupabaseMeetingRepository, SQLiteMeetingRepository
from .documents import DocumentRepository, SupabaseDocumentRepository, SQLiteDocumentRepository
from .tickets import TicketRepository, SupabaseTicketRepository, SQLiteTicketRepository

# Configuration: Which backend to use
_DEFAULT_BACKEND = "supabase"  # "supabase" | "sqlite"


def get_meeting_repository(backend: str = None) -> MeetingRepository:
    """Get meeting repository for the specified backend."""
    backend = backend or _DEFAULT_BACKEND
    if backend == "sqlite":
        return SQLiteMeetingRepository()
    return SupabaseMeetingRepository()


def get_document_repository(backend: str = None) -> DocumentRepository:
    """Get document repository for the specified backend."""
    backend = backend or _DEFAULT_BACKEND
    if backend == "sqlite":
        return SQLiteDocumentRepository()
    return SupabaseDocumentRepository()


def get_ticket_repository(backend: str = None) -> TicketRepository:
    """Get ticket repository for the specified backend."""
    backend = backend or _DEFAULT_BACKEND
    if backend == "sqlite":
        return SQLiteTicketRepository()
    return SupabaseTicketRepository()


def set_default_backend(backend: str):
    """Set the default backend for all repositories."""
    global _DEFAULT_BACKEND
    if backend not in ("supabase", "sqlite"):
        raise ValueError(f"Invalid backend: {backend}. Use 'supabase' or 'sqlite'")
    _DEFAULT_BACKEND = backend


__all__ = [
    # Base
    "BaseRepository",
    # Meetings
    "MeetingRepository",
    "SupabaseMeetingRepository",
    "SQLiteMeetingRepository",
    "get_meeting_repository",
    # Documents
    "DocumentRepository",
    "SupabaseDocumentRepository",
    "SQLiteDocumentRepository",
    "get_document_repository",
    # Tickets
    "TicketRepository",
    "SupabaseTicketRepository",
    "SQLiteTicketRepository",
    "get_ticket_repository",
    # Config
    "set_default_backend",
]
