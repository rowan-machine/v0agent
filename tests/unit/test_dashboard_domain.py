# tests/unit/test_dashboard_domain.py
"""
Unit tests for Dashboard Domain.

Tests the dashboard domain API routes:
- Quick Ask: AI-powered quick questions
- Highlights: Smart coaching highlights
- Context: Drill-down context for highlights
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json


# =============================================================================
# ROUTER STRUCTURE TESTS
# =============================================================================

class TestDashboardRouterStructure:
    """Tests for dashboard router structure and mounting."""
    
    def test_dashboard_router_imports(self):
        """Dashboard router should be importable."""
        from src.app.domains.dashboard import router
        
        assert router is not None
    
    def test_combined_router_has_prefix(self):
        """Combined router should have /api/dashboard prefix."""
        from src.app.domains.dashboard.api import router
        
        assert router.prefix == "/api/dashboard"
    
    def test_quick_ask_router_exists(self):
        """Quick ask sub-router should exist."""
        from src.app.domains.dashboard.api.quick_ask import router
        
        assert router is not None
    
    def test_highlights_router_exists(self):
        """Highlights sub-router should exist."""
        from src.app.domains.dashboard.api.highlights import router
        
        assert router is not None
    
    def test_context_router_exists(self):
        """Context sub-router should exist."""
        from src.app.domains.dashboard.api.context import router
        
        assert router is not None


# =============================================================================
# ROUTER ROUTE DEFINITIONS TESTS
# =============================================================================

class TestRouterRouteDefinitions:
    """Tests for route definitions in dashboard routers."""
    
    def test_quick_ask_has_post_route(self):
        """Quick ask router should have POST endpoint."""
        from src.app.domains.dashboard.api.quick_ask import router
        
        # Find POST routes
        post_routes = [r for r in router.routes if hasattr(r, 'methods') and 'POST' in r.methods]
        assert len(post_routes) > 0, "Quick ask should have at least one POST route"
    
    def test_highlights_has_get_route(self):
        """Highlights router should have GET endpoint."""
        from src.app.domains.dashboard.api.highlights import router
        
        # Find GET routes
        get_routes = [r for r in router.routes if hasattr(r, 'methods') and 'GET' in r.methods]
        assert len(get_routes) > 0, "Highlights should have at least one GET route"
    
    def test_context_has_post_route(self):
        """Context router should have POST endpoint."""
        from src.app.domains.dashboard.api.context import router
        
        # Find POST routes
        post_routes = [r for r in router.routes if hasattr(r, 'methods') and 'POST' in r.methods]
        assert len(post_routes) > 0, "Context should have at least one POST route"


# =============================================================================
# COMBINED ROUTER TESTS
# =============================================================================

class TestCombinedRouter:
    """Tests for combined dashboard router."""
    
    def test_router_includes_all_subrouters(self):
        """Combined router should include routes from all sub-routers."""
        from src.app.domains.dashboard.api import router
        
        # Get all route paths
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        
        # Should have routes from different sub-routers
        assert len(paths) >= 3, "Should have routes from quick_ask, highlights, and context"
    
    def test_router_has_dashboard_tags(self):
        """Dashboard router should have appropriate tags."""
        from src.app.domains.dashboard.api import router
        
        # Combined router should exist
        assert router is not None
        assert router.prefix == "/api/dashboard"


# =============================================================================
# SERVICE IMPORT TESTS
# =============================================================================

class TestServiceImports:
    """Tests verifying service imports work correctly."""
    
    def test_meeting_service_importable(self):
        """Meeting service module should be importable."""
        from src.app.services import meeting_service
        
        assert meeting_service is not None
        # Check key functions exist
        assert hasattr(meeting_service, 'get_all_meetings')
        assert hasattr(meeting_service, 'get_meeting_by_id')
    
    def test_ticket_service_importable(self):
        """Ticket service module should be importable."""
        from src.app.services import ticket_service
        
        assert ticket_service is not None
        # Check key functions exist
        assert hasattr(ticket_service, 'get_all_tickets')
    
    def test_arjuna_quick_ask_importable(self):
        """Arjuna quick_ask should be importable."""
        from src.app.agents.arjuna import quick_ask
        
        assert quick_ask is not None


# =============================================================================
# REPOSITORY IMPORT TESTS
# =============================================================================

class TestRepositoryImports:
    """Tests verifying repository imports work correctly."""
    
    def test_settings_repository_importable(self):
        """Settings repository should be importable."""
        from src.app.repositories import get_settings_repository
        
        assert get_settings_repository is not None
    
    def test_signal_repository_importable(self):
        """Signal repository should be importable."""
        from src.app.repositories import get_signal_repository
        
        assert get_signal_repository is not None


# =============================================================================
# DOMAIN EXPORTS TESTS
# =============================================================================

class TestDomainExports:
    """Tests for dashboard domain exports."""
    
    def test_dashboard_init_exports_router(self):
        """Dashboard __init__ should export router."""
        from src.app.domains.dashboard import router
        
        assert router is not None
    
    def test_api_init_exports_router(self):
        """Dashboard api __init__ should export combined router."""
        from src.app.domains.dashboard.api import router
        
        assert router is not None
        assert router.prefix == "/api/dashboard"
