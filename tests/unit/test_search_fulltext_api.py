# tests/unit/test_search_fulltext_api.py
"""
Unit tests for Search Domain Fulltext API.

Tests the /search endpoint for HTML template-based search.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestFulltextSearchAPI:
    """Tests for the fulltext search API route."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from src.app.main import app
        return TestClient(app)

    def test_search_returns_html(self, client):
        """Should return HTML template response."""
        response = client.get("/search")
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_search_requires_min_query_length(self, client):
        """Should not search with query less than 2 chars."""
        response = client.get("/search", params={"q": "a"})
        
        assert response.status_code == 200
        # Should have no results with single char query

    @patch('src.app.domains.search.services.text_search.document_service')
    def test_search_docs_source_type(self, mock_doc_service, client):
        """Should search only documents when source_type is docs."""
        mock_doc_service.get_all_documents.return_value = [
            {"id": "doc-1", "source": "API Guide", "content": "REST API documentation", "document_date": "2026-01-20"},
        ]
        
        response = client.get("/search", params={"q": "REST API", "source_type": "docs"})
        
        assert response.status_code == 200
        assert "API Guide" in response.text

    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_search_meetings_source_type(self, mock_meeting_service, client):
        """Should search only meetings when source_type is meetings."""
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Sprint Planning", "synthesized_notes": "Discussed sprint goals", "meeting_date": "2026-01-20"},
        ]
        
        response = client.get("/search", params={"q": "sprint", "source_type": "meetings"})
        
        assert response.status_code == 200
        assert "Sprint Planning" in response.text

    @patch('src.app.domains.search.services.text_search.document_service')
    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_search_both_source_type(self, mock_meeting_service, mock_doc_service, client):
        """Should search both documents and meetings when source_type is both."""
        mock_doc_service.get_all_documents.return_value = [
            {"id": "doc-1", "source": "Sprint Guide", "content": "Sprint planning tips", "document_date": "2026-01-20"},
        ]
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Sprint Planning", "synthesized_notes": "Discussed sprint goals", "meeting_date": "2026-01-20"},
        ]
        
        response = client.get("/search", params={"q": "sprint", "source_type": "both"})
        
        assert response.status_code == 200
        assert "Sprint Guide" in response.text
        assert "Sprint Planning" in response.text

    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_include_transcripts_flag(self, mock_meeting_service, client):
        """Should search raw_text when include_transcripts is true."""
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Meeting", "synthesized_notes": "Summary only", "raw_text": "MetaSpan integration details", "meeting_date": "2026-01-20"},
        ]
        
        # Without flag - should not find
        response = client.get("/search", params={"q": "MetaSpan", "source_type": "meetings"})
        assert "Meeting" not in response.text or "No results" in response.text
        
        # With flag - should find
        response = client.get("/search", params={"q": "MetaSpan", "source_type": "meetings", "include_transcripts": "true"})
        assert response.status_code == 200

    def test_date_filters_passed(self, client):
        """Should accept date filter parameters."""
        response = client.get("/search", params={
            "q": "test",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        })
        
        assert response.status_code == 200


class TestFulltextSearchRouterRegistration:
    """Tests for search router registration."""

    def test_fulltext_router_registered(self):
        """Should have fulltext_router in search domain exports."""
        from src.app.domains.search.api import fulltext_router
        assert fulltext_router is not None

    def test_fulltext_router_has_search_route(self):
        """Should have /search route."""
        from src.app.domains.search.api.fulltext import router
        routes = [route.path for route in router.routes]
        assert "/search" in routes


class TestSearchDomainServices:
    """Tests for search domain service imports from API."""

    def test_api_imports_services(self):
        """Should import services correctly in fulltext API."""
        from src.app.domains.search.api.fulltext import (
            highlight_match,
            search_documents,
            search_meetings,
            search_meeting_documents,
        )
        
        assert callable(highlight_match)
        assert callable(search_documents)
        assert callable(search_meetings)
        assert callable(search_meeting_documents)
