# tests/unit/test_search_services.py
"""
Unit tests for Search Domain Services.

Tests the text_search service functions including:
- highlight_match: Query highlighting with context
- search_documents: Document search functionality  
- search_meetings: Meeting search functionality
- search_meeting_documents: Transcript document search
"""

import pytest
from unittest.mock import patch, MagicMock


class TestHighlightMatch:
    """Tests for the highlight_match function."""

    def test_highlights_match_with_context(self):
        """Should highlight match and include context."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "This is a long text with MetaSpan mentioned in the middle of a sentence."
        result = highlight_match(text, "MetaSpan")
        
        assert "<mark>MetaSpan</mark>" in result
        assert "mentioned" in result  # Context after

    def test_case_insensitive_highlight(self):
        """Should highlight case-insensitively."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "The metaspan integration and METASPAN data are important."
        result = highlight_match(text, "MetaSpan")
        
        assert "<mark>" in result
        assert result.count("<mark>") == 2  # Both occurrences

    def test_handles_no_match(self):
        """Should return truncated text when no match."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "This is some text without the search term."
        result = highlight_match(text, "nonexistent")
        
        assert "<mark>" not in result
        assert len(result) <= 300

    def test_handles_empty_text(self):
        """Should handle empty text."""
        from src.app.domains.search.services.text_search import highlight_match
        
        result = highlight_match("", "query")
        assert result == ""

    def test_handles_none_text(self):
        """Should handle None text."""
        from src.app.domains.search.services.text_search import highlight_match
        
        result = highlight_match(None, "query")
        assert result == ""

    def test_handles_empty_query(self):
        """Should handle empty query."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "Some sample text content."
        result = highlight_match(text, "")
        assert result == text[:300]

    def test_handles_none_query(self):
        """Should handle None query."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "Some sample text content."
        result = highlight_match(text, None)
        assert result == text[:300]

    def test_adds_ellipsis_for_long_text(self):
        """Should add ellipsis when text is truncated."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "x" * 500 + "MetaSpan" + "y" * 500
        result = highlight_match(text, "MetaSpan", context_chars=50)
        
        assert result.startswith("...")
        assert result.endswith("...")

    def test_no_ellipsis_at_start_when_match_near_beginning(self):
        """Should not add ellipsis at start when match is near beginning."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "MetaSpan is mentioned at the start of this text."
        result = highlight_match(text, "MetaSpan", context_chars=100)
        
        assert not result.startswith("...")

    def test_no_ellipsis_at_end_when_match_near_end(self):
        """Should not add ellipsis at end when match is near end."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "This text ends with MetaSpan"
        result = highlight_match(text, "MetaSpan", context_chars=100)
        
        assert not result.endswith("...")

    def test_handles_special_regex_characters(self):
        """Should handle special regex characters in query."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "The timestamp [00:05:30] shows the time."
        result = highlight_match(text, "[00:05:30]")
        
        assert "<mark>[00:05:30]</mark>" in result

    def test_custom_context_chars(self):
        """Should respect custom context_chars parameter."""
        from src.app.domains.search.services.text_search import highlight_match
        
        text = "a" * 200 + "target" + "b" * 200
        result = highlight_match(text, "target", context_chars=20)
        
        # Should have about 20 chars before + "target" + 20 chars after + ellipsis
        assert len(result) < 100  # Much less than full text


class TestSearchDocuments:
    """Tests for the search_documents function."""

    @patch('src.app.domains.search.services.text_search.document_service')
    def test_returns_matching_documents(self, mock_doc_service):
        """Should return documents matching query."""
        from src.app.domains.search.services.text_search import search_documents
        
        mock_doc_service.get_all_documents.return_value = [
            {"id": "doc-1", "source": "API Guide", "content": "REST API documentation", "document_date": "2026-01-20"},
            {"id": "doc-2", "source": "Database Schema", "content": "PostgreSQL tables", "document_date": "2026-01-21"},
        ]
        
        results = search_documents("REST API")
        
        assert len(results) == 1
        assert results[0]["id"] == "doc-1"
        assert results[0]["type"] == "document"

    @patch('src.app.domains.search.services.text_search.document_service')
    def test_case_insensitive_search(self, mock_doc_service):
        """Should perform case-insensitive search."""
        from src.app.domains.search.services.text_search import search_documents
        
        mock_doc_service.get_all_documents.return_value = [
            {"id": "doc-1", "source": "Guide", "content": "REST api documentation", "document_date": "2026-01-20"},
        ]
        
        results = search_documents("REST API")
        
        assert len(results) == 1

    @patch('src.app.domains.search.services.text_search.document_service')
    def test_searches_source_field(self, mock_doc_service):
        """Should search in source field too."""
        from src.app.domains.search.services.text_search import search_documents
        
        mock_doc_service.get_all_documents.return_value = [
            {"id": "doc-1", "source": "REST API Guide", "content": "Documentation", "document_date": "2026-01-20"},
        ]
        
        results = search_documents("REST API")
        
        assert len(results) == 1

    @patch('src.app.domains.search.services.text_search.document_service')
    def test_respects_date_filters(self, mock_doc_service):
        """Should filter by date range."""
        from src.app.domains.search.services.text_search import search_documents
        
        mock_doc_service.get_all_documents.return_value = [
            {"id": "doc-1", "source": "Guide", "content": "REST API v1", "document_date": "2026-01-15"},
            {"id": "doc-2", "source": "Guide", "content": "REST API v2", "document_date": "2026-01-25"},
        ]
        
        results = search_documents("REST API", start_date="2026-01-20")
        
        assert len(results) == 1
        assert results[0]["id"] == "doc-2"

    @patch('src.app.domains.search.services.text_search.document_service')
    def test_respects_limit(self, mock_doc_service):
        """Should respect limit parameter."""
        from src.app.domains.search.services.text_search import search_documents
        
        mock_doc_service.get_all_documents.return_value = [
            {"id": f"doc-{i}", "source": "Guide", "content": "REST API content", "document_date": "2026-01-20"}
            for i in range(20)
        ]
        
        results = search_documents("REST API", limit=5)
        
        assert len(results) == 5

    @patch('src.app.domains.search.services.text_search.document_service')
    def test_returns_empty_list_when_no_matches(self, mock_doc_service):
        """Should return empty list when no matches."""
        from src.app.domains.search.services.text_search import search_documents
        
        mock_doc_service.get_all_documents.return_value = [
            {"id": "doc-1", "source": "Guide", "content": "Other content", "document_date": "2026-01-20"},
        ]
        
        results = search_documents("nonexistent")
        
        assert len(results) == 0


class TestSearchMeetings:
    """Tests for the search_meetings function."""

    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_returns_matching_meetings(self, mock_meeting_service):
        """Should return meetings matching query in notes."""
        from src.app.domains.search.services.text_search import search_meetings
        
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Sprint Planning", "synthesized_notes": "Discussed sprint goals", "meeting_date": "2026-01-20"},
            {"id": "mtg-2", "meeting_name": "Design Review", "synthesized_notes": "UI mockups review", "meeting_date": "2026-01-21"},
        ]
        
        results = search_meetings("sprint")
        
        assert len(results) == 1
        assert results[0]["id"] == "mtg-1"
        assert results[0]["type"] == "meeting"

    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_searches_meeting_name(self, mock_meeting_service):
        """Should search in meeting name."""
        from src.app.domains.search.services.text_search import search_meetings
        
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Sprint Planning", "synthesized_notes": "General notes", "meeting_date": "2026-01-20"},
        ]
        
        results = search_meetings("Sprint")
        
        assert len(results) == 1

    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_includes_raw_text_when_flag_set(self, mock_meeting_service):
        """Should search raw_text when include_transcripts is True."""
        from src.app.domains.search.services.text_search import search_meetings
        
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Meeting", "synthesized_notes": "Summary", "raw_text": "MetaSpan discussion", "meeting_date": "2026-01-20"},
        ]
        
        # Without transcript flag - should not find
        results = search_meetings("MetaSpan", include_transcripts=False)
        assert len(results) == 0
        
        # With transcript flag - should find
        results = search_meetings("MetaSpan", include_transcripts=True)
        assert len(results) == 1
        assert results[0]["match_source"] == "transcript"

    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_match_source_indicates_notes(self, mock_meeting_service):
        """Should indicate match_source as 'notes' when found in notes."""
        from src.app.domains.search.services.text_search import search_meetings
        
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Meeting", "synthesized_notes": "Sprint goals discussion", "raw_text": "Other content", "meeting_date": "2026-01-20"},
        ]
        
        results = search_meetings("Sprint", include_transcripts=True)
        
        assert results[0]["match_source"] == "notes"

    @patch('src.app.domains.search.services.text_search.meeting_service')
    def test_respects_date_filters(self, mock_meeting_service):
        """Should filter by date range."""
        from src.app.domains.search.services.text_search import search_meetings
        
        mock_meeting_service.get_all_meetings.return_value = [
            {"id": "mtg-1", "meeting_name": "Meeting", "synthesized_notes": "Sprint planning", "meeting_date": "2026-01-15"},
            {"id": "mtg-2", "meeting_name": "Meeting", "synthesized_notes": "Sprint review", "meeting_date": "2026-01-25"},
        ]
        
        results = search_meetings("Sprint", start_date="2026-01-20", end_date="2026-01-30")
        
        assert len(results) == 1
        assert results[0]["id"] == "mtg-2"


class TestSearchMeetingDocuments:
    """Tests for the search_meeting_documents function."""

    @patch('src.app.domains.search.services.text_search.get_supabase_client')
    def test_returns_empty_when_no_supabase(self, mock_get_client):
        """Should return empty list when Supabase not configured."""
        from src.app.domains.search.services.text_search import search_meeting_documents
        
        mock_get_client.return_value = None
        
        results = search_meeting_documents("test")
        
        assert results == []

    @patch('src.app.domains.search.services.text_search.get_supabase_client')
    def test_searches_meeting_documents(self, mock_get_client):
        """Should search meeting documents table."""
        from src.app.domains.search.services.text_search import search_meeting_documents
        
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase
        
        # Mock the chained query
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.ilike.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.eq.return_value = mock_table
        
        # Mock document results
        mock_doc_response = MagicMock()
        mock_doc_response.data = [
            {"id": "doc-1", "meeting_id": "mtg-1", "doc_type": "transcript", "source": "teams", "content": "Snowflake discussion", "created_at": "2026-01-20"},
        ]
        
        # Mock meeting lookup
        mock_meeting_response = MagicMock()
        mock_meeting_response.data = [{"meeting_name": "Architecture Review", "meeting_date": "2026-01-20"}]
        
        mock_table.execute.side_effect = [mock_doc_response, mock_meeting_response]
        
        results = search_meeting_documents("Snowflake")
        
        assert len(results) == 1
        assert results[0]["type"] == "transcript"
        assert results[0]["source"] == "teams"

    @patch('src.app.domains.search.services.text_search.get_supabase_client')
    def test_handles_supabase_error(self, mock_get_client):
        """Should handle Supabase errors gracefully."""
        from src.app.domains.search.services.text_search import search_meeting_documents
        
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase
        mock_supabase.table.side_effect = Exception("Connection failed")
        
        results = search_meeting_documents("test")
        
        assert results == []


class TestSearchServicesIntegration:
    """Integration tests for search services module."""

    def test_module_exports(self):
        """Should export all expected functions."""
        from src.app.domains.search.services import (
            highlight_match,
            search_documents,
            search_meetings,
            search_meeting_documents,
        )
        
        assert callable(highlight_match)
        assert callable(search_documents)
        assert callable(search_meetings)
        assert callable(search_meeting_documents)

    def test_highlight_match_imported_correctly(self):
        """Should be able to import highlight_match from services."""
        from src.app.domains.search.services import highlight_match
        
        result = highlight_match("test text", "text")
        assert "<mark>text</mark>" in result
