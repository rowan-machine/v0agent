# src/app/api/v1/imports/models.py
"""
Pydantic models for import endpoints.
"""

from pydantic import BaseModel
from typing import Optional


class ImportResult(BaseModel):
    """Result of a successful file import."""
    meeting_id: int
    meeting_name: str
    transcript_length: int
    signal_count: int
    import_source: str
    warnings: list[str] = []


class ImportHistoryItem(BaseModel):
    """Import history record."""
    id: int
    filename: str
    file_type: str
    meeting_id: Optional[int]
    status: str
    error_message: Optional[str]
    created_at: str


class MeetingDocumentResult(BaseModel):
    """Result of adding a document to a meeting."""
    document_id: int
    meeting_id: int
    doc_type: str
    source: str
    content_length: int
    signal_count: int
    is_primary: bool


class AmendMeetingResult(BaseModel):
    """Result of amending a meeting with Pocket bundle."""
    meeting_id: int
    meeting_name: str
    documents_added: list[MeetingDocumentResult]
    total_signals_extracted: int
    holistic_signals_merged: int
    warnings: list[str] = []


class MeetingDocumentInfo(BaseModel):
    """Document info for listing."""
    id: int
    doc_type: str
    source: str
    content_length: int
    format: Optional[str]
    is_primary: bool
    created_at: str


class MindmapNode(BaseModel):
    """A node in the mindmap structure."""
    text: str
    children: list['MindmapNode'] = []
    node_type: Optional[str] = None  # 'root', 'category', 'item', 'detail'


class MindmapAnalysis(BaseModel):
    """Result of mindmap analysis."""
    root_topic: str
    structure: MindmapNode
    entities: list[str]  # People, systems, processes mentioned
    relationships: list[dict]  # {from: str, to: str, type: str}
    patterns: list[str]  # Identified patterns
    insights: list[str]  # AI-generated insights
    dikw_candidates: list[dict]  # Items suitable for DIKW promotion


class MindmapIngestResult(BaseModel):
    """Result of mindmap ingestion."""
    meeting_id: int
    document_id: int
    analysis: MindmapAnalysis
    dikw_items_created: int
    warnings: list[str] = []
