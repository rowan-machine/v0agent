# src/app/api/v1/models.py
"""
Pydantic models for API v1 request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# -------------------------
# Pagination
# -------------------------

class PaginatedResponse(BaseModel):
    """Standard paginated response wrapper."""
    items: List[Any]
    skip: int = 0
    limit: int = 50
    total: int
    
    
# -------------------------
# Meetings
# -------------------------

class MeetingCreate(BaseModel):
    """Request model for creating a meeting."""
    name: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = ""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    device_id: Optional[str] = None


class MeetingUpdate(BaseModel):
    """Request model for updating a meeting."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    notes: Optional[str] = None
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class MeetingResponse(BaseModel):
    """Response model for a meeting."""
    id: int
    name: str
    notes: Optional[str]
    date: str
    created_at: Optional[str] = None
    last_modified_at: Optional[str] = None


# -------------------------
# Documents
# -------------------------

class DocumentCreate(BaseModel):
    """Request model for creating a document."""
    title: str = Field(..., min_length=1, max_length=500)
    content: str
    doc_type: str = Field(default="note", pattern=r"^(note|doc|paste)$")


class DocumentUpdate(BaseModel):
    """Request model for updating a document."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = None


class DocumentResponse(BaseModel):
    """Response model for a document."""
    id: int
    title: str
    content: str
    doc_type: str
    created_at: Optional[str] = None


# -------------------------
# Signals
# -------------------------

class SignalCreate(BaseModel):
    """Request model for creating a signal."""
    signal_type: str = Field(..., pattern=r"^(decision|action_item|blocker|risk|idea)$")
    content: str = Field(..., min_length=1)
    source_meeting_id: Optional[int] = None
    priority: int = Field(default=0, ge=0, le=5)
    status: str = Field(default="active", pattern=r"^(active|resolved|archived)$")


class SignalUpdate(BaseModel):
    """Request model for updating a signal."""
    content: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=5)
    status: Optional[str] = Field(None, pattern=r"^(active|resolved|archived)$")


class SignalResponse(BaseModel):
    """Response model for a signal."""
    id: int
    signal_type: str
    content: str
    source_meeting_id: Optional[int]
    priority: int
    status: str
    created_at: Optional[str] = None


# -------------------------
# Tickets
# -------------------------

class TicketCreate(BaseModel):
    """Request model for creating a ticket."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = ""
    status: str = Field(default="backlog", pattern=r"^(backlog|active|in_progress|done|archived)$")
    priority: int = Field(default=0, ge=0, le=5)
    points: Optional[int] = Field(None, ge=0, le=21)
    tags: Optional[str] = None


class TicketUpdate(BaseModel):
    """Request model for updating a ticket."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r"^(backlog|active|in_progress|done|archived)$")
    priority: Optional[int] = Field(None, ge=0, le=5)
    points: Optional[int] = Field(None, ge=0, le=21)
    tags: Optional[str] = None


class TicketResponse(BaseModel):
    """Response model for a ticket."""
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: int
    points: Optional[int]
    tags: Optional[str]
    created_at: Optional[str] = None


# -------------------------
# Generic API Response
# -------------------------

class APIResponse(BaseModel):
    """Generic API response wrapper."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    status_code: int
