# src/app/domains/documents/constants.py
"""
Documents Domain Constants
"""

# Document types
DOCUMENT_TYPES = [
    "note",
    "meeting_notes",
    "spec",
    "design",
    "adr",  # Architecture Decision Record
    "runbook",
    "wiki",
    "other",
]

# Document statuses
DOCUMENT_STATUSES = [
    "draft",
    "active",
    "archived",
    "deprecated",
]

# Default limits
DEFAULT_DOCUMENT_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 20
