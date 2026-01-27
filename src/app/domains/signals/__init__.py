# src/app/domains/signals/__init__.py
"""
Signals Domain - Signal extraction and management.

This domain handles:
- Signal browsing (decisions, action_items, blockers, risks, ideas)
- Signal extraction from documents/transcripts
- Signal status tracking and feedback

Sub-modules:
- api/browse.py: Signal browsing endpoints (by type, with filtering)
- api/extraction.py: Signal extraction from documents
- api/status.py: Signal status management
"""

from .api import router as signals_router

__all__ = ["signals_router"]
