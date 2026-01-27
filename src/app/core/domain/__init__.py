# src/app/core/domain/__init__.py
"""
Domain Models for V0Agent

Pure dataclasses representing core business entities.
These are database-agnostic and contain no infrastructure concerns.

Design Principles:
- Immutable by default (frozen=True where sensible)
- No database-specific types (use str for UUIDs, Optional for nullable)
- Rich type hints for IDE support
- Factory methods for common creation patterns
"""

from .models import (
    # Enums
    DIKWLevel,
    SignalType,
    TicketStatus,
    NotificationType,
    SuggestionType,
    SuggestionStatus,
    MemoryType,
    
    # Meeting Domain
    Meeting,
    Signal,
    MeetingBundle,
    
    # Document Domain
    Document,
    
    # Ticket Domain
    Ticket,
    TaskDecomposition,
    
    # DIKW Domain
    DIKWItem,
    
    # Conversation Domain
    Conversation,
    Message,
    
    # Career Domain
    CareerProfile,
    CareerSuggestion,
    CareerMemory,
    StandupUpdate,
    Skill,
    
    # System Domain
    Notification,
    UserStatus,
    ModeSession,
    Settings,
)

__all__ = [
    # Enums
    "DIKWLevel",
    "SignalType",
    "TicketStatus",
    "NotificationType",
    "SuggestionType",
    "SuggestionStatus",
    "MemoryType",
    
    # Meeting Domain
    "Meeting",
    "Signal",
    "MeetingBundle",
    
    # Document Domain
    "Document",
    
    # Ticket Domain
    "Ticket",
    "TaskDecomposition",
    
    # DIKW Domain
    "DIKWItem",
    
    # Conversation Domain
    "Conversation",
    "Message",
    
    # Career Domain
    "CareerProfile",
    "CareerSuggestion",
    "CareerMemory",
    "StandupUpdate",
    "Skill",
    
    # System Domain
    "Notification",
    "UserStatus",
    "ModeSession",
    "Settings",
]
