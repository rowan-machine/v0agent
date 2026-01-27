# tests/unit/test_dikw_repository.py
"""
Tests for DIKW Repository

Validates the repository pattern implementation for DIKW operations.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestDIKWRepositoryImports:
    """Test DIKW repository module structure."""

    def test_dikw_repository_module_exists(self):
        """Test dikw_repository module exists."""
        from src.app.repositories import dikw_repository
        assert dikw_repository is not None

    def test_dikw_repository_class_exists(self):
        """Test DIKWRepository abstract class exists."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert DIKWRepository is not None

    def test_supabase_dikw_repository_exists(self):
        """Test SupabaseDIKWRepository implementation exists."""
        from src.app.repositories.dikw_repository import SupabaseDIKWRepository
        assert SupabaseDIKWRepository is not None

    def test_get_dikw_repository_factory_exists(self):
        """Test factory function exists."""
        from src.app.repositories import get_dikw_repository
        assert callable(get_dikw_repository)


class TestDIKWDataClasses:
    """Test DIKW data classes."""

    def test_dikw_item_dataclass_exists(self):
        """Test DIKWItem dataclass exists."""
        from src.app.repositories.dikw_repository import DIKWItem
        assert DIKWItem is not None

    def test_dikw_item_from_dict(self):
        """Test DIKWItem.from_dict creates instance correctly."""
        from src.app.repositories.dikw_repository import DIKWItem
        
        data = {
            "id": 1,
            "level": "information",
            "content": "Test content",
            "summary": "Test summary",
            "tags": "test,data",
            "meeting_id": "meeting-123",
            "source_type": "signal",
            "confidence": 80,
            "validation_count": 3,
            "status": "active"
        }
        
        item = DIKWItem.from_dict(data)
        
        assert item.id == 1
        assert item.level == "information"
        assert item.content == "Test content"
        assert item.summary == "Test summary"
        assert item.confidence == 80
        assert item.validation_count == 3

    def test_dikw_item_to_dict(self):
        """Test DIKWItem.to_dict converts to dictionary."""
        from src.app.repositories.dikw_repository import DIKWItem
        
        item = DIKWItem(
            id=1,
            level="knowledge",
            content="Test knowledge",
            summary="Summary",
            confidence=90
        )
        
        data = item.to_dict()
        
        assert data["level"] == "knowledge"
        assert data["content"] == "Test knowledge"
        assert data["confidence"] == 90

    def test_dikw_evolution_dataclass_exists(self):
        """Test DIKWEvolution dataclass exists."""
        from src.app.repositories.dikw_repository import DIKWEvolution
        assert DIKWEvolution is not None

    def test_dikw_evolution_from_dict(self):
        """Test DIKWEvolution.from_dict creates instance correctly."""
        from src.app.repositories.dikw_repository import DIKWEvolution
        
        data = {
            "id": 1,
            "item_id": 5,
            "action": "promote",
            "previous_level": "data",
            "new_level": "information",
            "reason": "Validated 3 times"
        }
        
        evolution = DIKWEvolution.from_dict(data)
        
        assert evolution.item_id == 5
        assert evolution.action == "promote"
        assert evolution.previous_level == "data"
        assert evolution.new_level == "information"

    def test_dikw_pyramid_dataclass_exists(self):
        """Test DIKWPyramid dataclass exists."""
        from src.app.repositories.dikw_repository import DIKWPyramid
        assert DIKWPyramid is not None

    def test_dikw_pyramid_counts(self):
        """Test DIKWPyramid.counts returns correct counts."""
        from src.app.repositories.dikw_repository import DIKWPyramid, DIKWItem
        
        pyramid = DIKWPyramid(
            data=[DIKWItem(content="d1"), DIKWItem(content="d2")],
            information=[DIKWItem(content="i1")],
            knowledge=[],
            wisdom=[]
        )
        
        counts = pyramid.counts
        
        assert counts["data"] == 2
        assert counts["information"] == 1
        assert counts["knowledge"] == 0
        assert counts["wisdom"] == 0


class TestDIKWConstants:
    """Test DIKW constants."""

    def test_dikw_levels_defined(self):
        """Test DIKW_LEVELS constant exists."""
        from src.app.repositories.dikw_repository import DIKW_LEVELS
        
        assert "data" in DIKW_LEVELS
        assert "information" in DIKW_LEVELS
        assert "knowledge" in DIKW_LEVELS
        assert "wisdom" in DIKW_LEVELS

    def test_dikw_next_level_mapping(self):
        """Test DIKW_NEXT_LEVEL mapping."""
        from src.app.repositories.dikw_repository import DIKW_NEXT_LEVEL
        
        assert DIKW_NEXT_LEVEL["data"] == "information"
        assert DIKW_NEXT_LEVEL["information"] == "knowledge"
        assert DIKW_NEXT_LEVEL["knowledge"] == "wisdom"


class TestDIKWRepositoryInterface:
    """Test DIKW repository abstract interface."""

    def test_repository_has_get_items_method(self):
        """Test repository has get_items method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "get_items")

    def test_repository_has_get_pyramid_method(self):
        """Test repository has get_pyramid method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "get_pyramid")

    def test_repository_has_get_by_id_method(self):
        """Test repository has get_by_id method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "get_by_id")

    def test_repository_has_create_method(self):
        """Test repository has create method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "create")

    def test_repository_has_update_method(self):
        """Test repository has update method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "update")

    def test_repository_has_delete_method(self):
        """Test repository has delete method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "delete")

    def test_repository_has_promote_method(self):
        """Test repository has promote method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "promote")

    def test_repository_has_validate_method(self):
        """Test repository has validate method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "validate")

    def test_repository_has_merge_method(self):
        """Test repository has merge method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "merge")

    def test_repository_has_get_history_method(self):
        """Test repository has get_history method."""
        from src.app.repositories.dikw_repository import DIKWRepository
        assert hasattr(DIKWRepository, "get_history")


class TestSupabaseDIKWRepository:
    """Test Supabase DIKW repository implementation."""

    def test_implements_dikw_repository(self):
        """Test SupabaseDIKWRepository implements DIKWRepository."""
        from src.app.repositories.dikw_repository import (
            DIKWRepository,
            SupabaseDIKWRepository
        )
        
        assert issubclass(SupabaseDIKWRepository, DIKWRepository)

    def test_has_get_items_method(self):
        """Test SupabaseDIKWRepository has get_items method."""
        from src.app.repositories.dikw_repository import SupabaseDIKWRepository
        assert hasattr(SupabaseDIKWRepository, "get_items")
        assert callable(getattr(SupabaseDIKWRepository, "get_items", None))

    def test_has_get_by_id_method(self):
        """Test SupabaseDIKWRepository has get_by_id method."""
        from src.app.repositories.dikw_repository import SupabaseDIKWRepository
        assert hasattr(SupabaseDIKWRepository, "get_by_id")
        assert callable(getattr(SupabaseDIKWRepository, "get_by_id", None))


class TestDIKWDomainIntegration:
    """Test DIKW domain uses repository."""

    def test_dikw_domain_items_module_exists(self):
        """Test DIKW domain items module exists."""
        from src.app.domains.dikw.api import items
        assert items is not None

    def test_dikw_domain_items_router_exists(self):
        """Test DIKW domain items router exists."""
        from src.app.domains.dikw.api.items import router
        assert router is not None

    def test_dikw_domain_promotion_module_exists(self):
        """Test DIKW domain promotion module exists."""
        from src.app.domains.dikw.api import promotion
        assert promotion is not None

    def test_dikw_domain_synthesis_module_exists(self):
        """Test DIKW domain synthesis module exists."""
        from src.app.domains.dikw.api import synthesis
        assert synthesis is not None

    def test_dikw_domain_relationships_module_exists(self):
        """Test DIKW domain relationships module exists."""
        from src.app.domains.dikw.api import relationships
        assert relationships is not None


class TestDIKWAgentPackage:
    """Test DIKW synthesizer agent package."""

    def test_dikw_synthesizer_package_exists(self):
        """Test dikw_synthesizer package exists."""
        from src.app.agents import dikw_synthesizer
        assert dikw_synthesizer is not None

    def test_dikw_synthesizer_has_constants(self):
        """Test dikw_synthesizer has constants."""
        from src.app.agents.dikw_synthesizer import DIKW_LEVELS
        assert "data" in DIKW_LEVELS

    def test_dikw_synthesizer_agent_class_exists(self):
        """Test DIKWSynthesizerAgent class exists."""
        from src.app.agents.dikw_synthesizer import DIKWSynthesizerAgent
        assert DIKWSynthesizerAgent is not None

    def test_dikw_synthesizer_has_adapters(self):
        """Test dikw_synthesizer has adapters."""
        from src.app.agents.dikw_synthesizer import get_dikw_synthesizer
        assert callable(get_dikw_synthesizer)
