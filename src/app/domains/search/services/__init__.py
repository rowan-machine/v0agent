# src/app/domains/search/services/__init__.py
"""
Search Domain Services

Business logic for search operations.
"""

from .text_search import (
    highlight_match,
    search_documents,
    search_meetings,
    search_meeting_documents,
)

__all__ = [
    "highlight_match",
    "search_documents",
    "search_meetings",
    "search_meeting_documents",
]
