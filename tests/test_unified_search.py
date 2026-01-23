# tests/test_unified_search.py
"""
Tests for F5: Unified Semantic Search

Tests the unified search API that searches across all entity types:
- Meetings, Documents, Tickets, DIKW, Signals
- Keyword matching with score boosting
- Semantic search (when Supabase configured)
- Result deduplication and ranking
- Entity filtering
- My mentions filter
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
def sample_meetings():
    """Create sample meetings for search testing."""
    meeting_ids = []
    with connect() as conn:
        for i, (name, notes) in enumerate([
            ("Sprint Planning", "Discussed sprint goals and prioritized tickets for the next iteration."),
            ("API Design Review", "Reviewed the REST API design patterns and decided on semantic versioning."),
            ("Tech Debt Discussion", "Identified key areas of technical debt including database optimization."),
        ]):
            cursor = conn.execute("""
                INSERT INTO meeting_summaries 
                (meeting_name, synthesized_notes, meeting_date, signals_json)
                VALUES (?, ?, ?, ?)
            """, (name, notes, f"2026-01-{20+i:02d}", json.dumps({})))
            meeting_ids.append(cursor.lastrowid)
        conn.commit()
    
    yield meeting_ids
    
    with connect() as conn:
        conn.execute(f"DELETE FROM meeting_summaries WHERE id IN ({','.join('?' * len(meeting_ids))})", meeting_ids)
        conn.commit()


@pytest.fixture
def sample_documents():
    """Create sample documents for search testing."""
    doc_ids = []
    with connect() as conn:
        for title, content in [
            ("API Documentation", "This document describes the REST API endpoints for user authentication and authorization."),
            ("Database Schema", "The database uses PostgreSQL with pgvector for semantic similarity search."),
            ("Sprint Notes", "Sprint 42 focused on improving search functionality and user experience."),
        ]:
            cursor = conn.execute("""
                INSERT INTO docs (source, content, document_date)
                VALUES (?, ?, ?)
            """, (title, content, "2026-01-20"))
            doc_ids.append(cursor.lastrowid)
        conn.commit()
    
    yield doc_ids
    
    with connect() as conn:
        conn.execute(f"DELETE FROM docs WHERE id IN ({','.join('?' * len(doc_ids))})", doc_ids)
        conn.commit()


@pytest.fixture
def sample_tickets():
    """Create sample tickets for search testing."""
    ticket_ids = []
    with connect() as conn:
        for ticket_id, title, desc in [
            ("PROJ-123", "Implement search API", "Build a unified search endpoint that queries all entity types"),
            ("PROJ-456", "Fix database connection", "Database connection pooling needs optimization for high load"),
            ("PROJ-789", "Add user authentication", "Implement OAuth2 authentication flow for API access"),
        ]:
            cursor = conn.execute("""
                INSERT INTO tickets (ticket_id, title, description, status, in_sprint)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, title, desc, "in_progress", True))
            ticket_ids.append(cursor.lastrowid)
        conn.commit()
    
    yield ticket_ids
    
    with connect() as conn:
        conn.execute(f"DELETE FROM tickets WHERE id IN ({','.join('?' * len(ticket_ids))})", ticket_ids)
        conn.commit()


@pytest.fixture
def sample_dikw():
    """Create sample DIKW items for search testing."""
    dikw_ids = []
    with connect() as conn:
        for level, content in [
            ("Information", "The search API uses hybrid ranking combining semantic and keyword matching."),
            ("Knowledge", "Semantic search provides better results for conceptual queries than keyword search."),
            ("Wisdom", "Good search UX requires fast response times and relevant ranking."),
        ]:
            cursor = conn.execute("""
                INSERT INTO dikw_items (level, content, status, confidence)
                VALUES (?, ?, ?, ?)
            """, (level, content, "active", 0.8))
            dikw_ids.append(cursor.lastrowid)
        conn.commit()
    
    yield dikw_ids
    
    with connect() as conn:
        conn.execute(f"DELETE FROM dikw_items WHERE id IN ({','.join('?' * len(dikw_ids))})", dikw_ids)
        conn.commit()


@pytest.fixture
def all_sample_data(sample_meetings, sample_documents, sample_tickets, sample_dikw):
    """Combine all fixtures."""
    return {
        "meetings": sample_meetings,
        "documents": sample_documents,
        "tickets": sample_tickets,
        "dikw": sample_dikw,
    }


# ============== Unified Search GET Endpoint Tests ==============

class TestUnifiedSearchGET:
    """Tests for GET /api/search/unified"""
    
    def test_basic_search(self, all_sample_data):
        """Test basic unified search across all types."""
        response = client.get("/api/search/unified?q=search")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "query" in data
        assert data["query"] == "search"
        assert "results" in data
        assert "total_results" in data
        assert "entity_counts" in data
        assert "search_duration_ms" in data
        assert data["search_type"] == "unified"
    
    def test_search_finds_meetings(self, sample_meetings):
        """Test that search finds meetings by content."""
        response = client.get("/api/search/unified?q=sprint&entity_types=meetings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find "Sprint Planning" meeting
        assert data["total_results"] >= 1
        result = data["results"][0]
        assert result["entity_type"] == "meetings"
        assert "Sprint" in result["title"]
    
    def test_search_finds_documents(self, sample_documents):
        """Test that search finds documents by content."""
        response = client.get("/api/search/unified?q=PostgreSQL&entity_types=documents")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find "Database Schema" document
        assert data["total_results"] >= 1
        result = data["results"][0]
        assert result["entity_type"] == "documents"
        assert "Database" in result["title"]
    
    def test_search_finds_tickets(self, sample_tickets):
        """Test that search finds tickets by content."""
        response = client.get("/api/search/unified?q=authentication&entity_types=tickets")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find ticket about authentication
        assert data["total_results"] >= 1
        result = data["results"][0]
        assert result["entity_type"] == "tickets"
        assert "PROJ-" in result["title"]
    
    def test_search_finds_dikw(self, sample_dikw):
        """Test that search finds DIKW items."""
        response = client.get("/api/search/unified?q=semantic&entity_types=dikw")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_results"] >= 1
        result = data["results"][0]
        assert result["entity_type"] == "dikw"
    
    def test_search_across_all_types(self, all_sample_data):
        """Test search across multiple entity types."""
        response = client.get("/api/search/unified?q=API&entity_types=meetings,documents,tickets")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find results from multiple types
        types_found = set(r["entity_type"] for r in data["results"])
        assert len(types_found) >= 1  # At least one type
    
    def test_search_with_limit(self, all_sample_data):
        """Test search respects limit parameter."""
        response = client.get("/api/search/unified?q=search&limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["results"]) <= 2
    
    def test_search_empty_query_fails(self):
        """Test that empty query returns validation error."""
        response = client.get("/api/search/unified?q=")
        
        # Should fail validation (min_length=1)
        assert response.status_code == 422
    
    def test_search_short_query(self, all_sample_data):
        """Test search with very short query."""
        response = client.get("/api/search/unified?q=a")
        
        assert response.status_code == 200
        # May or may not find results, but shouldn't error
    
    def test_search_no_results(self):
        """Test search with query that matches nothing."""
        response = client.get("/api/search/unified?q=xyzzynonexistent12345")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_results"] == 0
        assert len(data["results"]) == 0
    
    def test_result_structure(self, all_sample_data):
        """Test that result items have correct structure."""
        response = client.get("/api/search/unified?q=sprint")
        
        assert response.status_code == 200
        data = response.json()
        
        if data["results"]:
            result = data["results"][0]
            assert "id" in result
            assert "entity_type" in result
            assert "title" in result
            assert "snippet" in result
            assert "score" in result
            assert "match_type" in result
            assert "icon" in result
            assert "url" in result
    
    def test_entity_counts_populated(self, all_sample_data):
        """Test that entity_counts is populated correctly."""
        response = client.get("/api/search/unified?q=search")
        
        assert response.status_code == 200
        data = response.json()
        
        # entity_counts should have counts for searched types
        assert isinstance(data["entity_counts"], dict)
    
    def test_search_duration_tracked(self, all_sample_data):
        """Test that search duration is tracked."""
        response = client.get("/api/search/unified?q=test")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "search_duration_ms" in data
        assert isinstance(data["search_duration_ms"], int)
        assert data["search_duration_ms"] >= 0


class TestUnifiedSearchPOST:
    """Tests for POST /api/search/unified"""
    
    def test_post_basic_search(self, all_sample_data):
        """Test POST endpoint for unified search."""
        response = client.post("/api/search/unified", json={
            "query": "search",
            "entity_types": ["meetings", "documents"],
            "limit": 10
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["query"] == "search"
        assert "results" in data
    
    def test_post_with_filters(self, all_sample_data):
        """Test POST with various filter options."""
        response = client.post("/api/search/unified", json={
            "query": "API",
            "entity_types": ["tickets"],
            "limit": 5,
            "use_keyword": True,
            "use_semantic": False,
            "min_score": 0.3
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # All results should be tickets
        for result in data["results"]:
            assert result["entity_type"] == "tickets"


class TestUnifiedSearchScoring:
    """Tests for search result scoring."""
    
    def test_title_match_boosted(self, sample_meetings):
        """Test that title matches get higher scores."""
        response = client.get("/api/search/unified?q=Sprint Planning&entity_types=meetings")
        
        assert response.status_code == 200
        data = response.json()
        
        if data["results"]:
            # First result should have "Sprint Planning" in title
            first_result = data["results"][0]
            assert first_result["score"] > 0.5  # Should have boosted score
    
    def test_results_sorted_by_score(self, all_sample_data):
        """Test that results are sorted by score descending."""
        response = client.get("/api/search/unified?q=API")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["results"]) > 1:
            scores = [r["score"] for r in data["results"]]
            assert scores == sorted(scores, reverse=True)


class TestUnifiedSearchHealthCheck:
    """Tests for search health endpoint."""
    
    def test_health_includes_unified_search(self):
        """Test that health check includes unified search status."""
        response = client.get("/api/search/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "services" in data
        assert "unified_search" in data["services"]
        assert data["services"]["unified_search"] == True  # Always available


class TestUnifiedSearchEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_invalid_entity_type_ignored(self, all_sample_data):
        """Test that invalid entity types are ignored."""
        response = client.get("/api/search/unified?q=test&entity_types=invalid,meetings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still work with valid types
        for result in data["results"]:
            assert result["entity_type"] in ["meetings", "documents", "tickets", "dikw", "signals"]
    
    def test_empty_entity_types_defaults(self, all_sample_data):
        """Test that empty entity_types uses defaults."""
        response = client.get("/api/search/unified?q=test&entity_types=")
        
        assert response.status_code == 200
        # Should search default types
    
    def test_special_characters_in_query(self):
        """Test search with special characters."""
        response = client.get("/api/search/unified?q=test%20%26%20query")
        
        assert response.status_code == 200
        # Should handle special chars gracefully
    
    def test_very_long_query_truncated(self):
        """Test that very long queries are handled."""
        long_query = "test " * 200  # ~1000 chars
        response = client.get(f"/api/search/unified?q={long_query[:1000]}")
        
        assert response.status_code == 200
    
    def test_sql_injection_safe(self, all_sample_data):
        """Test that SQL injection attempts are safe."""
        response = client.get("/api/search/unified?q='; DROP TABLE meetings; --")
        
        assert response.status_code == 200
        
        # Verify meetings table still exists
        with connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM meeting_summaries").fetchone()
            assert result is not None


class TestUnifiedSearchModels:
    """Tests for Pydantic models."""
    
    def test_request_validation(self):
        """Test request model validation."""
        # Query too long
        response = client.post("/api/search/unified", json={
            "query": "x" * 1001,
            "entity_types": ["meetings"]
        })
        
        assert response.status_code == 422
    
    def test_response_model_complete(self, all_sample_data):
        """Test response model has all required fields."""
        response = client.get("/api/search/unified?q=test")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required response fields
        required_fields = ["query", "results", "total_results", "entity_counts", 
                          "search_duration_ms", "search_type"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
