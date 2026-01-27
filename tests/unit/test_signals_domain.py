# tests/unit/test_signals_domain.py
"""
Unit tests for Signals Domain.

Tests the signals domain API routes:
- Browse: Signal listing by type with date filtering
- Extraction: Document signal extraction
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json


# =============================================================================
# ROUTER STRUCTURE TESTS
# =============================================================================

class TestSignalsRouterStructure:
    """Tests for signals router structure and mounting."""
    
    def test_signals_router_imports(self):
        """Signals router should be importable."""
        from src.app.domains.signals import signals_router
        
        assert signals_router is not None
    
    def test_signals_router_has_prefix(self):
        """Signals router should have /api/signals prefix."""
        from src.app.domains.signals.api import router
        
        assert router.prefix == "/api/signals"
    
    def test_browse_router_exists(self):
        """Browse sub-router should exist."""
        from src.app.domains.signals.api.browse import router
        
        assert router is not None
    
    def test_extraction_router_exists(self):
        """Extraction sub-router should exist."""
        from src.app.domains.signals.api.extraction import router
        
        assert router is not None


# =============================================================================
# BROWSE CONSTANTS TESTS
# =============================================================================

class TestBrowseConstants:
    """Tests for browse constants."""
    
    def test_date_presets_defined(self):
        """DATE_PRESETS should be defined."""
        from src.app.domains.signals.api.browse import DATE_PRESETS
        
        assert DATE_PRESETS is not None
        assert "all" in DATE_PRESETS
        assert "7" in DATE_PRESETS
        assert "14" in DATE_PRESETS
        assert "30" in DATE_PRESETS
    
    def test_signal_type_map_defined(self):
        """SIGNAL_TYPE_MAP should be defined."""
        from src.app.domains.signals.api.browse import SIGNAL_TYPE_MAP
        
        assert SIGNAL_TYPE_MAP is not None
        assert "decisions" in SIGNAL_TYPE_MAP
        assert "action_items" in SIGNAL_TYPE_MAP
        assert "blockers" in SIGNAL_TYPE_MAP
        assert "risks" in SIGNAL_TYPE_MAP
        assert "ideas" in SIGNAL_TYPE_MAP
    
    def test_signal_types_list_defined(self):
        """SIGNAL_TYPES list should be defined."""
        from src.app.domains.signals.api.browse import SIGNAL_TYPES
        
        assert SIGNAL_TYPES is not None
        assert len(SIGNAL_TYPES) == 5
        assert "decisions" in SIGNAL_TYPES


# =============================================================================
# BROWSE HELPER FUNCTIONS TESTS
# =============================================================================

class TestBrowseHelperFunctions:
    """Tests for browse helper functions."""
    
    def test_collect_all_signals_with_empty_data(self):
        """_collect_all_signals should handle empty signals."""
        from src.app.domains.signals.api.browse import _collect_all_signals
        
        meeting = {"id": "test-123"}
        signals = {}
        status_map = {}
        
        result = _collect_all_signals(meeting, signals, status_map)
        
        assert result == []
    
    def test_collect_all_signals_with_list_data(self):
        """_collect_all_signals should handle list signals."""
        from src.app.domains.signals.api.browse import _collect_all_signals
        
        meeting = {"id": "test-123"}
        signals = {
            "decisions": ["Decision 1", "Decision 2"],
            "action_items": ["Action 1"],
            "blockers": [],
            "risks": [],
            "ideas": []
        }
        status_map = {}
        
        result = _collect_all_signals(meeting, signals, status_map)
        
        assert len(result) == 3
        assert any(s["text"] == "Decision 1" for s in result)
        assert any(s["type"] == "decision" for s in result)
    
    def test_collect_all_signals_with_status(self):
        """_collect_all_signals should include status from status_map."""
        from src.app.domains.signals.api.browse import _collect_all_signals
        
        meeting = {"id": "meeting-1"}
        signals = {"decisions": ["Important decision"]}
        status_map = {"meeting-1:decision:Important decision": "reviewed"}
        
        result = _collect_all_signals(meeting, signals, status_map)
        
        assert len(result) == 1
        assert result[0]["status"] == "reviewed"
    
    def test_collect_typed_signals_empty(self):
        """_collect_typed_signals should handle empty data."""
        from src.app.domains.signals.api.browse import _collect_typed_signals
        
        meeting = {"id": "test-123"}
        signals = {}
        
        result = _collect_typed_signals(meeting, signals, "decisions", {})
        
        assert result == []
    
    def test_collect_typed_signals_with_data(self):
        """_collect_typed_signals should collect signals of specific type."""
        from src.app.domains.signals.api.browse import _collect_typed_signals
        
        meeting = {"id": "test-123"}
        signals = {
            "decisions": ["Decision 1", "Decision 2"],
            "action_items": ["Action 1"]
        }
        
        result = _collect_typed_signals(meeting, signals, "decisions", {})
        
        assert len(result) == 2
        assert all(s["type"] == "decision" for s in result)


# =============================================================================
# ROUTER ROUTES TESTS
# =============================================================================

class TestRouterRoutes:
    """Tests for route definitions."""
    
    def test_browse_router_has_list_route(self):
        """Browse router should have /list endpoint."""
        from src.app.domains.signals.api.browse import router
        
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        assert "/list" in paths
    
    def test_browse_router_has_view_routes(self):
        """Browse router should have /view/* endpoints."""
        from src.app.domains.signals.api.browse import router
        
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        
        assert "/view" in paths or any("/view" in p for p in paths)
    
    def test_extraction_router_has_extract_route(self):
        """Extraction router should have /extract-from-document endpoint."""
        from src.app.domains.signals.api.extraction import router
        
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        
        assert "/extract-from-document" in paths
    
    def test_extraction_router_has_save_route(self):
        """Extraction router should have /save-from-document endpoint."""
        from src.app.domains.signals.api.extraction import router
        
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        
        assert "/save-from-document" in paths


# =============================================================================
# DOMAIN EXPORTS TESTS
# =============================================================================

class TestDomainExports:
    """Tests for signals domain exports."""
    
    def test_domain_exports_router(self):
        """Signals domain __init__ should export router."""
        from src.app.domains.signals import signals_router
        
        assert signals_router is not None
        assert signals_router.prefix == "/api/signals"
    
    def test_api_exports_combined_router(self):
        """Signals api __init__ should export combined router."""
        from src.app.domains.signals.api import router
        
        assert router is not None
        assert router.prefix == "/api/signals"
        assert len(router.routes) > 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSignalsDomainIntegration:
    """Integration tests for signals domain."""
    
    def test_combined_router_has_both_subrouters(self):
        """Combined router should include routes from both sub-routers."""
        from src.app.domains.signals.api import router
        
        paths = [r.path for r in router.routes if hasattr(r, 'path')]
        
        # Should have browse routes
        assert any("/list" in p or "/view" in p for p in paths)
        
        # Should have extraction routes
        assert any("extract" in p or "save" in p for p in paths)
    
    def test_signals_domain_mounted_in_main(self):
        """Signals domain should be mounted in main app."""
        from src.app.main import app
        
        paths = [str(r.path) for r in app.routes]
        
        # Should have signals domain routes
        assert any("/api/signals" in p for p in paths)
