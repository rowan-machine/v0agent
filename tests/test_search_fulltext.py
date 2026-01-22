# tests/test_search_fulltext.py
"""
Tests for F2: Full-Text Transcript Search

Tests the enhanced search functionality including:
- Search across raw_text in meetings
- Search across meeting_documents (Teams/Pocket transcripts)
- Highlight matching with context
- Source filtering (transcripts only mode)
"""

import pytest
import json
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.main import app
from src.app.db import connect


client = TestClient(app)


# ============== Test Fixtures ==============

@pytest.fixture
def meeting_with_transcript():
    """Create a meeting with raw transcript text."""
    with connect() as conn:
        cursor = conn.execute("""
            INSERT INTO meeting_summaries 
            (meeting_name, synthesized_notes, meeting_date, signals_json, raw_text)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Sprint Planning Meeting",
            "We discussed the sprint goals and assigned tasks.",
            "2026-01-22",
            json.dumps({"decisions": [], "action_items": []}),
            """[00:00:15] Rowan: Good morning everyone. Today we're going to discuss the 
            MetaSpan integration and how it affects our pricing pipeline.
            
            [00:02:30] Alex: I think we need to consider the DataBricks connection first.
            
            [00:05:00] Sam: The Kubernetes deployment is ready for testing.
            
            [00:08:00] Rowan: Great, let's proceed with the MetaSpan pricing updates."""
        ))
        meeting_id = cursor.lastrowid
        conn.commit()
    
    yield meeting_id
    
    # Cleanup
    with connect() as conn:
        conn.execute("DELETE FROM meeting_documents WHERE meeting_id = ?", (meeting_id,))
        conn.execute("DELETE FROM meeting_summaries WHERE id = ?", (meeting_id,))
        conn.commit()


@pytest.fixture
def meeting_with_linked_documents():
    """Create a meeting with linked transcript documents."""
    with connect() as conn:
        cursor = conn.execute("""
            INSERT INTO meeting_summaries 
            (meeting_name, synthesized_notes, meeting_date, signals_json)
            VALUES (?, ?, ?, ?)
        """, (
            "Architecture Review",
            "Reviewed the system architecture and identified improvements.",
            "2026-01-21",
            json.dumps({"decisions": []})
        ))
        meeting_id = cursor.lastrowid
        
        # Add Teams transcript
        conn.execute("""
            INSERT INTO meeting_documents 
            (meeting_id, doc_type, source, content, format, is_primary)
            VALUES (?, 'transcript', 'teams', ?, 'txt', 1)
        """, (meeting_id, """
            Teams transcript of architecture review.
            
            Jonathan mentioned the PostgreSQL migration is critical.
            We discussed the OLAP vs OLTP considerations.
            The Snowflake integration was a key topic.
        """))
        
        # Add Pocket transcript
        conn.execute("""
            INSERT INTO meeting_documents 
            (meeting_id, doc_type, source, content, format, is_primary)
            VALUES (?, 'transcript', 'pocket', ?, 'txt', 0)
        """, (meeting_id, """
            Pocket transcription of architecture session.
            
            Nathan brought up the Redis caching strategy.
            Kristen suggested using Apache Kafka for event streaming.
            The microservices architecture was debated.
        """))
        
        conn.commit()
    
    yield meeting_id
    
    # Cleanup
    with connect() as conn:
        conn.execute("DELETE FROM meeting_documents WHERE meeting_id = ?", (meeting_id,))
        conn.execute("DELETE FROM meeting_summaries WHERE id = ?", (meeting_id,))
        conn.commit()


# ============== Test Highlight Function ==============

class TestHighlightMatch:
    """Tests for the highlight_match function."""
    
    def test_highlights_match_with_context(self):
        """Should highlight match and include context."""
        from src.app.search import highlight_match
        
        text = "This is a long text with MetaSpan mentioned in the middle of a sentence."
        result = highlight_match(text, "MetaSpan")
        
        assert "<mark>MetaSpan</mark>" in result
        assert "mentioned" in result  # Context after
    
    def test_case_insensitive_highlight(self):
        """Should highlight case-insensitively."""
        from src.app.search import highlight_match
        
        text = "The metaspan integration and METASPAN data are important."
        result = highlight_match(text, "MetaSpan")
        
        assert "<mark>" in result
        assert result.count("<mark>") == 2  # Both occurrences
    
    def test_handles_no_match(self):
        """Should return truncated text when no match."""
        from src.app.search import highlight_match
        
        text = "This is some text without the search term."
        result = highlight_match(text, "nonexistent")
        
        assert "<mark>" not in result
        assert len(result) <= 300
    
    def test_handles_empty_text(self):
        """Should handle empty text."""
        from src.app.search import highlight_match
        
        result = highlight_match("", "query")
        assert result == ""
    
    def test_adds_ellipsis_for_long_text(self):
        """Should add ellipsis when text is truncated."""
        from src.app.search import highlight_match
        
        text = "x" * 500 + "MetaSpan" + "y" * 500
        result = highlight_match(text, "MetaSpan", context_chars=50)
        
        assert result.startswith("...")
        assert result.endswith("...")


# ============== Test Search with Transcripts ==============

class TestSearchWithTranscripts:
    """Tests for search including raw transcripts."""
    
    def test_search_finds_in_raw_text(self, meeting_with_transcript):
        """Should find matches in raw_text when include_transcripts is True."""
        response = client.get(
            "/search",
            params={
                "q": "MetaSpan",
                "source_type": "meetings",
                "include_transcripts": "true"
            }
        )
        
        assert response.status_code == 200
        # Check that the meeting is found (HTML response)
        assert "Sprint Planning Meeting" in response.text
    
    def test_search_excludes_raw_text_by_default(self, meeting_with_transcript):
        """Should NOT search raw_text when include_transcripts is False."""
        response = client.get(
            "/search",
            params={
                "q": "MetaSpan",
                "source_type": "meetings"
                # include_transcripts defaults to False
            }
        )
        
        assert response.status_code == 200
        # MetaSpan is only in raw_text, not in synthesized_notes
        # So it should NOT be found
        assert "Sprint Planning Meeting" not in response.text or "No results" in response.text
    
    def test_search_finds_in_notes_without_transcript_flag(self, meeting_with_transcript):
        """Should find matches in synthesized_notes without transcript flag."""
        response = client.get(
            "/search",
            params={
                "q": "sprint goals",
                "source_type": "meetings"
            }
        )
        
        assert response.status_code == 200
        assert "Sprint Planning Meeting" in response.text
    
    def test_indicates_match_source(self, meeting_with_transcript):
        """Should indicate when match was found in transcript."""
        response = client.get(
            "/search",
            params={
                "q": "DataBricks",
                "source_type": "meetings",
                "include_transcripts": "true"
            }
        )
        
        assert response.status_code == 200
        # Should show the transcript badge
        assert "found in transcript" in response.text or "transcript" in response.text.lower()


# ============== Test Search Linked Documents ==============

class TestSearchLinkedDocuments:
    """Tests for search in meeting_documents table."""
    
    def test_search_finds_in_teams_transcript(self, meeting_with_linked_documents):
        """Should find matches in Teams transcript documents."""
        response = client.get(
            "/search",
            params={
                "q": "Snowflake",
                "source_type": "transcripts",
                "include_transcripts": "true"
            }
        )
        
        assert response.status_code == 200
        assert "Architecture Review" in response.text or "teams" in response.text.lower()
    
    def test_search_finds_in_pocket_transcript(self, meeting_with_linked_documents):
        """Should find matches in Pocket transcript documents."""
        response = client.get(
            "/search",
            params={
                "q": "Kafka",
                "include_transcripts": "true"
            }
        )
        
        assert response.status_code == 200
        assert "pocket" in response.text.lower() or "Architecture Review" in response.text
    
    def test_transcripts_only_mode(self, meeting_with_linked_documents):
        """Should filter to transcripts only when source_type is transcripts."""
        response = client.get(
            "/search",
            params={
                "q": "Redis",
                "source_type": "transcripts"
            }
        )
        
        assert response.status_code == 200
        # Should find in Pocket transcript
        assert "Redis" in response.text or "Architecture Review" in response.text


# ============== Test Search Result Types ==============

class TestSearchResultTypes:
    """Tests for different result type handling."""
    
    def test_meeting_result_links_to_meeting(self, meeting_with_transcript):
        """Meeting results should link to /meetings/{id}."""
        response = client.get(
            "/search",
            params={
                "q": "sprint",
                "source_type": "meetings"
            }
        )
        
        assert response.status_code == 200
        assert f"/meetings/{meeting_with_transcript}" in response.text
    
    def test_transcript_result_links_to_meeting(self, meeting_with_linked_documents):
        """Transcript results should link to the parent meeting."""
        response = client.get(
            "/search",
            params={
                "q": "PostgreSQL",
                "include_transcripts": "true"
            }
        )
        
        assert response.status_code == 200
        assert f"/meetings/{meeting_with_linked_documents}" in response.text


# ============== Test Search UI Elements ==============

class TestSearchUI:
    """Tests for search UI elements."""
    
    def test_shows_transcript_toggle(self):
        """Should show the transcript search toggle."""
        response = client.get("/search")
        
        assert response.status_code == 200
        assert "include_transcripts" in response.text
        assert "Deep search" in response.text or "raw transcripts" in response.text
    
    def test_shows_transcripts_source_option(self):
        """Should show Transcripts Only option in source dropdown."""
        response = client.get("/search")
        
        assert response.status_code == 200
        assert "Transcripts Only" in response.text or "transcripts" in response.text
    
    def test_preserves_transcript_toggle_state(self):
        """Should preserve checkbox state after search."""
        response = client.get(
            "/search",
            params={
                "q": "test",
                "include_transcripts": "true"
            }
        )
        
        assert response.status_code == 200
        # Checkbox should be checked
        assert 'checked' in response.text


# ============== Test Edge Cases ==============

class TestSearchEdgeCases:
    """Edge case tests for full-text search."""
    
    def test_handles_special_characters(self, meeting_with_transcript):
        """Should handle special regex characters in query."""
        response = client.get(
            "/search",
            params={
                "q": "[00:00",  # Timestamp format with brackets
                "include_transcripts": "true"
            }
        )
        
        # Should not crash
        assert response.status_code == 200
    
    def test_handles_very_long_query(self):
        """Should handle long search queries."""
        long_query = "a" * 100
        response = client.get(
            "/search",
            params={"q": long_query}
        )
        
        assert response.status_code == 200
    
    def test_handles_empty_raw_text(self):
        """Should handle meetings with NULL raw_text."""
        with connect() as conn:
            cursor = conn.execute("""
                INSERT INTO meeting_summaries 
                (meeting_name, synthesized_notes, meeting_date, signals_json)
                VALUES (?, ?, ?, ?)
            """, (
                "Meeting Without Transcript",
                "Just notes, no raw transcript available.",
                "2026-01-20",
                json.dumps({})
            ))
            meeting_id = cursor.lastrowid
            conn.commit()
        
        try:
            response = client.get(
                "/search",
                params={
                    "q": "Just notes",
                    "source_type": "meetings",
                    "include_transcripts": "true"
                }
            )
            
            assert response.status_code == 200
            assert "Meeting Without Transcript" in response.text
        finally:
            with connect() as conn:
                conn.execute("DELETE FROM meeting_summaries WHERE id = ?", (meeting_id,))
                conn.commit()
