# tests/test_imports_mindmap.py
"""
Tests for F1c: Mindmap Screenshot Ingest

Tests the mindmap analysis and pattern recognition functionality including:
- Vision API integration
- Structure extraction
- Pattern/insight identification
- DIKW item creation
- Meeting linking
"""

import pytest
import io
import json
import base64
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
    """Create a sample meeting for testing mindmap ingestion."""
    with connect() as conn:
        cursor = conn.execute("""
            INSERT INTO meeting_summaries 
            (meeting_name, synthesized_notes, meeting_date, signals_json)
            VALUES (?, ?, ?, ?)
        """, (
            "PBM Pipeline Planning Meeting",
            "Discussion about Rx claim reallocation and DMP pipeline.",
            "2026-01-22",
            json.dumps({"decisions": [], "action_items": []})
        ))
        meeting_id = cursor.lastrowid
        conn.commit()
    
    yield meeting_id
    
    # Cleanup
    with connect() as conn:
        conn.execute("DELETE FROM meeting_documents WHERE meeting_id = ?", (meeting_id,))
        conn.execute("DELETE FROM dikw_items WHERE meeting_id = ?", (meeting_id,))
        conn.execute("DELETE FROM meeting_summaries WHERE id = ?", (meeting_id,))
        conn.commit()


@pytest.fixture
def mock_vision_response():
    """Mock response from GPT-4 Vision API."""
    return json.dumps({
        "root_topic": "PBM Rx claim reallocation and DMP pipeline planning",
        "structure": {
            "text": "PBM Rx claim reallocation and DMP pipeline planning",
            "node_type": "root",
            "children": [
                {
                    "text": "Stakeholders and collaboration dynamics",
                    "node_type": "category",
                    "children": [
                        {"text": "Primary stakeholders: Jonathan, Rowan, James, Nathan, Kristen, Jeff", "node_type": "item", "children": []},
                        {"text": "Cross-functional collaboration between data engineers and PBM-focused developers", "node_type": "item", "children": []}
                    ]
                },
                {
                    "text": "Technical system and process context",
                    "node_type": "category",
                    "children": [
                        {"text": "Reallocation DAG for PBM formulary mapping and claims repricing", "node_type": "item", "children": []},
                        {"text": "Integration of MetaSpan pricing data and enrichment tasks", "node_type": "item", "children": []}
                    ]
                }
            ]
        },
        "entities": [
            "Jonathan", "Rowan", "James", "Nathan", "Kristen", "Jeff",
            "DMP v1", "DMP v2", "MetaSpan", "PBM"
        ],
        "relationships": [
            {"from": "data engineers", "to": "PBM developers", "type": "collaborates_with"},
            {"from": "DMP v1", "to": "DMP v2", "type": "migrates_to"},
            {"from": "MetaSpan", "to": "pricing data", "type": "provides"}
        ],
        "patterns": [
            "Cross-functional collaboration required",
            "Technical migration from v1 to v2",
            "Stakeholder alignment across teams",
            "Data integration complexity"
        ],
        "insights": [
            "The project requires coordination between multiple stakeholders with different domains",
            "Pipeline consolidation from DMP v1 to v2 is a key technical focus",
            "Configuration management across PBM JSON files needs attention",
            "Dual repricing outputs suggest need for comparison tooling"
        ],
        "dikw_candidates": [
            {
                "content": "Cross-functional collaboration between data engineers and PBM developers is essential for this project",
                "level": "knowledge",
                "category": "relationship"
            },
            {
                "content": "DMP v2 pipeline consolidation is the strategic direction",
                "level": "information",
                "category": "decision"
            },
            {
                "content": "When dealing with dual data sources (e.g., repricing outputs), build comparison tooling early",
                "level": "wisdom",
                "category": "principle"
            }
        ]
    })


@pytest.fixture
def sample_image_bytes():
    """Create a minimal valid PNG image for testing."""
    # Minimal 1x1 pixel PNG
    png_header = b'\x89PNG\r\n\x1a\n'
    ihdr = b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    idat = b'\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
    iend = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    return png_header + ihdr + idat + iend


# ============== Test Parse Mindmap Analysis ==============

class TestParseMindmapAnalysis:
    """Tests for parsing vision API responses."""
    
    def test_parses_clean_json(self, mock_vision_response):
        """Should parse clean JSON response."""
        from src.app.api.v1.imports import parse_mindmap_analysis
        
        result = parse_mindmap_analysis(mock_vision_response)
        
        assert result["root_topic"] == "PBM Rx claim reallocation and DMP pipeline planning"
        assert len(result["entities"]) > 0
        assert len(result["patterns"]) > 0
    
    def test_handles_markdown_wrapped_json(self, mock_vision_response):
        """Should handle JSON wrapped in markdown code blocks."""
        from src.app.api.v1.imports import parse_mindmap_analysis
        
        wrapped = f"```json\n{mock_vision_response}\n```"
        result = parse_mindmap_analysis(wrapped)
        
        assert result["root_topic"] == "PBM Rx claim reallocation and DMP pipeline planning"
    
    def test_handles_invalid_json(self):
        """Should return minimal structure for invalid JSON."""
        from src.app.api.v1.imports import parse_mindmap_analysis
        
        result = parse_mindmap_analysis("This is not JSON at all")
        
        assert result["root_topic"] == "Unknown"
        assert len(result["insights"]) > 0  # Should include raw response
    
    def test_handles_empty_response(self):
        """Should handle empty response."""
        from src.app.api.v1.imports import parse_mindmap_analysis
        
        result = parse_mindmap_analysis("")
        
        assert result["root_topic"] == "Unknown"


# ============== Test Mindmap Ingest Endpoint ==============

class TestMindmapIngestEndpoint:
    """Tests for POST /api/v1/imports/mindmap/{meeting_id}"""
    
    def test_successful_mindmap_upload(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should successfully ingest a mindmap screenshot."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")},
                data={"source": "pocket"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["meeting_id"] == sample_meeting
            assert "document_id" in data
            assert data["analysis"]["root_topic"] == "PBM Rx claim reallocation and DMP pipeline planning"
    
    def test_extracts_entities(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should extract entities from mindmap."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            assert response.status_code == 200
            entities = response.json()["analysis"]["entities"]
            assert "Rowan" in entities
            assert "MetaSpan" in entities
    
    def test_extracts_relationships(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should extract relationships between entities."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            assert response.status_code == 200
            relationships = response.json()["analysis"]["relationships"]
            assert len(relationships) > 0
            assert any(r["type"] == "collaborates_with" for r in relationships)
    
    def test_identifies_patterns(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should identify patterns from mindmap structure."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            assert response.status_code == 200
            patterns = response.json()["analysis"]["patterns"]
            assert "Cross-functional collaboration required" in patterns
    
    def test_generates_insights(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should generate actionable insights."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            assert response.status_code == 200
            insights = response.json()["analysis"]["insights"]
            assert len(insights) >= 3  # At least 3 insights
    
    def test_creates_dikw_items(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should create DIKW items from mindmap analysis."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            assert response.status_code == 200
            assert response.json()["dikw_items_created"] >= 1
    
    def test_rejects_nonexistent_meeting(self, sample_image_bytes, mock_vision_response):
        """Should return 404 for non-existent meeting."""
        response = client.post(
            "/api/v1/imports/mindmap/999999",
            files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
        )
        
        assert response.status_code == 404
    
    def test_rejects_unsupported_file_type(self, sample_meeting):
        """Should reject non-image file types."""
        response = client.post(
            f"/api/v1/imports/mindmap/{sample_meeting}",
            files={"mindmap": ("document.pdf", io.BytesIO(b"not an image"), "application/pdf")}
        )
        
        assert response.status_code == 400
        assert "Unsupported image type" in response.json()["detail"]
    
    def test_supports_jpeg_format(self, sample_meeting, mock_vision_response):
        """Should support JPEG format."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            # Minimal JPEG (not valid but enough for filename check)
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")}
            )
            
            # Will fail at vision API but should pass file type validation
            # Mock ensures it succeeds
            assert response.status_code == 200


# ============== Test List Mindmaps Endpoint ==============

class TestListMindmapsEndpoint:
    """Tests for GET /api/v1/imports/meetings/{meeting_id}/mindmaps"""
    
    def test_returns_empty_list_initially(self, sample_meeting):
        """Should return empty list for meeting with no mindmaps."""
        response = client.get(f"/api/v1/imports/meetings/{sample_meeting}/mindmaps")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_returns_mindmaps_after_upload(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should return mindmaps after upload."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            # Upload mindmap
            client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")},
                data={"source": "pocket"}
            )
        
        # List mindmaps
        response = client.get(f"/api/v1/imports/meetings/{sample_meeting}/mindmaps")
        
        assert response.status_code == 200
        mindmaps = response.json()
        assert len(mindmaps) == 1
        assert mindmaps[0]["source"] == "pocket"
        assert mindmaps[0]["root_topic"] == "PBM Rx claim reallocation and DMP pipeline planning"
        assert mindmaps[0]["pattern_count"] > 0
    
    def test_returns_404_for_nonexistent_meeting(self):
        """Should return 404 for non-existent meeting."""
        response = client.get("/api/v1/imports/meetings/999999/mindmaps")
        assert response.status_code == 404


# ============== Test DIKW Integration ==============

class TestDIKWIntegration:
    """Tests for DIKW item creation from mindmaps."""
    
    def test_creates_dikw_at_correct_levels(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should create DIKW items at appropriate levels."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
        
        # Check DIKW items were created
        with connect() as conn:
            items = conn.execute("""
                SELECT level, content, source_type, tags
                FROM dikw_items
                WHERE meeting_id = ?
            """, (sample_meeting,)).fetchall()
        
        assert len(items) >= 1
        levels = {item['level'] for item in items}
        # Should have items at multiple levels
        assert 'knowledge' in levels or 'information' in levels or 'wisdom' in levels
    
    def test_dikw_items_link_to_meeting(self, sample_meeting, sample_image_bytes, mock_vision_response):
        """Should link DIKW items to the source meeting."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = mock_vision_response
            
            client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
        
        with connect() as conn:
            items = conn.execute("""
                SELECT meeting_id, source_type
                FROM dikw_items
                WHERE meeting_id = ?
            """, (sample_meeting,)).fetchall()
        
        for item in items:
            assert item['meeting_id'] == sample_meeting
            assert item['source_type'] == 'mindmap'


# ============== Test Edge Cases ==============

class TestMindmapEdgeCases:
    """Edge case tests for mindmap processing."""
    
    def test_handles_vision_api_failure(self, sample_meeting, sample_image_bytes):
        """Should handle vision API failures gracefully."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.side_effect = Exception("API rate limit exceeded")
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            assert response.status_code == 500
            assert "Vision analysis failed" in response.json()["detail"]
    
    def test_handles_malformed_vision_response(self, sample_meeting, sample_image_bytes):
        """Should handle malformed vision API response."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = "This is not JSON but some text description"
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            # Should still succeed but with minimal analysis
            assert response.status_code == 200
            data = response.json()
            assert data["analysis"]["root_topic"] == "Unknown"
            # Raw response should be preserved in insights
            assert len(data["analysis"]["insights"]) > 0
    
    def test_handles_empty_dikw_candidates(self, sample_meeting, sample_image_bytes):
        """Should handle response with no DIKW candidates."""
        with patch('src.app.api.v1.imports.analyze_image') as mock_analyze:
            mock_analyze.return_value = json.dumps({
                "root_topic": "Simple Meeting",
                "structure": {"text": "Simple Meeting", "children": [], "node_type": "root"},
                "entities": [],
                "relationships": [],
                "patterns": [],
                "insights": ["A simple insight"],
                "dikw_candidates": []
            })
            
            response = client.post(
                f"/api/v1/imports/mindmap/{sample_meeting}",
                files={"mindmap": ("mindmap.png", io.BytesIO(sample_image_bytes), "image/png")}
            )
            
            assert response.status_code == 200
            assert response.json()["dikw_items_created"] == 0
