# src/app/api/models.py
"""
Pydantic models for API request/response validation.
Phase 3.4/3.5: HTTP status codes and Pydantic validation

Provides:
- Request validation with automatic 422 errors
- Response serialization
- Clear API contracts
- OpenAPI schema generation
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


# -------------------------
# Enums
# -------------------------

class SignalType(str, Enum):
    """Types of signals extracted from meetings."""
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    BLOCKER = "blocker"
    RISK = "risk"
    IDEA = "idea"


class SignalStatus(str, Enum):
    """Status of a signal."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class FeedbackType(str, Enum):
    """User feedback on AI-extracted content."""
    UP = "up"
    DOWN = "down"


class SuggestionType(str, Enum):
    """Types of career suggestions."""
    STRETCH = "stretch"
    SKILL_BUILDING = "skill_building"
    PROJECT = "project"
    LEARNING = "learning"


class SuggestionStatus(str, Enum):
    """Status of a career suggestion."""
    ACTIVE = "active"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"


class Difficulty(str, Enum):
    """Difficulty level for suggestions."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Sentiment(str, Enum):
    """Sentiment detected in standup updates."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    BLOCKED = "blocked"
    STRUGGLING = "struggling"


class MemoryType(str, Enum):
    """Types of career memories."""
    COMPLETED_PROJECT = "completed_project"
    AI_IMPLEMENTATION = "ai_implementation"
    SKILL_MILESTONE = "skill_milestone"
    ACHIEVEMENT = "achievement"
    LEARNING = "learning"


class DIKWLevel(str, Enum):
    """DIKW hierarchy levels."""
    DATA = "data"
    INFORMATION = "information"
    KNOWLEDGE = "knowledge"
    WISDOM = "wisdom"


class TicketStatus(str, Enum):
    """Ticket/task status."""
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    BLOCKED = "blocked"
    DONE = "done"


# -------------------------
# Base Response Models
# -------------------------

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None  # Machine-readable error code


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    items: List[Any]
    total: int
    skip: int = 0
    limit: int = 50
    has_more: bool = False


# -------------------------
# Signal Models
# -------------------------

class SignalFeedbackRequest(BaseModel):
    """Request to submit feedback on a signal."""
    meeting_id: int
    signal_type: SignalType
    signal_text: str
    feedback: FeedbackType
    include_in_chat: bool = True
    notes: Optional[str] = None


class SignalStatusRequest(BaseModel):
    """Request to update signal status."""
    meeting_id: int
    signal_type: SignalType
    signal_text: str
    status: SignalStatus


class SignalResponse(BaseModel):
    """Signal data response."""
    id: int
    signal_type: SignalType
    content: str
    status: SignalStatus
    priority: int = 0
    source_meeting_id: Optional[int] = None
    created_at: Optional[datetime] = None


# -------------------------
# Career Models
# -------------------------

class CareerProfileRequest(BaseModel):
    """Request to update career profile."""
    role_current: Optional[str] = None
    role_target: Optional[str] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    goals: Optional[str] = None
    skills: Optional[Dict[str, Any]] = None
    years_experience: Optional[int] = Field(None, ge=0, le=50)


class CareerProfileResponse(BaseModel):
    """Career profile response."""
    id: int
    role_current: Optional[str] = None
    role_target: Optional[str] = None
    strengths: List[str] = []
    weaknesses: List[str] = []
    interests: List[str] = []
    goals: Optional[str] = None
    skills: Dict[str, Any] = {}
    certifications: List[str] = []
    years_experience: Optional[int] = None
    updated_at: Optional[datetime] = None


class CareerSuggestionRequest(BaseModel):
    """Request to create/update a career suggestion."""
    suggestion_type: SuggestionType
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    rationale: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    time_estimate: Optional[str] = None
    related_goal: Optional[str] = None
    status: SuggestionStatus = SuggestionStatus.ACTIVE


class CareerSuggestionResponse(BaseModel):
    """Career suggestion response."""
    id: int
    suggestion_type: SuggestionType
    title: str
    description: Optional[str] = None
    rationale: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    time_estimate: Optional[str] = None
    related_goal: Optional[str] = None
    status: SuggestionStatus
    source: str = "ai"
    created_at: Optional[datetime] = None


class CareerChatRequest(BaseModel):
    """Request for career chat."""
    message: str = Field(..., min_length=1, max_length=10000)
    include_context: bool = True


class CareerChatResponse(BaseModel):
    """Career chat response."""
    response: str
    context_used: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None


class StandupRequest(BaseModel):
    """Request to submit a standup update."""
    content: str = Field(..., min_length=1, max_length=5000)
    sprint_date: Optional[str] = None


class StandupResponse(BaseModel):
    """Standup update response."""
    id: int
    content: str
    sentiment: Optional[Sentiment] = None
    key_themes: List[str] = []
    feedback: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    sprint_date: Optional[str] = None
    created_at: Optional[datetime] = None


class SkillUpdateRequest(BaseModel):
    """Request to update a skill."""
    skill_name: str = Field(..., min_length=1, max_length=255)
    category: str = "general"
    proficiency_level: int = Field(0, ge=0, le=100)
    evidence: Optional[List[Dict[str, Any]]] = None
    projects_count: int = Field(0, ge=0)
    tickets_count: int = Field(0, ge=0)


class SkillResponse(BaseModel):
    """Skill data response."""
    id: int
    skill_name: str
    category: str
    proficiency_level: int
    evidence: List[Dict[str, Any]] = []
    projects_count: int = 0
    tickets_count: int = 0
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class CareerMemoryRequest(BaseModel):
    """Request to create a career memory."""
    memory_type: MemoryType
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    skills: Optional[List[str]] = None
    source_type: Optional[str] = None
    is_pinned: bool = False
    is_ai_work: bool = False
    metadata: Optional[Dict[str, Any]] = None


class CareerMemoryResponse(BaseModel):
    """Career memory response."""
    id: int
    memory_type: MemoryType
    title: str
    description: Optional[str] = None
    skills: List[str] = []
    source_type: Optional[str] = None
    is_pinned: bool = False
    is_ai_work: bool = False
    metadata: Dict[str, Any] = {}
    created_at: Optional[datetime] = None


# -------------------------
# Search Models
# -------------------------

class SearchRequest(BaseModel):
    """Request for search."""
    query: str = Field(..., min_length=1, max_length=1000)
    source_type: str = "both"  # docs | meetings | both
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(10, ge=1, le=100)
    
    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed = {'docs', 'meetings', 'both'}
        if v not in allowed:
            raise ValueError(f'source_type must be one of: {allowed}')
        return v


class SemanticSearchRequest(BaseModel):
    """Request for semantic/hybrid search."""
    query: str = Field(..., min_length=1, max_length=1000)
    embedding: Optional[List[float]] = None  # Pre-computed embedding
    match_count: int = Field(10, ge=1, le=50)
    match_threshold: float = Field(0.7, ge=0.0, le=1.0)
    use_hybrid: bool = True  # Combine semantic + keyword search
    full_text_weight: float = Field(1.0, ge=0.0, le=10.0)
    semantic_weight: float = Field(1.0, ge=0.0, le=10.0)


class SearchResultItem(BaseModel):
    """Single search result."""
    id: Union[int, str]
    type: str  # document | meeting
    title: str
    snippet: str
    date: Optional[str] = None
    score: Optional[float] = None  # Relevance score


class SearchResponse(BaseModel):
    """Search results response."""
    results: List[SearchResultItem]
    query: str
    total_results: int
    search_type: str = "keyword"  # keyword | semantic | hybrid


# -------------------------
# Meeting Models
# -------------------------

class MeetingCreateRequest(BaseModel):
    """Request to create a meeting."""
    name: str = Field(..., min_length=1, max_length=500)
    notes: str = ""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    raw_text: Optional[str] = None


class MeetingUpdateRequest(BaseModel):
    """Request to update a meeting."""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    notes: Optional[str] = None
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class MeetingResponse(BaseModel):
    """Meeting data response."""
    id: int
    name: str
    notes: Optional[str] = None
    date: Optional[str] = None
    signals: Dict[str, List[str]] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# -------------------------
# Document Models
# -------------------------

class DocumentCreateRequest(BaseModel):
    """Request to create a document."""
    title: str = Field(..., min_length=1, max_length=500)
    content: str
    doc_type: str = Field(default="note", pattern=r"^(note|paste|transcript)$")


class DocumentResponse(BaseModel):
    """Document data response."""
    id: int
    title: str
    content: str
    doc_type: str = "note"
    created_at: Optional[datetime] = None


# -------------------------
# Ticket Models
# -------------------------

class TicketCreateRequest(BaseModel):
    """Request to create a ticket."""
    ticket_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    status: TicketStatus = TicketStatus.BACKLOG
    priority: Optional[str] = None
    sprint_points: int = Field(0, ge=0, le=21)
    in_sprint: bool = True
    tags: Optional[List[str]] = None


class TicketUpdateRequest(BaseModel):
    """Request to update a ticket."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[str] = None
    sprint_points: Optional[int] = Field(None, ge=0, le=21)
    in_sprint: Optional[bool] = None
    tags: Optional[List[str]] = None


class TicketResponse(BaseModel):
    """Ticket data response."""
    id: int
    ticket_id: str
    title: str
    description: Optional[str] = None
    status: TicketStatus
    priority: Optional[str] = None
    sprint_points: int = 0
    in_sprint: bool = True
    ai_summary: Optional[str] = None
    implementation_plan: Optional[str] = None
    tags: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# -------------------------
# DIKW Models
# -------------------------

class DIKWItemRequest(BaseModel):
    """Request to create a DIKW item."""
    level: DIKWLevel
    content: str = Field(..., min_length=1)
    summary: Optional[str] = None
    source_type: Optional[str] = None
    original_signal_type: Optional[str] = None
    meeting_id: Optional[int] = None
    tags: Optional[List[str]] = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class DIKWItemResponse(BaseModel):
    """DIKW item response."""
    id: int
    level: DIKWLevel
    content: str
    summary: Optional[str] = None
    source_type: Optional[str] = None
    original_signal_type: Optional[str] = None
    tags: List[str] = []
    confidence: float
    validation_count: int = 0
    status: str = "active"
    created_at: Optional[datetime] = None


# -------------------------
# Health Check Models
# -------------------------

class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, bool] = {}
