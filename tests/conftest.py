# tests/conftest.py
"""
Pytest configuration and fixtures for SignalFlow test suite.

Provides:
- Supabase mock client for testing
- FastAPI test client
- Common fixtures for meetings, documents, signals

Note: Tests use mocked Supabase client to avoid hitting production database.
The application uses Supabase as primary datastore (SQLite is deprecated).
"""

import os
import pytest
import uuid
from typing import Generator, Dict, Any, List
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

# Set test environment before imports
os.environ["SIGNALFLOW_ENV"] = "test"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_KEY"] = "test-key"


from src.app.main import app


# ============== Supabase Mock Fixtures ==============

class MockSupabaseResponse:
    """Mock response from Supabase operations."""
    def __init__(self, data: List[Dict] = None, count: int = None, error: str = None):
        self.data = data or []
        self.count = count if count is not None else len(self.data)
        self.error = error


class MockSupabaseTable:
    """Mock Supabase table with chainable methods."""
    
    def __init__(self, table_name: str, data_store: Dict[str, List[Dict]]):
        self.table_name = table_name
        self._data_store = data_store
        self._filters = {}
        self._order_by = None
        self._limit = None
        self._select_cols = "*"
        
    def select(self, columns: str = "*"):
        self._select_cols = columns
        return self
    
    def insert(self, data: Dict | List[Dict]):
        if isinstance(data, dict):
            data = [data]
        # Add UUIDs and timestamps if not present
        for item in data:
            if "id" not in item:
                item["id"] = str(uuid.uuid4())
            if "created_at" not in item:
                item["created_at"] = datetime.utcnow().isoformat()
        # Store in mock data store
        if self.table_name not in self._data_store:
            self._data_store[self.table_name] = []
        self._data_store[self.table_name].extend(data)
        return self
    
    def update(self, data: Dict):
        self._update_data = data
        return self
    
    def delete(self):
        return self
    
    def eq(self, column: str, value: Any):
        self._filters[column] = value
        return self
    
    def neq(self, column: str, value: Any):
        self._filters[f"neq_{column}"] = value
        return self
    
    def order(self, column: str, desc: bool = False):
        self._order_by = (column, desc)
        return self
    
    def limit(self, count: int):
        self._limit = count
        return self
    
    def range(self, start: int, end: int):
        self._range = (start, end)
        return self
    
    def execute(self) -> MockSupabaseResponse:
        """Execute the query and return results."""
        data = self._data_store.get(self.table_name, [])
        
        # Apply filters
        for col, val in self._filters.items():
            if col.startswith("neq_"):
                actual_col = col[4:]
                data = [d for d in data if d.get(actual_col) != val]
            else:
                data = [d for d in data if d.get(col) == val]
        
        # Apply limit
        if self._limit:
            data = data[:self._limit]
        
        # Reset state
        self._filters = {}
        self._order_by = None
        self._limit = None
        
        return MockSupabaseResponse(data=data)


class MockSupabaseClient:
    """Mock Supabase client for testing."""
    
    def __init__(self):
        self._data_store: Dict[str, List[Dict]] = {}
        self._rpc_results = {}
    
    def table(self, name: str) -> MockSupabaseTable:
        return MockSupabaseTable(name, self._data_store)
    
    def rpc(self, function_name: str, params: Dict = None):
        """Mock RPC call."""
        mock = MagicMock()
        result = self._rpc_results.get(function_name, [])
        mock.execute.return_value = MockSupabaseResponse(data=result)
        return mock
    
    def set_rpc_result(self, function_name: str, result: List[Dict]):
        """Set the result for an RPC call."""
        self._rpc_results[function_name] = result
    
    def seed_data(self, table_name: str, data: List[Dict]):
        """Seed test data into a table."""
        self._data_store[table_name] = data
    
    def clear(self):
        """Clear all test data."""
        self._data_store.clear()
        self._rpc_results.clear()


@pytest.fixture(scope="function")
def mock_supabase() -> MockSupabaseClient:
    """
    Mock Supabase client for testing.
    
    Provides a fully functional mock that stores data in memory
    and supports common operations like select, insert, update, delete.
    """
    return MockSupabaseClient()


@pytest.fixture(scope="function")
def mock_supabase_with_data(mock_supabase) -> MockSupabaseClient:
    """Supabase mock with sample data pre-loaded."""
    # Seed meetings
    mock_supabase.seed_data("meeting_summaries", [
        {
            "id": "uuid-meeting-1",
            "meeting_name": "Test Standup",
            "synthesized_notes": "Discussed test coverage goals",
            "meeting_date": "2024-01-15",
            "signals_json": {"decisions": [], "action_items": []},
            "created_at": "2024-01-15T10:00:00Z"
        }
    ])
    
    # Seed documents
    mock_supabase.seed_data("docs", [
        {
            "id": "uuid-doc-1",
            "source": "Test Document",
            "content": "Sample document content for testing",
            "document_date": "2024-01-15",
            "created_at": "2024-01-15T10:00:00Z"
        }
    ])
    
    # Seed tickets
    mock_supabase.seed_data("tickets", [
        {
            "id": "uuid-ticket-1",
            "ticket_id": "TEST-001",
            "title": "Test Ticket",
            "description": "Test ticket description",
            "status": "backlog",
            "sprint_points": 3,
            "created_at": "2024-01-15T10:00:00Z"
        }
    ])
    
    # Seed DIKW items
    mock_supabase.seed_data("dikw_items", [
        {
            "id": "uuid-dikw-1",
            "level": "information",
            "content": "Test insight from meeting",
            "source_type": "signal",
            "confidence": 0.75,
            "created_at": "2024-01-15T10:00:00Z"
        }
    ])
    
    # Seed AI memory
    mock_supabase.seed_data("ai_memory", [
        {
            "id": "uuid-memory-1",
            "source_type": "chat",
            "source_query": "What is testing?",
            "content": "Testing ensures code quality...",
            "status": "approved",
            "importance": 7,
            "created_at": "2024-01-15T10:00:00Z"
        }
    ])
    
    return mock_supabase


# ============== FastAPI Client Fixtures ==============

@pytest.fixture(scope="function")
def client(mock_supabase) -> Generator[TestClient, None, None]:
    """
    FastAPI test client with mocked Supabase.
    
    Patches get_supabase_client() to return the mock client.
    """
    with patch("src.app.infrastructure.supabase_client.get_supabase_client", return_value=mock_supabase):
        with patch("src.app.repositories.meeting_repository.get_supabase_client", return_value=mock_supabase):
            with TestClient(app) as test_client:
                yield test_client


@pytest.fixture(scope="function")
def client_with_data(mock_supabase_with_data) -> Generator[TestClient, None, None]:
    """FastAPI test client with pre-loaded test data."""
    with patch("src.app.infrastructure.supabase_client.get_supabase_client", return_value=mock_supabase_with_data):
        with patch("src.app.repositories.meeting_repository.get_supabase_client", return_value=mock_supabase_with_data):
            with TestClient(app) as test_client:
                yield test_client


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
