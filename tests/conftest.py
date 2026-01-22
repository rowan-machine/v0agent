# tests/conftest.py
"""
Pytest configuration and fixtures for SignalFlow test suite.

Provides:
- Test database setup/teardown
- FastAPI test client
- Supabase mock client
- Common fixtures for meetings, documents, signals
"""

import os
import pytest
import sqlite3
from typing import Generator, Dict, Any
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Set test environment before imports
os.environ["SIGNALFLOW_ENV"] = "test"
os.environ["AGENT_DB_PATH"] = ":memory:"

from src.app.main import app
from src.app.db import connect, init_db, SCHEMA


# ============== Database Fixtures ==============

@pytest.fixture(scope="function")
def test_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Create an in-memory SQLite database for testing.
    
    Yields a connection that is automatically cleaned up after the test.
    Each test gets a fresh database.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Initialize schema
    conn.executescript(SCHEMA)
    conn.commit()
    
    yield conn
    
    conn.close()


@pytest.fixture(scope="function")
def db_with_data(test_db) -> sqlite3.Connection:
    """Database with sample test data pre-loaded."""
    # Insert sample meeting
    test_db.execute(
        """
        INSERT INTO meeting_summaries (id, meeting_name, synthesized_notes, meeting_date, signals_json)
        VALUES (1, 'Test Standup', 'Discussed test coverage goals', '2024-01-15', '{"decisions": [], "action_items": []}')
        """
    )
    
    # Insert sample document
    test_db.execute(
        """
        INSERT INTO docs (id, source, content, document_date)
        VALUES (1, 'Test Document', 'Sample document content for testing', '2024-01-15')
        """
    )
    
    # Insert sample ticket
    test_db.execute(
        """
        INSERT INTO tickets (id, ticket_id, title, description, status, sprint_points)
        VALUES (1, 'TEST-001', 'Test Ticket', 'Test ticket description', 'backlog', 3)
        """
    )
    
    # Insert sample DIKW item
    test_db.execute(
        """
        INSERT INTO dikw_items (id, level, content, source_type, confidence)
        VALUES (1, 'information', 'Test insight from meeting', 'signal', 0.75)
        """
    )
    
    # Insert sample AI memory
    test_db.execute(
        """
        INSERT INTO ai_memory (id, source_type, source_query, content, status, importance)
        VALUES (1, 'chat', 'What is testing?', 'Testing ensures code quality...', 'approved', 7)
        """
    )
    
    test_db.commit()
    return test_db


# ============== FastAPI Client Fixtures ==============

@pytest.fixture(scope="function")
def client(test_db) -> Generator[TestClient, None, None]:
    """
    FastAPI test client with mocked database.
    
    Patches the connect() function to use the test database.
    """
    def mock_connect():
        return test_db
    
    with patch("src.app.db.connect", mock_connect):
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture(scope="function")
def client_with_data(db_with_data) -> Generator[TestClient, None, None]:
    """FastAPI test client with pre-loaded test data."""
    def mock_connect():
        return db_with_data
    
    with patch("src.app.db.connect", mock_connect):
        with TestClient(app) as test_client:
            yield test_client


# ============== Supabase Mock Fixtures ==============

@pytest.fixture
def mock_supabase() -> MagicMock:
    """
    Mock Supabase client for testing cloud sync.
    
    Provides chainable mock methods that mimic Supabase client behavior.
    """
    mock = MagicMock()
    
    # Mock table operations
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[], count=0)
    
    mock.table.return_value = mock_table
    
    return mock


@pytest.fixture
def mock_supabase_with_data(mock_supabase) -> MagicMock:
    """Supabase mock with sample data in responses."""
    sample_meeting = {
        "id": "uuid-123",
        "meeting_name": "Test Meeting",
        "synthesized_notes": "Test notes",
        "created_at": "2024-01-15T10:00:00Z"
    }
    
    mock_supabase.table.return_value.execute.return_value = MagicMock(
        data=[sample_meeting],
        count=1
    )
    
    return mock_supabase


# ============== Embedding Mock Fixtures ==============

@pytest.fixture
def mock_embeddings():
    """Mock embedding functions to avoid API calls in tests."""
    mock_vector = [0.1] * 1536  # OpenAI embedding dimension
    
    with patch("src.app.memory.embed.embed_text", return_value=mock_vector):
        with patch("src.app.memory.vector_store.upsert_embedding"):
            with patch("src.app.memory.vector_store.semantic_search", return_value=[]):
                yield mock_vector


# ============== Sample Data Factories ==============

@pytest.fixture
def meeting_factory():
    """Factory for creating test meeting data."""
    def _create_meeting(
        name: str = "Test Meeting",
        notes: str = "Test notes",
        date: str = "2024-01-15",
        signals: Dict = None
    ) -> Dict[str, Any]:
        return {
            "meeting_name": name,
            "synthesized_notes": notes,
            "meeting_date": date,
            "signals_json": signals or {"decisions": [], "action_items": []}
        }
    return _create_meeting


@pytest.fixture
def document_factory():
    """Factory for creating test document data."""
    def _create_document(
        source: str = "Test Source",
        content: str = "Test content",
        date: str = "2024-01-15"
    ) -> Dict[str, Any]:
        return {
            "source": source,
            "content": content,
            "document_date": date
        }
    return _create_document


@pytest.fixture
def ticket_factory():
    """Factory for creating test ticket data."""
    def _create_ticket(
        ticket_id: str = "TEST-001",
        title: str = "Test Ticket",
        description: str = "Test description",
        status: str = "backlog",
        points: int = 3
    ) -> Dict[str, Any]:
        return {
            "ticket_id": ticket_id,
            "title": title,
            "description": description,
            "status": status,
            "sprint_points": points
        }
    return _create_ticket


@pytest.fixture
def signal_feedback_factory():
    """Factory for creating signal feedback data."""
    def _create_feedback(
        meeting_id: int = 1,
        signal_type: str = "action_item",
        signal_text: str = "Test action item",
        feedback: str = "up"
    ) -> Dict[str, Any]:
        return {
            "meeting_id": meeting_id,
            "signal_type": signal_type,
            "signal_text": signal_text,
            "feedback": feedback,
            "include_in_chat": True
        }
    return _create_feedback


@pytest.fixture
def ai_memory_factory():
    """Factory for creating AI memory data."""
    def _create_memory(
        source_type: str = "chat",
        query: str = "Test question",
        content: str = "Test AI response",
        importance: int = 5
    ) -> Dict[str, Any]:
        return {
            "source_type": source_type,
            "source_query": query,
            "content": content,
            "importance": importance
        }
    return _create_memory


# ============== Assertion Helpers ==============

@pytest.fixture
def assert_response_success():
    """Helper to assert successful API responses."""
    def _assert(response, status_code: int = 200):
        assert response.status_code == status_code, f"Expected {status_code}, got {response.status_code}: {response.text}"
        return response.json()
    return _assert


@pytest.fixture
def assert_response_error():
    """Helper to assert error API responses."""
    def _assert(response, status_code: int = 400, detail: str = None):
        assert response.status_code == status_code
        if detail:
            assert detail in response.json().get("detail", "")
        return response.json()
    return _assert
