# sdk/signalflow/models.py
"""
SignalFlow SDK Data Models

Pydantic models for API responses and requests.
These models provide type safety and validation for SDK operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class DIKWLevel(str, Enum):
    """DIKW pyramid levels."""
    DATA = "data"
    INFORMATION = "information"
    KNOWLEDGE = "knowledge"
    WISDOM = "wisdom"


class SignalType(str, Enum):
    """Meeting signal types."""
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    BLOCKER = "blocker"
    RISK = "risk"
    IDEA = "idea"
    QUESTION = "question"
    FOLLOWUP = "followup"


class TicketStatus(str, Enum):
    """Ticket status values."""
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    DONE = "done"


class TicketPriority(str, Enum):
    """Ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# DOMAIN MODELS
# =============================================================================

class Signal(BaseModel):
    """A signal extracted from a meeting."""
    id: Optional[int] = None
    meeting_id: str
    signal_type: SignalType
    content: str
    confidence: float = Field(default=0.7, ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class Meeting(BaseModel):
    """A meeting with extracted intelligence."""
    id: str
    meeting_name: str
    meeting_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    participants: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    signals: Dict[str, List[str]] = Field(default_factory=dict)
    transcript_length: Optional[int] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Ticket(BaseModel):
    """A work ticket."""
    id: Optional[int] = None
    ticket_id: str
    title: str
    description: Optional[str] = None
    status: TicketStatus = TicketStatus.BACKLOG
    priority: TicketPriority = TicketPriority.MEDIUM
    assignee: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    story_points: Optional[int] = None
    in_sprint: bool = False
    meeting_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DIKWItem(BaseModel):
    """An item in the DIKW knowledge pyramid."""
    id: Optional[int] = None
    level: DIKWLevel
    content: str
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)
    source_meeting_id: Optional[str] = None
    parent_id: Optional[int] = None
    status: str = "active"
    created_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None


class CareerProfile(BaseModel):
    """User's career profile."""
    id: Optional[int] = None
    user_id: Optional[str] = None
    current_role: Optional[str] = None
    target_role: Optional[str] = None
    years_experience: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CareerSuggestion(BaseModel):
    """AI-generated career suggestion."""
    id: Optional[int] = None
    suggestion_type: str
    title: str
    description: str
    priority: str = "medium"
    status: str = "suggested"
    source: Optional[str] = None
    created_at: Optional[datetime] = None


# =============================================================================
# API RESPONSE MODELS
# =============================================================================

class PaginatedResponse(BaseModel):
    """Paginated API response wrapper."""
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class MeetingListResponse(BaseModel):
    """Response for meeting list endpoint."""
    meetings: List[Meeting]
    count: int


class SignalListResponse(BaseModel):
    """Response for signal list endpoint."""
    signals: List[Signal]
    count: int


class TicketListResponse(BaseModel):
    """Response for ticket list endpoint."""
    tickets: List[Ticket]
    count: int


class DIKWPyramidResponse(BaseModel):
    """Response for DIKW pyramid endpoint."""
    pyramid: Dict[str, List[DIKWItem]]
    counts: Dict[str, int]


class SearchResponse(BaseModel):
    """Response for search endpoints."""
    results: List[Dict[str, Any]]
    count: int
    query: str
    took_ms: Optional[float] = None


# =============================================================================
# ANALYST MODELS (LangSmith Integration)
# =============================================================================

class TraceFeedback(BaseModel):
    """Feedback for a LangSmith trace."""
    run_id: str
    score: float = Field(ge=0, le=1)
    comment: Optional[str] = None
    feedback_type: str = "user_rating"
    created_at: Optional[datetime] = None


class AgentPerformance(BaseModel):
    """Performance metrics for an agent."""
    agent_name: str
    total_runs: int
    avg_latency_ms: float
    avg_score: Optional[float] = None
    error_rate: float
    period_days: int


class FeedbackSummary(BaseModel):
    """Aggregated feedback summary."""
    total_runs: int
    rated_runs: int
    avg_score: Optional[float] = None
    score_distribution: Dict[str, int] = Field(default_factory=dict)
    by_agent: Dict[str, AgentPerformance] = Field(default_factory=dict)
    period_days: int
