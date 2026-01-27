# src/app/shared/repositories/__init__.py
"""
Repository Layer - Ports and Adapters Pattern

This module re-exports all repositories from the legacy location during migration.
Once migration is complete, the actual repository implementations will live here.

Usage:
    from src.app.shared.repositories import get_meeting_repository
    
    meetings_repo = get_meeting_repository()
    all_meetings = meetings_repo.get_all(limit=50)
"""

# Re-export from legacy location during migration
from ...repositories import (
    # Base
    BaseRepository,
    # Meetings
    MeetingRepository,
    SupabaseMeetingRepository,
    get_meeting_repository,
    # Documents
    DocumentRepository,
    SupabaseDocumentRepository,
    get_document_repository,
    # Tickets
    TicketRepository,
    SupabaseTicketRepository,
    get_ticket_repository,
    # Signals
    SignalRepository,
    SupabaseSignalRepository,
    get_signal_repository,
    # Settings
    SettingsRepository,
    SupabaseSettingsRepository,
    get_settings_repository,
    # AI Memory
    AIMemoryRepository,
    SupabaseAIMemoryRepository,
    get_ai_memory_repository,
    # Agent Messages
    AgentMessage,
    AgentMessagesRepository,
    SupabaseAgentMessagesRepository,
    MessagePriority,
    MessageType,
    get_agent_messages_repository,
    # Mindmaps
    ConversationMindmap,
    MindmapSynthesis,
    MindmapRepository,
    SupabaseMindmapRepository,
    get_mindmap_repository,
    # Notifications
    NotificationEntity,
    NotificationsRepository,
    SupabaseNotificationsRepository,
    get_notifications_repository,
    # Career
    CareerProfile,
    CareerMemory,
    CareerSuggestion,
    SkillEntry,
    StandupUpdate,
    CodeLockerEntry,
    CareerRepository,
    SupabaseCareerRepository,
    get_career_repository,
    # DIKW
    DIKWItem,
    DIKWEvolution,
    DIKWPyramid,
    DIKW_LEVELS,
    DIKW_NEXT_LEVEL,
    DIKWRepository,
    SupabaseDIKWRepository,
    get_dikw_repository,
)

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
