# src/app/repositories/__init__.py
"""
Repository Layer - Ports and Adapters Pattern

This module provides a clean abstraction over data access using Supabase.

Usage:
    from src.app.repositories import get_meeting_repository, get_ticket_repository
    
    meetings_repo = get_meeting_repository()
    tickets_repo = get_ticket_repository()
    
    # Use consistent interface
    all_meetings = meetings_repo.get_all(limit=50)
    meeting = meetings_repo.get_by_id("uuid")
    meetings_repo.create({"meeting_name": "Standup", ...})
"""

from .base import BaseRepository
from .meetings import MeetingRepository, SupabaseMeetingRepository
from .documents import DocumentRepository, SupabaseDocumentRepository
from .tickets import TicketRepository, SupabaseTicketRepository

def get_meeting_repository() -> MeetingRepository:
    """Get meeting repository (Supabase)."""
    return SupabaseMeetingRepository()


def get_document_repository() -> DocumentRepository:
    """Get document repository (Supabase)."""
    return SupabaseDocumentRepository()


def get_ticket_repository() -> TicketRepository:
    """Get ticket repository (Supabase)."""
    return SupabaseTicketRepository()


__all__ = [
    # Base
    "BaseRepository",
    # Meetings
    "MeetingRepository",
    "SupabaseMeetingRepository",
    "get_meeting_repository",
    # Documents
    "DocumentRepository",
    "SupabaseDocumentRepository",
    "get_document_repository",
    # Tickets
    "TicketRepository",
    "SupabaseTicketRepository",
    "get_ticket_repository",
]
