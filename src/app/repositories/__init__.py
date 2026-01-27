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
from .meeting_repository import MeetingRepository, SupabaseMeetingRepository
from .document_repository import DocumentRepository, SupabaseDocumentRepository
from .ticket_repository import TicketRepository, SupabaseTicketRepository
from .signal_repository import (
    SignalRepository,
    SupabaseSignalRepository,
    get_signal_repository,
)
from .settings_repository import (
    SettingsRepository,
    SupabaseSettingsRepository,
    get_settings_repository,
)
from .ai_memory_repository import (
    AIMemoryRepository,
    SupabaseAIMemoryRepository,
    get_ai_memory_repository,
)
from .agent_messages_repository import (
    AgentMessage,
    AgentMessagesRepository,
    SupabaseAgentMessagesRepository,
    MessagePriority,
    MessageType,
    get_agent_messages_repository,
)
from .mindmap_repository import (
    ConversationMindmap,
    MindmapSynthesis,
    MindmapRepository,
    SupabaseMindmapRepository,
    get_mindmap_repository,
)
from .notifications_repository import (
    NotificationEntity,
    NotificationsRepository,
    SupabaseNotificationsRepository,
    get_notifications_repository,
)
from .career_repository import (
    CareerProfile,
    CareerMemory,
    CareerSuggestion,
    SkillEntry,
    StandupUpdate,
    CodeLockerEntry,
    CareerRepository,
    SupabaseCareerRepository,
    get_career_repository,
)
from .dikw_repository import (
    DIKWItem,
    DIKWEvolution,
    DIKWPyramid,
    DIKW_LEVELS,
    DIKW_NEXT_LEVEL,
    DIKWRepository,
    SupabaseDIKWRepository,
    get_dikw_repository,
)

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
    # Signals
    "SignalRepository",
    "SupabaseSignalRepository",
    "get_signal_repository",
    # Settings
    "SettingsRepository",
    "SupabaseSettingsRepository",
    "get_settings_repository",
    # AI Memory
    "AIMemoryRepository",
    "SupabaseAIMemoryRepository",
    "get_ai_memory_repository",
    # Agent Messages
    "AgentMessage",
    "AgentMessagesRepository",
    "SupabaseAgentMessagesRepository",
    "MessagePriority",
    "MessageType",
    "get_agent_messages_repository",
    # Mindmaps
    "ConversationMindmap",
    "MindmapSynthesis",
    "MindmapRepository",
    "SupabaseMindmapRepository",
    "get_mindmap_repository",
    # Notifications
    "NotificationEntity",
    "NotificationsRepository",
    "SupabaseNotificationsRepository",
    "get_notifications_repository",
    # Career
    "CareerProfile",
    "CareerMemory",
    "CareerSuggestion",
    "SkillEntry",
    "StandupUpdate",
    "CodeLockerEntry",
    "CareerRepository",
    "SupabaseCareerRepository",
    "get_career_repository",
    # DIKW
    "DIKWItem",
    "DIKWEvolution",
    "DIKWPyramid",
    "DIKW_LEVELS",
    "DIKW_NEXT_LEVEL",
    "DIKWRepository",
    "SupabaseDIKWRepository",
    "get_dikw_repository",
]
