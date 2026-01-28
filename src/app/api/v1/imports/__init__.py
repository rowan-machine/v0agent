# src/app/api/v1/imports/__init__.py
"""
API v1 - File Import endpoints package.

Modular import functionality split into:
- upload: File upload and transcript import
- amend: Amend meetings with additional documents
- mindmap: Vision AI mindmap analysis

All routers are merged and exposed as a single 'router' for backward compatibility.
"""

from fastapi import APIRouter

from .upload import router as upload_router
from .amend import router as amend_router
from .mindmap import router as mindmap_router
from .mindmap import (
    parse_mindmap_analysis,
    create_dikw_items_from_mindmap,
    MINDMAP_ANALYSIS_PROMPT,
)
from .models import (
    ImportResult,
    ImportHistoryItem,
    MeetingDocumentResult,
    AmendMeetingResult,
    MeetingDocumentInfo,
    MindmapNode,
    MindmapAnalysis,
    MindmapIngestResult,
)
from .helpers import (
    extract_markdown_text,
    infer_meeting_name_from_content,
    record_import_history,
    extract_signals_from_content,
    merge_signals_holistically,
    add_document_to_meeting,
)

# Create combined router for backward compatibility
router = APIRouter()
router.include_router(upload_router)
router.include_router(amend_router)
router.include_router(mindmap_router)

__all__ = [
    "router",
    # Models
    "ImportResult",
    "ImportHistoryItem",
    "MeetingDocumentResult",
    "AmendMeetingResult",
    "MeetingDocumentInfo",
    "MindmapNode",
    "MindmapAnalysis",
    "MindmapIngestResult",
    # Helpers
    "extract_markdown_text",
    "infer_meeting_name_from_content",
    "record_import_history",
    "extract_signals_from_content",
    "merge_signals_holistically",
    "add_document_to_meeting",
    # Mindmap helpers
    "parse_mindmap_analysis",
    "create_dikw_items_from_mindmap",
    "MINDMAP_ANALYSIS_PROMPT",
]
