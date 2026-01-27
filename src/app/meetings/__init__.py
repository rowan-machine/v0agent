# src/app/meetings/__init__.py
"""
Meeting management module.

This module handles all meeting-related functionality including:
- Meeting CRUD operations (create, read, update, delete)
- Screenshot processing with vision API
- Action items management
- Transcript summarization

Re-exports the combined router for use in main.py.
"""

from fastapi import APIRouter
from .routes import router as main_router
from .action_items import router as action_items_router
from .screenshots import process_screenshots, get_meeting_screenshots
from .transcripts import router as transcripts_router

# Create combined router
router = APIRouter()

# Include all sub-routers
router.include_router(main_router)
router.include_router(action_items_router)
router.include_router(transcripts_router)

__all__ = [
    "router",
    "process_screenshots",
    "get_meeting_screenshots",
]
