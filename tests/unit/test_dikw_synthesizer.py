# tests/unit/test_dikw_synthesizer.py
"""
Unit tests for DIKW Synthesizer Agent Package.

Tests the modular components of the dikw_synthesizer package:
- Constants and level definitions
- Visualization utilities (mindmap, graph, tag clusters)
- Agent class and action handlers
- Adapter functions for backward compatibility
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

class TestDIKWConstants:
    """Tests for DIKW constants and level definitions."""
    
    def test_dikw_levels_defined(self):
        """All DIKW levels should be defined."""
        from src.app.agents.dikw_synthesizer.constants import DIKW_LEVELS
        
        assert "data" in DIKW_LEVELS
        assert "information" in DIKW_LEVELS
        assert "knowledge" in DIKW_LEVELS
        assert "wisdom" in DIKW_LEVELS
        assert len(DIKW_LEVELS) == 4
    
    def test_dikw_level_progression(self):
        """Next level mapping should be correct."""
        from src.app.agents.dikw_synthesizer.constants import DIKW_NEXT_LEVEL
        
        assert DIKW_NEXT_LEVEL["data"] == "information"
        assert DIKW_NEXT_LEVEL["information"] == "knowledge"
        assert DIKW_NEXT_LEVEL["knowledge"] == "wisdom"
        assert "wisdom" not in DIKW_NEXT_LEVEL  # No next level for wisdom
    
    def test_dikw_level_descriptions(self):
        """Level descriptions should be defined."""
        from src.app.agents.dikw_synthesizer.constants import DIKW_LEVEL_DESCRIPTIONS
        
        assert "data" in DIKW_LEVEL_DESCRIPTIONS
        assert "wisdom" in DIKW_LEVEL_DESCRIPTIONS
        assert len(DIKW_LEVEL_DESCRIPTIONS) == 4
        
        # Descriptions should be non-empty strings
        for level, desc in DIKW_LEVEL_DESCRIPTIONS.items():
            assert isinstance(desc, str)
            assert len(desc) > 10
    
    def test_synthesis_prompts_defined(self):
        """Synthesis prompts should be defined for promotable levels."""
        from src.app.agents.dikw_synthesizer.constants import SYNTHESIS_PROMPTS
        
        # Should have prompts for levels you can promote TO
        assert "information" in SYNTHESIS_PROMPTS
        assert "knowledge" in SYNTHESIS_PROMPTS
        assert "wisdom" in SYNTHESIS_PROMPTS
    
    def test_merge_prompt_defined(self):
        """Merge prompt template should be defined."""
        from src.app.agents.dikw_synthesizer.constants import MERGE_PROMPT
        
        assert isinstance(MERGE_PROMPT, str)
        assert "{count}" in MERGE_PROMPT
        assert "{current_level}" in MERGE_PROMPT
        assert "{next_level}" in MERGE_PROMPT


# =============================================================================
# VISUALIZATION TESTS
# =============================================================================

class TestDIKWVisualization:
    """Tests for DIKW visualization utilities."""
    
    @pytest.fixture
    def sample_dikw_items(self):
        """Sample DIKW items for testing."""
        return [
            {"id": 1, "level": "data", "content": "Raw observation", "summary": "Observation", "tags": "test,data"},
            {"id": 2, "level": "data", "content": "Another fact", "summary": "Fact", "tags": "test"},
            {"id": 3, "level": "information", "content": "Contextualized info", "summary": "Context", "tags": "info,test"},
            {"id": 4, "level": "knowledge", "content": "Actionable insight", "summary": "Insight", "tags": "knowledge"},
            {"id": 5, "level": "wisdom", "content": "Strategic principle", "summary": "Principle", "tags": "wisdom,strategy"},
        ]
    
    def test_build_mindmap_tree(self, sample_dikw_items):
        """Should build hierarchical tree structure."""
        from src.app.agents.dikw_synthesizer.visualization import build_mindmap_tree
        
        tree = build_mindmap_tree(sample_dikw_items)
        
        assert tree["name"] == "Knowledge"
        assert tree["type"] == "root"
        assert "children" in tree
        assert len(tree["children"]) == 4  # One for each DIKW level
        
        # Check level nodes exist
        level_names = [child["name"] for child in tree["children"]]
        assert "Data" in level_names
        assert "Information" in level_names
        assert "Knowledge" in level_names
        assert "Wisdom" in level_names
    
    def test_build_graph_data(self, sample_dikw_items):
        """Should build nodes and links for graph visualization."""
        from src.app.agents.dikw_synthesizer.visualization import build_graph_data
        
        nodes, links = build_graph_data(sample_dikw_items)
        
        # Should have root node + level nodes + item nodes
        assert len(nodes) >= 5  # At least root + 4 levels
        
        # Should have links connecting nodes
        assert len(links) >= 4  # At least root to each level
        
        # Check root node exists
        root_nodes = [n for n in nodes if n["id"] == "root"]
        assert len(root_nodes) == 1
    
    def test_build_tag_clusters(self, sample_dikw_items):
        """Should cluster items by tags."""
        from src.app.agents.dikw_synthesizer.visualization import build_tag_clusters
        
        clusters = build_tag_clusters(sample_dikw_items)
        
        # Should have 'test' cluster with multiple items
        assert "test" in clusters
        assert len(clusters["test"]) >= 2
        
        # Each cluster item should have id and level
        for tag, items in clusters.items():
            for item in items:
                assert "id" in item
                assert "level" in item
    
    def test_get_mindmap_data(self, sample_dikw_items):
        """Should return complete mindmap data structure."""
        from src.app.agents.dikw_synthesizer.visualization import get_mindmap_data
        
        data = get_mindmap_data(sample_dikw_items)
        
        assert "tree" in data
        assert "nodes" in data
        assert "links" in data
        assert "tagClusters" in data
        assert "counts" in data
        
        # Counts should reflect input data
        assert data["counts"]["data"] == 2
        assert data["counts"]["information"] == 1
        assert data["counts"]["knowledge"] == 1
        assert data["counts"]["wisdom"] == 1
    
    def test_empty_items_handled(self):
        """Should handle empty item list gracefully."""
        from src.app.agents.dikw_synthesizer.visualization import get_mindmap_data
        
        data = get_mindmap_data([])
        
        assert data["counts"]["data"] == 0
        assert data["counts"]["wisdom"] == 0
        assert len(data["tagClusters"]) == 0


# =============================================================================
# AGENT CLASS TESTS
# =============================================================================

class TestDIKWSynthesizerAgent:
    """Tests for DIKWSynthesizerAgent class."""
    
    def test_agent_instantiation(self):
        """Agent should instantiate with config."""
        from src.app.agents.dikw_synthesizer.agent import DIKWSynthesizerAgent
        from src.app.agents.base import AgentConfig
        
        config = AgentConfig(
            name="test_dikw",
            description="Test DIKW agent",
        )
        
        agent = DIKWSynthesizerAgent(config=config)
        
        assert agent.config.name == "test_dikw"
    
    def test_get_next_level(self):
        """Static method should return correct next level."""
        from src.app.agents.dikw_synthesizer.agent import DIKWSynthesizerAgent
        
        assert DIKWSynthesizerAgent.get_next_level("data") == "information"
        assert DIKWSynthesizerAgent.get_next_level("information") == "knowledge"
        assert DIKWSynthesizerAgent.get_next_level("knowledge") == "wisdom"
        assert DIKWSynthesizerAgent.get_next_level("wisdom") is None
    
    def test_get_prev_level(self):
        """Static method should return correct previous level."""
        from src.app.agents.dikw_synthesizer.agent import DIKWSynthesizerAgent
        
        assert DIKWSynthesizerAgent.get_prev_level("wisdom") == "knowledge"
        assert DIKWSynthesizerAgent.get_prev_level("knowledge") == "information"
        assert DIKWSynthesizerAgent.get_prev_level("information") == "data"
        assert DIKWSynthesizerAgent.get_prev_level("data") is None
    
    def test_is_valid_level(self):
        """Should validate DIKW levels correctly."""
        from src.app.agents.dikw_synthesizer.agent import DIKWSynthesizerAgent
        
        assert DIKWSynthesizerAgent.is_valid_level("data") is True
        assert DIKWSynthesizerAgent.is_valid_level("information") is True
        assert DIKWSynthesizerAgent.is_valid_level("knowledge") is True
        assert DIKWSynthesizerAgent.is_valid_level("wisdom") is True
        assert DIKWSynthesizerAgent.is_valid_level("invalid") is False
    
    def test_normalize_confidence(self):
        """Should normalize confidence values correctly."""
        from src.app.agents.dikw_synthesizer.agent import DIKWSynthesizerAgent
        
        # Values 0-1 should stay same
        assert DIKWSynthesizerAgent.normalize_confidence(0.5) == 0.5
        assert DIKWSynthesizerAgent.normalize_confidence(0.85) == 0.85
        
        # Values 0-100 should be converted
        assert DIKWSynthesizerAgent.normalize_confidence(50) == 0.5
        assert DIKWSynthesizerAgent.normalize_confidence(85) == 0.85


# =============================================================================
# ADAPTER FUNCTIONS TESTS
# =============================================================================

class TestDIKWAdapters:
    """Tests for backward-compatible adapter functions."""
    
    def test_get_dikw_synthesizer_singleton(self):
        """Should return singleton instance."""
        from src.app.agents.dikw_synthesizer.adapters import get_dikw_synthesizer
        
        agent1 = get_dikw_synthesizer()
        agent2 = get_dikw_synthesizer()
        
        # Should be same instance
        assert agent1 is agent2
    
    def test_get_mindmap_data_adapter(self):
        """Adapter should delegate to visualization function."""
        from src.app.agents.dikw_synthesizer.adapters import get_mindmap_data_adapter
        
        items = [
            {"id": 1, "level": "data", "content": "Test", "tags": "tag1"},
        ]
        
        result = get_mindmap_data_adapter(items)
        
        assert "tree" in result
        assert "nodes" in result
        assert "counts" in result


# =============================================================================
# PACKAGE EXPORTS TESTS
# =============================================================================

class TestDIKWPackageExports:
    """Tests for package-level exports."""
    
    def test_constants_exported(self):
        """Constants should be importable from package."""
        from src.app.agents.dikw_synthesizer import (
            DIKW_LEVELS,
            DIKW_NEXT_LEVEL,
            DIKW_PREV_LEVEL,
            DIKW_LEVEL_DESCRIPTIONS,
        )
        
        assert DIKW_LEVELS is not None
        assert DIKW_NEXT_LEVEL is not None
    
    def test_agent_exported(self):
        """Agent class should be importable from package."""
        from src.app.agents.dikw_synthesizer import DIKWSynthesizerAgent
        
        assert DIKWSynthesizerAgent is not None
    
    def test_visualization_exported(self):
        """Visualization functions should be importable from package."""
        from src.app.agents.dikw_synthesizer import (
            build_mindmap_tree,
            build_graph_data,
            build_tag_clusters,
            get_mindmap_data,
        )
        
        assert build_mindmap_tree is not None
        assert build_graph_data is not None
    
    def test_adapters_exported(self):
        """Adapter functions should be importable from package."""
        from src.app.agents.dikw_synthesizer import (
            get_dikw_synthesizer,
            promote_signal_to_dikw_adapter,
            promote_dikw_item_adapter,
        )
        
        assert get_dikw_synthesizer is not None
