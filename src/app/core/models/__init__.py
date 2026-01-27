# src/app/core/models/__init__.py
"""
Domain models for the application.

These are pure data classes representing the core domain entities.
They are database-agnostic and used throughout the application.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DIKWLevel(str, Enum):
    """DIKW pyramid levels."""
    DATA = "data"
    INFORMATION = "information"
    KNOWLEDGE = "knowledge"
    WISDOM = "wisdom"


class SignalType(str, Enum):
    """Types of signals extracted from content."""
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    BLOCKER = "blocker"
    RISK = "risk"
    IDEA = "idea"
    INSIGHT = "insight"


class TicketStatus(str, Enum):
    """Ticket workflow statuses."""
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class NotificationType(str, Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    TASK = "task"


@dataclass
class Meeting:
    """Meeting entity."""
    id: Optional[int] = None
    meeting_name: str = ""
    meeting_date: Optional[str] = None
    signals: Optional[Dict[str, Any]] = None
    signals_json: Optional[str] = None
    topics: Optional[str] = None
    attendees: Optional[str] = None
    summary: Optional[str] = None
    processed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Document:
    """Document entity (transcripts, notes, etc.)."""
    id: Optional[int] = None
    source: str = ""
    content: str = ""
    meeting_id: Optional[int] = None
    document_type: str = "transcript"
    processed: bool = False
    embedding_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Ticket:
    """Ticket/task entity."""
    id: Optional[int] = None
    ticket_id: str = ""
    title: str = ""
    description: Optional[str] = None
    status: TicketStatus = TicketStatus.BACKLOG
    priority: str = "medium"
    meeting_id: Optional[int] = None
    source_signal: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d['status'] = self.status.value if isinstance(self.status, TicketStatus) else self.status
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class DIKWItem:
    """DIKW pyramid item."""
    id: Optional[int] = None
    level: DIKWLevel = DIKWLevel.DATA
    content: str = ""
    summary: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    meeting_id: Optional[int] = None
    original_signal_type: Optional[str] = None
    tags: Optional[str] = None
    confidence: int = 70
    validation_count: int = 0
    status: str = "active"
    promoted_to: Optional[int] = None
    promoted_at: Optional[datetime] = None
    source_ref_ids: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d['level'] = self.level.value if isinstance(self.level, DIKWLevel) else self.level
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Signal:
    """Signal extracted from content."""
    id: Optional[int] = None
    meeting_id: int = 0
    signal_type: SignalType = SignalType.DECISION
    signal_text: str = ""
    feedback: Optional[str] = None
    status: Optional[str] = None
    converted_to: Optional[str] = None
    converted_id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d['signal_type'] = self.signal_type.value if isinstance(self.signal_type, SignalType) else self.signal_type
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Conversation:
    """Chat conversation entity."""
    id: Optional[int] = None
    title: Optional[str] = None
    meeting_id: Optional[int] = None
    document_id: Optional[int] = None
    summary: Optional[str] = None
    archived: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Message:
    """Chat message entity."""
    id: Optional[int] = None
    conversation_id: int = 0
    role: str = "user"  # user, assistant, system
    content: str = ""
    run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Notification:
    """User notification entity."""
    id: Optional[int] = None
    title: str = ""
    message: str = ""
    notification_type: NotificationType = NotificationType.INFO
    link: Optional[str] = None
    read: bool = False
    dismissed: bool = False
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d['notification_type'] = self.notification_type.value if isinstance(self.notification_type, NotificationType) else self.notification_type
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class UserStatus:
    """User status/presence."""
    id: Optional[int] = None
    user_id: str = "default"
    status: str = "available"
    current_task: Optional[str] = None
    mode_session_id: Optional[int] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class ModeSession:
    """Workflow mode session."""
    id: Optional[int] = None
    mode: str = "mode-a"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


__all__ = [
    # Enums
    "DIKWLevel",
    "SignalType",
    "TicketStatus",
    "NotificationType",
    # Models
    "Meeting",
    "Document",
    "Ticket",
    "DIKWItem",
    "Signal",
    "Conversation",
    "Message",
    "Notification",
    "UserStatus",
    "ModeSession",
]
