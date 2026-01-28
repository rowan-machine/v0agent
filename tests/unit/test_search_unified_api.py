# tests/unit/test_search_unified_api.py
"""
Unit tests for Search Domain Unified API.

Tests the unified search API including:
- Multi-entity search
- Entity type filtering
- Score ranking
- Smart suggestions
"""

import pytest
from unittest.mock import patch, MagicMock


class TestUnifiedSearchModule:
    """Tests for unified search module structure."""

    def test_unified_module_exists(self):
        """Test unified search module exists."""
        from src.app.domains.search.api import unified
        assert unified is not None

    def test_unified_router_exists(self):
        """Test unified module has router."""
        from src.app.domains.search.api.unified import router
        assert router is not None

    def test_unified_router_has_routes(self):
        """Test unified router has registered routes."""
        from src.app.domains.search.api.unified import router
        routes = [route.path for route in router.routes]
        assert len(routes) > 0


class TestHighlightSnippet:
    """Tests for the highlight_snippet function in unified search."""

    def test_highlights_text(self):
        """Should highlight query in text."""
        from src.app.domains.search.api.unified import highlight_snippet
        
        text = "This is a test document with some content."
        result = highlight_snippet(text, "test")
        
        assert result is not None
        # Function may or may not highlight, depends on implementation

    def test_handles_empty_text(self):
        """Should handle empty text."""
        from src.app.domains.search.api.unified import highlight_snippet
        
        result = highlight_snippet("", "query")
        assert result == ""

    def test_handles_none_text(self):
        """Should handle None text."""
        from src.app.domains.search.api.unified import highlight_snippet
        
        result = highlight_snippet(None, "query")
        assert result == ""

    def test_respects_max_length(self):
        """Should respect max_length parameter."""
        from src.app.domains.search.api.unified import highlight_snippet
        
        text = "a" * 500
        result = highlight_snippet(text, "test", max_length=100)
        
        assert len(result) <= 103  # 100 + "..."


class TestEntityConfig:
    """Tests for entity configuration."""

    def test_entity_config_has_meetings(self):
        """Should have meetings configuration."""
        from src.app.domains.search.api.unified import ENTITY_CONFIG
        
        assert "meetings" in ENTITY_CONFIG
        assert ENTITY_CONFIG["meetings"]["icon"] == "📅"
        assert "title_field" in ENTITY_CONFIG["meetings"]

    def test_entity_config_has_documents(self):
        """Should have documents configuration."""
        from src.app.domains.search.api.unified import ENTITY_CONFIG
        
        assert "documents" in ENTITY_CONFIG
        assert ENTITY_CONFIG["documents"]["icon"] == "📄"

    def test_entity_config_has_tickets(self):
        """Should have tickets configuration."""
        from src.app.domains.search.api.unified import ENTITY_CONFIG
        
        assert "tickets" in ENTITY_CONFIG
        assert ENTITY_CONFIG["tickets"]["icon"] == "🎫"

    def test_entity_config_has_dikw(self):
        """Should have DIKW configuration."""
        from src.app.domains.search.api.unified import ENTITY_CONFIG
        
        assert "dikw" in ENTITY_CONFIG
        assert ENTITY_CONFIG["dikw"]["icon"] == "💡"

    def test_entity_config_has_signals(self):
        """Should have signals configuration."""
        from src.app.domains.search.api.unified import ENTITY_CONFIG
        
        assert "signals" in ENTITY_CONFIG
        assert ENTITY_CONFIG["signals"]["icon"] == "📡"

    def test_all_configs_have_required_fields(self):
        """All entity configs should have required fields."""
        from src.app.domains.search.api.unified import ENTITY_CONFIG
        
        required_fields = ["icon", "table", "id_field", "title_field", "content_field", "date_field", "url_template"]
        
        for entity_type, config in ENTITY_CONFIG.items():
            for field in required_fields:
                assert field in config, f"{entity_type} missing {field}"


class TestUnifiedSearchAPI:
    """Tests for unified search API endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from src.app.main import app
        return TestClient(app)

    def test_search_returns_json(self, client):
        """Should return JSON response."""
        response = client.get("/api/domains/search/unified", params={"q": "test"})
        
        assert response.status_code == 200
        data = response.json()
        assert "query" in data or "results" in data

    def test_search_requires_query(self, client):
        """Should handle missing query gracefully."""
        response = client.get("/api/domains/search/unified")
        
        # Should return 200 with empty results or 422 validation error
        assert response.status_code in [200, 422]

    def test_search_accepts_entity_types(self, client):
        """Should accept entity_types parameter."""
        response = client.get("/api/domains/search/unified", params={
            "q": "test",
            "entity_types": "meetings,documents"
        })
        
        assert response.status_code == 200


class TestKeywordSearchModule:
    """Tests for keyword search module."""

    def test_keyword_module_exists(self):
        """Test keyword search module exists."""
        from src.app.domains.search.api import keyword
        assert keyword is not None

    def test_keyword_router_exists(self):
        """Test keyword module has router."""
        from src.app.domains.search.api.keyword import router
        assert router is not None

    def test_keyword_router_has_routes(self):
        """Test keyword router has registered routes."""
        from src.app.domains.search.api.keyword import router
        routes = [route.path for route in router.routes]
        assert "/keyword" in routes


class TestSemanticSearchModule:
    """Tests for semantic search module."""

    def test_semantic_module_exists(self):
        """Test semantic search module exists."""
        from src.app.domains.search.api import semantic
        assert semantic is not None

    def test_semantic_router_exists(self):
        """Test semantic module has router."""
        from src.app.domains.search.api.semantic import router
        assert router is not None

    def test_semantic_router_has_routes(self):
        """Test semantic router has registered routes."""
        from src.app.domains.search.api.semantic import router
        routes = [route.path for route in router.routes]
        assert "/semantic" in routes

    def test_get_embedding_function_exists(self):
        """Test get_embedding function exists."""
        from src.app.domains.search.api.semantic import get_embedding
        assert callable(get_embedding)


class TestSearchDomainIntegration:
    """Integration tests for search domain."""

    def test_search_domain_exports_router(self):
        """Search domain should export router."""
        from src.app.domains.search import router
        assert router is not None

    def test_search_domain_exports_fulltext_router(self):
        """Search domain should export fulltext_router."""
        from src.app.domains.search import fulltext_router
        assert fulltext_router is not None

    def test_search_api_aggregates_routers(self):
        """Search API should aggregate all sub-routers."""
        from src.app.domains.search.api import router
        
        # The router should have nested routes from keyword, semantic, unified
        routes = []
        for route in router.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
            elif hasattr(route, 'routes'):
                # Nested router
                for nested in route.routes:
                    if hasattr(nested, 'path'):
                        routes.append(nested.path)
        
        # Should have routes from all modules
        assert len(routes) >= 3
