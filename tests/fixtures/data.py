# tests/fixtures/data.py
"""
Test data fixtures for SignalFlow tests.

Provides factory functions and sample data for creating test entities.
"""

from datetime import datetime, date
from typing import Dict, Any, Optional
import json


# ============== Meeting Fixtures ==============

def make_meeting(
    id: int = 1,
    meeting_name: str = "Test Standup",
    synthesized_notes: str = "Test notes content",
    meeting_date: str = "2024-01-15",
    signals_json: Optional[Dict] = None,
    template_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a meeting record for testing."""
    return {
        "id": id,
        "meeting_name": meeting_name,
        "synthesized_notes": synthesized_notes,
        "meeting_date": meeting_date,
        "signals_json": json.dumps(signals_json or {"decisions": [], "action_items": []}),
        "template_id": template_id,
        **kwargs
    }


def make_meeting_with_signals(
    id: int = 1,
    num_decisions: int = 2,
    num_actions: int = 3
) -> Dict[str, Any]:
    """Create a meeting with populated signals for testing."""
    signals = {
        "decisions": [
            {"text": f"Decision {i+1}", "confidence": 0.8}
            for i in range(num_decisions)
        ],
        "action_items": [
            {
                "text": f"Action item {i+1}",
                "owner": "Test User",
                "due_date": "2024-01-20"
            }
            for i in range(num_actions)
        ],
        "risks": [],
        "blockers": []
    }
    return make_meeting(id=id, signals_json=signals)


# ============== Document Fixtures ==============

def make_document(
    id: int = 1,
    source: str = "Test Document",
    content: str = "Test document content",
    document_date: str = "2024-01-15",
    **kwargs
) -> Dict[str, Any]:
    """Create a document record for testing."""
    return {
        "id": id,
        "source": source,
        "content": content,
        "document_date": document_date,
        **kwargs
    }


# ============== Ticket Fixtures ==============

def make_ticket(
    id: int = 1,
    ticket_id: str = "TEST-001",
    title: str = "Test Ticket",
    description: str = "Test ticket description",
    status: str = "backlog",
    sprint_points: int = 3,
    **kwargs
) -> Dict[str, Any]:
    """Create a ticket record for testing."""
    return {
        "id": id,
        "ticket_id": ticket_id,
        "title": title,
        "description": description,
        "status": status,
        "sprint_points": sprint_points,
        **kwargs
    }


# ============== DIKW Fixtures ==============

def make_dikw_item(
    id: int = 1,
    level: str = "information",
    content: str = "Test insight",
    source_type: str = "signal",
    confidence: float = 0.75,
    **kwargs
) -> Dict[str, Any]:
    """Create a DIKW item for testing."""
    return {
        "id": id,
        "level": level,
        "content": content,
        "source_type": source_type,
        "confidence": confidence,
        **kwargs
    }


DIKW_LEVELS = ["data", "information", "knowledge", "wisdom"]


# ============== AI Memory Fixtures ==============

def make_ai_memory(
    id: int = 1,
    source_type: str = "chat",
    source_query: str = "What is testing?",
    content: str = "Testing ensures code quality...",
    status: str = "approved",
    importance: int = 7,
    **kwargs
) -> Dict[str, Any]:
    """Create an AI memory record for testing."""
    return {
        "id": id,
        "source_type": source_type,
        "source_query": source_query,
        "content": content,
        "status": status,
        "importance": importance,
        **kwargs
    }


# ============== Signal Fixtures ==============

SAMPLE_SIGNALS = {
    "decisions": [
        {"text": "Decided to use Supabase for backend", "confidence": 0.9},
        {"text": "Will implement DDD patterns", "confidence": 0.85}
    ],
    "action_items": [
        {"text": "Create API documentation", "owner": "John", "due_date": "2024-01-20"},
        {"text": "Write unit tests for services", "owner": "Jane", "due_date": "2024-01-22"}
    ],
    "risks": [
        {"text": "Migration timeline is tight", "severity": "medium"}
    ],
    "blockers": [
        {"text": "Waiting on API keys", "status": "open"}
    ]
}


def make_signals(
    decisions: int = 2,
    actions: int = 2,
    risks: int = 1,
    blockers: int = 0
) -> Dict[str, Any]:
    """Create a signals object for testing."""
    return {
        "decisions": [
            {"text": f"Decision {i+1}", "confidence": 0.8 + (i * 0.05)}
            for i in range(decisions)
        ],
        "action_items": [
            {"text": f"Action {i+1}", "owner": f"Owner {i+1}", "due_date": "2024-01-20"}
            for i in range(actions)
        ],
        "risks": [
            {"text": f"Risk {i+1}", "severity": "medium"}
            for i in range(risks)
        ],
        "blockers": [
            {"text": f"Blocker {i+1}", "status": "open"}
            for i in range(blockers)
        ]
    }


# ============== Embedding Fixtures ==============

def make_embedding(dim: int = 1536) -> list:
    """Create a mock embedding vector."""
    import random
    return [random.uniform(-1, 1) for _ in range(dim)]


# ============== Request/Response Fixtures ==============

def make_meeting_request(
    meeting_name: str = "New Meeting",
    synthesized_notes: str = "Notes content",
    meeting_date: str = "2024-01-15"
) -> Dict[str, Any]:
    """Create a meeting creation request payload."""
    return {
        "meeting_name": meeting_name,
        "synthesized_notes": synthesized_notes,
        "meeting_date": meeting_date
    }


def make_search_request(
    query: str = "test query",
    filters: Optional[Dict] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """Create a search request payload."""
    return {
        "query": query,
        "filters": filters or {},
        "limit": limit
    }
