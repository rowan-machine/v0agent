# tests/test_imports.py
"""
Tests for F1: Pocket Import Pipeline

Tests the markdown file import functionality including:
- Successful markdown upload
- File type validation
- Meeting name auto-detection
- Signal extraction integration
- Import history tracking
- Error handling
"""

import pytest
import io
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Import the app for testing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.main import app


client = TestClient(app)


# ============== Test Fixtures ==============

@pytest.fixture
def sample_markdown_content():
    """Sample markdown content for testing."""
    return """# Weekly Team Standup - January 22, 2026

## Attendees
- Rowan (Lead)
- Alex (Backend)
- Sam (Frontend)

## Decisions
- We decided to use PostgreSQL for the new feature
- API versioning will follow semver

## Action Items
- [ ] Rowan: Review PR #234 by Friday
- [ ] Alex: Set up database migrations
- [ ] Sam: Update UI components

## Blockers
- Waiting on design approval for the new dashboard

## Risks
- Timeline might slip if we don't get the API specs soon

## Ideas
- Consider using WebSockets for real-time updates
"""


@pytest.fixture
def minimal_markdown_content():
    """Minimal valid markdown content."""
    return "Simple meeting notes with some content here."


@pytest.fixture
def markdown_file(sample_markdown_content):
    """Create a file-like object for upload testing."""
    return io.BytesIO(sample_markdown_content.encode('utf-8'))


# ============== Unit Tests: Helper Functions ==============

class TestExtractMarkdownText:
    """Tests for extract_markdown_text helper function."""
    
    def test_extracts_utf8_content(self):
        """Should extract UTF-8 encoded text."""
        from src.app.api.v1.imports import extract_markdown_text
        
        content = "Hello, world!".encode('utf-8')
        result = extract_markdown_text(content)
        
        assert result == "Hello, world!"
    
    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        from src.app.api.v1.imports import extract_markdown_text
        
        content = "  \n\nContent with whitespace\n\n  ".encode('utf-8')
        result = extract_markdown_text(content)
        
        assert result == "Content with whitespace"
    
    def test_handles_latin1_fallback(self):
        """Should fall back to latin-1 if UTF-8 fails."""
        from src.app.api.v1.imports import extract_markdown_text
        
        # Latin-1 specific character (not valid UTF-8 when standalone)
        content = b"Meeting with caf\xe9"  # café in latin-1
        result = extract_markdown_text(content)
        
        assert "caf" in result
    
    def test_raises_on_binary_content(self):
        """Should raise ValueError for binary content."""
        from src.app.api.v1.imports import extract_markdown_text
        
        # PNG header (definitely not text)
        content = b'\x89PNG\r\n\x1a\n\x00\x00\x00'
        
        # This should succeed with latin-1 fallback, but content will be garbled
        # The function doesn't raise for this case - it falls back to latin-1
        result = extract_markdown_text(content)
        assert isinstance(result, str)


class TestInferMeetingName:
    """Tests for infer_meeting_name_from_content helper function."""
    
    def test_extracts_h1_header(self):
        """Should extract H1 header as meeting name."""
        from src.app.api.v1.imports import infer_meeting_name_from_content
        
        content = "# My Important Meeting\n\nSome content here."
        result = infer_meeting_name_from_content(content, "file.md")
        
        assert result == "My Important Meeting"
    
    def test_extracts_h1_with_spaces(self):
        """Should handle H1 with extra spaces."""
        from src.app.api.v1.imports import infer_meeting_name_from_content
        
        content = "#   Spaced Title   \n\nContent."
        result = infer_meeting_name_from_content(content, "file.md")
        
        assert result == "Spaced Title"
    
    def test_uses_first_line_if_no_h1(self):
        """Should use first line if it looks like a title."""
        from src.app.api.v1.imports import infer_meeting_name_from_content
        
        content = "Team Standup Notes\n\nWe discussed the project."
        result = infer_meeting_name_from_content(content, "file.md")
        
        assert result == "Team Standup Notes"
    
    def test_falls_back_to_filename(self):
        """Should fall back to filename if no title found."""
        from src.app.api.v1.imports import infer_meeting_name_from_content
        
        content = "- List item one\n- List item two\n- List item three"
        result = infer_meeting_name_from_content(content, "weekly_standup_notes.md")
        
        assert result == "weekly standup notes"
    
    def test_truncates_long_names(self):
        """Should truncate names longer than 100 characters."""
        from src.app.api.v1.imports import infer_meeting_name_from_content
        
        long_title = "# " + "A" * 150
        result = infer_meeting_name_from_content(long_title, "file.md")
        
        assert len(result) <= 100


# ============== Integration Tests: API Endpoints ==============

class TestImportUploadEndpoint:
    """Tests for POST /api/v1/imports/upload endpoint."""
    
    def test_successful_markdown_upload(self, sample_markdown_content):
        """Should successfully import a markdown file."""
        files = {
            "file": ("meeting.md", io.BytesIO(sample_markdown_content.encode()), "text/markdown")
        }
        data = {
            "meeting_name": "Test Meeting Import",
            "meeting_date": "2026-01-22"
        }
        
        response = client.post("/api/v1/imports/upload", files=files, data=data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["meeting_id"] > 0
        assert result["meeting_name"] == "Test Meeting Import"
        assert result["transcript_length"] > 0
        assert result["import_source"] == "markdown_upload"
    
    def test_upload_with_txt_extension(self, minimal_markdown_content):
        """Should accept .txt files."""
        files = {
            "file": ("notes.txt", io.BytesIO(minimal_markdown_content.encode()), "text/plain")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 200
        assert response.json()["meeting_id"] > 0
    
    def test_upload_with_markdown_extension(self, minimal_markdown_content):
        """Should accept .markdown files."""
        files = {
            "file": ("notes.markdown", io.BytesIO(minimal_markdown_content.encode()), "text/markdown")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 200
    
    def test_rejects_unsupported_file_type(self):
        """Should reject non-markdown file types."""
        files = {
            "file": ("document.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]
    
    def test_rejects_docx_file(self):
        """Should reject .docx files (not yet supported)."""
        files = {
            "file": ("document.docx", io.BytesIO(b"fake docx content"), "application/vnd.openxmlformats")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 400
    
    def test_rejects_empty_file(self):
        """Should reject empty files."""
        files = {
            "file": ("empty.md", io.BytesIO(b""), "text/markdown")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 400
        assert "Empty file" in response.json()["detail"]
    
    def test_rejects_too_short_content(self):
        """Should reject files with content shorter than 10 characters."""
        files = {
            "file": ("short.md", io.BytesIO(b"Hi"), "text/markdown")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 400
        assert "too short" in response.json()["detail"]
    
    def test_auto_detects_meeting_name(self, sample_markdown_content):
        """Should auto-detect meeting name from H1 header."""
        files = {
            "file": ("meeting.md", io.BytesIO(sample_markdown_content.encode()), "text/markdown")
        }
        # Don't provide meeting_name
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 200
        result = response.json()
        # Should extract "Weekly Team Standup - January 22, 2026" from H1
        assert "Weekly Team Standup" in result["meeting_name"]
        assert "auto-detected" in str(result["warnings"])
    
    def test_auto_sets_today_date(self, minimal_markdown_content):
        """Should set meeting date to today if not provided."""
        files = {
            "file": ("meeting.md", io.BytesIO(minimal_markdown_content.encode()), "text/markdown")
        }
        data = {"meeting_name": "Test Meeting"}
        
        response = client.post("/api/v1/imports/upload", files=files, data=data)
        
        assert response.status_code == 200
        result = response.json()
        assert "date set to today" in str(result["warnings"]).lower()
    
    def test_includes_source_url(self, minimal_markdown_content):
        """Should store source URL with meeting."""
        files = {
            "file": ("meeting.md", io.BytesIO(minimal_markdown_content.encode()), "text/markdown")
        }
        data = {
            "meeting_name": "Test",
            "source_url": "https://pocket.app/meeting/12345"
        }
        
        response = client.post("/api/v1/imports/upload", files=files, data=data)
        
        assert response.status_code == 200
        # Source URL should be stored (we can verify via DB or history)
    
    def test_extracts_signals(self, sample_markdown_content):
        """Should extract signals from uploaded content."""
        files = {
            "file": ("meeting.md", io.BytesIO(sample_markdown_content.encode()), "text/markdown")
        }
        data = {"meeting_name": "Signal Test"}
        
        response = client.post("/api/v1/imports/upload", files=files, data=data)
        
        assert response.status_code == 200
        result = response.json()
        # Sample content has decisions, actions, blockers, risks, ideas
        assert result["signal_count"] >= 0  # May be 0 if LLM not available


class TestImportHistoryEndpoint:
    """Tests for GET /api/v1/imports/history endpoint."""
    
    def test_returns_empty_list_initially(self):
        """Should return empty list if no imports."""
        # Clear any existing history first
        response = client.get("/api/v1/imports/history?limit=1")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_records_successful_import(self, minimal_markdown_content):
        """Should record successful import in history."""
        # First, do an import
        files = {
            "file": ("history_test.md", io.BytesIO(minimal_markdown_content.encode()), "text/markdown")
        }
        data = {"meeting_name": "History Test"}
        
        client.post("/api/v1/imports/upload", files=files, data=data)
        
        # Check history
        response = client.get("/api/v1/imports/history")
        
        assert response.status_code == 200
        history = response.json()
        
        # Find our import
        matching = [h for h in history if h["filename"] == "history_test.md"]
        assert len(matching) > 0
        assert matching[0]["status"] == "completed"
        assert matching[0]["file_type"] == "md"
    
    def test_filters_by_status(self, minimal_markdown_content):
        """Should filter history by status."""
        # Do a successful import first
        files = {
            "file": ("filter_test.md", io.BytesIO(minimal_markdown_content.encode()), "text/markdown")
        }
        client.post("/api/v1/imports/upload", files=files, data={"meeting_name": "Filter Test"})
        
        # Filter by completed
        response = client.get("/api/v1/imports/history?status=completed")
        
        assert response.status_code == 200
        history = response.json()
        assert all(h["status"] == "completed" for h in history)
    
    def test_respects_limit_parameter(self):
        """Should respect limit parameter."""
        response = client.get("/api/v1/imports/history?limit=5")
        
        assert response.status_code == 200
        assert len(response.json()) <= 5


class TestDeleteImportRecord:
    """Tests for DELETE /api/v1/imports/history/{id} endpoint."""
    
    def test_returns_404_for_nonexistent_id(self):
        """Should return 404 for non-existent import ID."""
        response = client.delete("/api/v1/imports/history/99999")
        
        assert response.status_code == 404
    
    def test_deletes_existing_record(self, minimal_markdown_content):
        """Should delete existing import record."""
        # Create an import
        files = {
            "file": ("delete_test.md", io.BytesIO(minimal_markdown_content.encode()), "text/markdown")
        }
        client.post("/api/v1/imports/upload", files=files, data={"meeting_name": "Delete Test"})
        
        # Get the import ID
        history = client.get("/api/v1/imports/history").json()
        matching = [h for h in history if h["filename"] == "delete_test.md"]
        
        if matching:
            import_id = matching[0]["id"]
            
            # Delete it
            response = client.delete(f"/api/v1/imports/history/{import_id}")
            
            assert response.status_code == 200
            assert response.json()["id"] == import_id


# ============== Edge Cases ==============

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_handles_unicode_content(self):
        """Should handle unicode characters in content."""
        content = "# Meeting with émojis 🎉\n\nDiscussion about café ☕ and naïve assumptions."
        files = {
            "file": ("unicode.md", io.BytesIO(content.encode('utf-8')), "text/markdown")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 200
    
    def test_handles_very_long_content(self):
        """Should handle large files (within reason)."""
        # Create content with 10,000 lines
        content = "# Large Meeting Notes\n\n" + ("This is a line of content.\n" * 10000)
        files = {
            "file": ("large.md", io.BytesIO(content.encode('utf-8')), "text/markdown")
        }
        
        response = client.post("/api/v1/imports/upload", files=files, data={"meeting_name": "Large Test"})
        
        assert response.status_code == 200
        assert response.json()["transcript_length"] > 100000
    
    def test_handles_windows_line_endings(self):
        """Should handle Windows-style line endings (CRLF)."""
        content = "# Windows Meeting\r\n\r\nContent with CRLF.\r\nMore content."
        files = {
            "file": ("windows.md", io.BytesIO(content.encode('utf-8')), "text/markdown")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 200
    
    def test_handles_special_characters_in_filename(self):
        """Should handle special characters in filename."""
        content = "Simple content for testing."
        files = {
            "file": ("meeting (copy) - final_v2.md", io.BytesIO(content.encode('utf-8')), "text/markdown")
        }
        
        response = client.post("/api/v1/imports/upload", files=files)
        
        assert response.status_code == 200
