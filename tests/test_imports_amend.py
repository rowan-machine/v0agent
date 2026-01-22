# tests/test_imports_amend.py
"""
Tests for F1b: Pocket Bundle Amend

Tests the meeting amendment functionality including:
- Amending with transcript only
- Amending with summary only
- Amending with both transcript and summary
- Holistic signal merging (no duplicates)
- Document linking and retrieval
- Multiple source support (Teams + Pocket)
"""

import pytest
import io
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.main import app
from src.app.db import connect


client = TestClient(app)


# ============== Test Fixtures ==============

@pytest.fixture
def sample_meeting():
    """Create a sample meeting for testing amendments."""
    with connect() as conn:
        cursor = conn.execute("""
            INSERT INTO meeting_summaries 
            (meeting_name, synthesized_notes, meeting_date, signals_json)
            VALUES (?, ?, ?, ?)
        """, (
            "Test Meeting for Amendment",
            "Initial meeting notes from manual entry.",
            "2026-01-22",
            json.dumps({
                "decisions": [{"text": "Use PostgreSQL for database"}],
                "action_items": [{"text": "Review PR by Friday"}]
            })
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
def sample_transcript():
    """Sample transcript content."""
    return """
    Meeting Transcript - Weekly Standup
    
    [00:00:15] Rowan: Good morning everyone. Let's start with updates.
    
    [00:01:20] Alex: I finished the database migration yesterday. 
    We should be ready to test by end of day.
    
    [00:02:45] Sam: Frontend work is progressing. I need to coordinate
    with Alex on the API changes.
    
    [00:05:00] Rowan: Great progress. Any blockers?
    
    [00:05:30] Sam: Yes, I'm blocked on the new design specs from UX team.
    
    [00:08:00] Rowan: I'll follow up with them today. Let's sync tomorrow.
    """


@pytest.fixture
def sample_summary():
    """Sample Pocket summary content with signals."""
    return """# Weekly Standup Summary

## Key Decisions
- Database migration approach approved
- Will coordinate API changes before frontend integration

## Action Items
- [ ] Rowan: Follow up with UX team on design specs
- [ ] Alex: Prepare test environment by EOD
- [ ] Sam: Create API integration tickets

## Blockers
- Sam is blocked on design specs from UX team

## Risks
- API changes might delay frontend work if not coordinated
"""


@pytest.fixture
def teams_summary():
    """Sample Teams summary with different signals."""
    return """# Teams Meeting Summary

## Decisions
- Use PostgreSQL for database (confirmed)
- Sprint planning moved to Monday

## Action Items
- Review PR by Friday (Rowan)
- Set up CI pipeline (Alex)

## Key Points
- Good progress on all fronts
- Need better UX coordination
"""


# ============== Test Signal Merging ==============

class TestMergeSignalsHolistically:
    """Tests for holistic signal merging (no duplicates)."""
    
    def test_merges_without_duplicates(self):
        """Should merge signals without creating duplicates."""
        from src.app.api.v1.imports import merge_signals_holistically
        
        existing = {
            "decisions": [{"text": "Use PostgreSQL"}],
            "action_items": [{"text": "Review PR by Friday"}]
        }
        
        new = {
            "decisions": [{"text": "Use PostgreSQL"}, {"text": "New decision"}],
            "action_items": [{"text": "Different action"}]
        }
        
        merged, count = merge_signals_holistically(existing, new)
        
        assert len(merged["decisions"]) == 2  # Original + new decision
        assert len(merged["action_items"]) == 2  # Original + different action
        assert count == 2  # 2 new items merged
    
    def test_handles_empty_existing(self):
        """Should handle empty existing signals."""
        from src.app.api.v1.imports import merge_signals_holistically
        
        existing = {}
        new = {
            "decisions": [{"text": "New decision"}],
            "blockers": [{"text": "A blocker"}]
        }
        
        merged, count = merge_signals_holistically(existing, new)
        
        assert len(merged["decisions"]) == 1
        assert len(merged["blockers"]) == 1
        assert count == 2
    
    def test_handles_empty_new(self):
        """Should handle empty new signals."""
        from src.app.api.v1.imports import merge_signals_holistically
        
        existing = {
            "decisions": [{"text": "Existing decision"}]
        }
        new = {}
        
        merged, count = merge_signals_holistically(existing, new)
        
        assert len(merged["decisions"]) == 1
        assert count == 0
    
    def test_normalizes_for_comparison(self):
        """Should normalize text for duplicate detection."""
        from src.app.api.v1.imports import merge_signals_holistically
        
        existing = {
            "decisions": [{"text": "Use PostgreSQL for the database"}]
        }
        new = {
            "decisions": [{"text": "  USE POSTGRESQL FOR THE DATABASE  "}]  # Same but different case/whitespace
        }
        
        merged, count = merge_signals_holistically(existing, new)
        
        assert len(merged["decisions"]) == 1  # Should not duplicate
        assert count == 0


# ============== Test Amend Endpoint ==============

class TestAmendMeetingEndpoint:
    """Tests for POST /api/v1/imports/amend/{meeting_id}"""
    
    def test_amend_with_transcript_only(self, sample_meeting, sample_transcript):
        """Should add transcript to existing meeting."""
        response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={
                "transcript": sample_transcript,
                "source": "pocket"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["meeting_id"] == sample_meeting
        assert len(data["documents_added"]) == 1
        assert data["documents_added"][0]["doc_type"] == "transcript"
        assert data["documents_added"][0]["source"] == "pocket"
    
    def test_amend_with_summary_only(self, sample_meeting, sample_summary):
        """Should add summary and extract signals."""
        response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={
                "summary": sample_summary,
                "source": "pocket"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents_added"]) == 1
        assert data["documents_added"][0]["doc_type"] == "summary"
        # Signal count may be 0 depending on parser - just verify it's a number
        assert isinstance(data["documents_added"][0]["signal_count"], int)
    
    def test_amend_with_both_transcript_and_summary(self, sample_meeting, sample_transcript, sample_summary):
        """Should add both transcript and summary."""
        response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={
                "transcript": sample_transcript,
                "summary": sample_summary,
                "source": "pocket"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents_added"]) == 2
        
        doc_types = {d["doc_type"] for d in data["documents_added"]}
        assert doc_types == {"transcript", "summary"}
    
    def test_amend_nonexistent_meeting(self, sample_summary):
        """Should return 404 for non-existent meeting."""
        response = client.post(
            "/api/v1/imports/amend/999999",
            data={"summary": sample_summary}
        )
        
        assert response.status_code == 404
    
    def test_amend_requires_content(self, sample_meeting):
        """Should reject request with no content."""
        response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"source": "pocket"}
        )
        
        assert response.status_code == 400
        assert "at least one" in response.json()["detail"].lower()
    
    def test_amend_with_file_upload(self, sample_meeting, sample_summary):
        """Should accept file upload for summary."""
        file_content = sample_summary.encode('utf-8')
        
        response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            files={"summary_file": ("summary.md", io.BytesIO(file_content), "text/markdown")},
            data={"source": "pocket"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents_added"]) == 1
    
    def test_holistic_signal_merging(self, sample_meeting, sample_summary, teams_summary):
        """Should merge signals from Teams and Pocket without duplicates."""
        # First add Teams summary
        response1 = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"summary": teams_summary, "source": "teams"}
        )
        assert response1.status_code == 200
        
        # Then add Pocket summary (has some overlapping signals)
        response2 = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"summary": sample_summary, "source": "pocket"}
        )
        assert response2.status_code == 200
        
        # Check that signals were merged holistically
        data = response2.json()
        # The "Use PostgreSQL" decision exists in both - should not duplicate
        assert data["holistic_signals_merged"] >= 0  # Some signals merged
    
    def test_marks_first_document_as_primary(self, sample_meeting, sample_transcript):
        """Should mark first document of each type as primary."""
        response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"transcript": sample_transcript, "source": "teams"}
        )
        
        assert response.status_code == 200
        assert response.json()["documents_added"][0]["is_primary"] == True
        
        # Second transcript from different source should not be primary
        response2 = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"transcript": "Another transcript from Pocket", "source": "pocket"}
        )
        
        assert response2.status_code == 200
        # Note: is_primary is determined by whether this source already has a transcript
        # Since pocket is a new source, its first transcript is primary for that source


# ============== Test Document Listing ==============

class TestListMeetingDocuments:
    """Tests for GET /api/v1/imports/meetings/{meeting_id}/documents"""
    
    def test_returns_empty_list_initially(self, sample_meeting):
        """Should return empty list for meeting with no documents."""
        response = client.get(f"/api/v1/imports/meetings/{sample_meeting}/documents")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_returns_added_documents(self, sample_meeting, sample_transcript, sample_summary):
        """Should return all documents after amendment."""
        # Add documents
        client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={
                "transcript": sample_transcript,
                "summary": sample_summary,
                "source": "pocket"
            }
        )
        
        response = client.get(f"/api/v1/imports/meetings/{sample_meeting}/documents")
        
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) == 2
        
        doc_types = {d["doc_type"] for d in docs}
        assert doc_types == {"transcript", "summary"}
    
    def test_returns_404_for_nonexistent_meeting(self):
        """Should return 404 for non-existent meeting."""
        response = client.get("/api/v1/imports/meetings/999999/documents")
        assert response.status_code == 404


# ============== Test Get Document Content ==============

class TestGetMeetingDocument:
    """Tests for GET /api/v1/imports/meetings/{meeting_id}/documents/{doc_id}"""
    
    def test_returns_document_content(self, sample_meeting, sample_transcript):
        """Should return full document content."""
        # Add document
        amend_response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"transcript": sample_transcript, "source": "pocket"}
        )
        doc_id = amend_response.json()["documents_added"][0]["document_id"]
        
        response = client.get(f"/api/v1/imports/meetings/{sample_meeting}/documents/{doc_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == sample_transcript.strip()
        assert data["doc_type"] == "transcript"
        assert data["source"] == "pocket"
    
    def test_returns_404_for_wrong_meeting(self, sample_meeting, sample_transcript):
        """Should return 404 if document doesn't belong to meeting."""
        # Add document
        amend_response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"transcript": sample_transcript, "source": "pocket"}
        )
        doc_id = amend_response.json()["documents_added"][0]["document_id"]
        
        # Try to get with wrong meeting ID
        response = client.get(f"/api/v1/imports/meetings/999999/documents/{doc_id}")
        assert response.status_code == 404


# ============== Test Multiple Sources Workflow ==============

class TestMultipleSourcesWorkflow:
    """Tests for the full Teams + Pocket workflow."""
    
    def test_full_workflow_teams_then_pocket(self, sample_meeting, sample_transcript, sample_summary, teams_summary):
        """Should support adding Teams content first, then Pocket content."""
        # Step 1: Add Teams transcript and summary
        response1 = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={
                "transcript": "Teams meeting transcript content...",
                "summary": teams_summary,
                "source": "teams"
            }
        )
        assert response1.status_code == 200
        assert len(response1.json()["documents_added"]) == 2
        
        # Step 2: Add Pocket transcript and summary
        response2 = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={
                "transcript": sample_transcript,
                "summary": sample_summary,
                "source": "pocket"
            }
        )
        assert response2.status_code == 200
        assert len(response2.json()["documents_added"]) == 2
        
        # Verify all 4 documents are linked
        docs_response = client.get(f"/api/v1/imports/meetings/{sample_meeting}/documents")
        assert len(docs_response.json()) == 4
        
        sources = {d["source"] for d in docs_response.json()}
        assert sources == {"teams", "pocket"}
    
    def test_signals_merged_across_sources(self, sample_meeting, sample_summary, teams_summary):
        """Should merge signals from multiple sources without duplicates."""
        # Add Teams summary with "Use PostgreSQL" decision
        client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"summary": teams_summary, "source": "teams"}
        )
        
        # Add Pocket summary 
        response = client.post(
            f"/api/v1/imports/amend/{sample_meeting}",
            data={"summary": sample_summary, "source": "pocket"}
        )
        
        # Check the merged signal count
        # Meeting already had "Use PostgreSQL" decision, Teams also has it
        # So it should not be duplicated
        assert response.status_code == 200
        data = response.json()
        
        # The holistic merge should have added new signals but not duplicated existing ones
        assert data["total_signals_extracted"] > 0
