# tests/unit/test_arjuna_package.py
"""
Unit tests for Arjuna Agent Package.

Tests the decomposed arjuna package structure:
- Constants: AVAILABLE_MODELS, SYSTEM_PAGES, MODEL_ALIASES, FOCUS_KEYWORDS
- Mixins: ArjunaToolsMixin, ArjunaContextMixin, ArjunaStandupMixin, ArjunaFocusMixin
- Core: ArjunaAgent class and adapters
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

class TestArjunaConstants:
    """Tests for arjuna constants module."""
    
    def test_available_models_defined(self):
        """AVAILABLE_MODELS should be defined and non-empty."""
        from src.app.agents.arjuna import AVAILABLE_MODELS
        
        assert AVAILABLE_MODELS is not None
        assert len(AVAILABLE_MODELS) > 0
    
    def test_available_models_has_gpt(self):
        """AVAILABLE_MODELS should include GPT models."""
        from src.app.agents.arjuna import AVAILABLE_MODELS
        
        gpt_models = [m for m in AVAILABLE_MODELS if "gpt" in m.lower()]
        assert len(gpt_models) > 0
    
    def test_system_pages_defined(self):
        """SYSTEM_PAGES should be defined."""
        from src.app.agents.arjuna import SYSTEM_PAGES
        
        assert SYSTEM_PAGES is not None
        assert isinstance(SYSTEM_PAGES, dict)
    
    def test_system_pages_have_paths(self):
        """Each system page should have a path."""
        from src.app.agents.arjuna import SYSTEM_PAGES
        
        for name, info in SYSTEM_PAGES.items():
            assert "path" in info, f"System page {name} missing 'path'"
    
    def test_model_aliases_defined(self):
        """MODEL_ALIASES should be defined."""
        from src.app.agents.arjuna.constants import MODEL_ALIASES
        
        assert MODEL_ALIASES is not None
        assert isinstance(MODEL_ALIASES, dict)
    
    def test_focus_keywords_defined(self):
        """FOCUS_KEYWORDS should be defined."""
        from src.app.agents.arjuna import FOCUS_KEYWORDS
        
        assert FOCUS_KEYWORDS is not None
        assert len(FOCUS_KEYWORDS) > 0


# =============================================================================
# MIXIN IMPORT TESTS
# =============================================================================

class TestMixinImports:
    """Tests for mixin class imports."""
    
    def test_tools_mixin_importable(self):
        """ArjunaToolsMixin should be importable."""
        from src.app.agents.arjuna import ArjunaToolsMixin
        
        assert ArjunaToolsMixin is not None
    
    def test_context_mixin_importable(self):
        """ArjunaContextMixin should be importable."""
        from src.app.agents.arjuna import ArjunaContextMixin
        
        assert ArjunaContextMixin is not None
    
    def test_standup_mixin_importable(self):
        """ArjunaStandupMixin should be importable."""
        from src.app.agents.arjuna import ArjunaStandupMixin
        
        assert ArjunaStandupMixin is not None
    
    def test_focus_mixin_importable(self):
        """ArjunaFocusMixin should be importable."""
        from src.app.agents.arjuna import ArjunaFocusMixin
        
        assert ArjunaFocusMixin is not None


# =============================================================================
# STANDUP MIXIN TESTS
# =============================================================================

class TestStandupMixin:
    """Tests for ArjunaStandupMixin methods."""
    
    def test_standup_mixin_has_methods(self):
        """ArjunaStandupMixin should have expected methods."""
        from src.app.agents.arjuna import ArjunaStandupMixin
        
        assert hasattr(ArjunaStandupMixin, '_get_standup_context')
        assert hasattr(ArjunaStandupMixin, '_format_standup_context_for_prompt')
        assert hasattr(ArjunaStandupMixin, 'generate_standup_draft')
        assert hasattr(ArjunaStandupMixin, '_create_standup')
    
    def test_format_standup_context_empty(self):
        """_format_standup_context_for_prompt should handle empty context."""
        from src.app.agents.arjuna import ArjunaStandupMixin
        
        mixin = ArjunaStandupMixin()
        ctx = {}
        
        result = mixin._format_standup_context_for_prompt(ctx)
        
        assert "No recent activity" in result
    
    def test_format_standup_context_with_meetings(self):
        """_format_standup_context_for_prompt should format meetings."""
        from src.app.agents.arjuna import ArjunaStandupMixin
        
        mixin = ArjunaStandupMixin()
        ctx = {
            "meetings_yesterday": [{"name": "Sprint Planning"}],
            "meetings_today": [{"name": "Daily Standup"}],
        }
        
        result = mixin._format_standup_context_for_prompt(ctx)
        
        assert "Sprint Planning" in result
        assert "Daily Standup" in result


# =============================================================================
# FOCUS MIXIN TESTS
# =============================================================================

class TestFocusMixin:
    """Tests for ArjunaFocusMixin methods."""
    
    def test_focus_mixin_has_methods(self):
        """ArjunaFocusMixin should have expected methods."""
        from src.app.agents.arjuna import ArjunaFocusMixin
        
        assert hasattr(ArjunaFocusMixin, '_is_focus_query')
        assert hasattr(ArjunaFocusMixin, '_handle_focus_query')
        assert hasattr(ArjunaFocusMixin, '_get_focus_recommendations')
        assert hasattr(ArjunaFocusMixin, '_format_focus_response')
    
    def test_is_focus_query_detects_keywords(self):
        """_is_focus_query should detect focus-related keywords."""
        from src.app.agents.arjuna import ArjunaFocusMixin
        
        mixin = ArjunaFocusMixin()
        
        assert mixin._is_focus_query("What should I focus on?")
        assert mixin._is_focus_query("What should I do next?")
        assert mixin._is_focus_query("What should I work on today?")
        assert mixin._is_focus_query("What should I start with?")
    
    def test_is_focus_query_ignores_unrelated(self):
        """_is_focus_query should not match unrelated queries."""
        from src.app.agents.arjuna import ArjunaFocusMixin
        
        mixin = ArjunaFocusMixin()
        
        assert not mixin._is_focus_query("Hello!")
        assert not mixin._is_focus_query("Create a ticket")
    
    def test_format_focus_response_empty(self):
        """_format_focus_response should handle no recommendations."""
        from src.app.agents.arjuna import ArjunaFocusMixin
        
        mixin = ArjunaFocusMixin()
        
        result = mixin._format_focus_response([], {})
        
        assert "all caught up" in result.lower()
    
    def test_format_focus_response_with_recs(self):
        """_format_focus_response should format recommendations."""
        from src.app.agents.arjuna import ArjunaFocusMixin
        
        mixin = ArjunaFocusMixin()
        recs = [
            {"priority": "high", "message": "🚫 Unblock TICK-1: Test ticket"},
            {"priority": "medium", "message": "🔄 Continue TICK-2: Another ticket"},
        ]
        
        result = mixin._format_focus_response(recs, {"blocked_count": 1})
        
        assert "High Priority" in result
        assert "TICK-1" in result


# =============================================================================
# AGENT CORE TESTS
# =============================================================================

class TestArjunaAgentCore:
    """Tests for ArjunaAgent class."""
    
    def test_arjuna_agent_importable(self):
        """ArjunaAgent should be importable."""
        from src.app.agents.arjuna import ArjunaAgent
        
        assert ArjunaAgent is not None
    
    def test_get_arjuna_agent_importable(self):
        """get_arjuna_agent should be importable."""
        from src.app.agents.arjuna import get_arjuna_agent
        
        assert get_arjuna_agent is not None
    
    def test_quick_ask_importable(self):
        """quick_ask should be importable."""
        from src.app.agents.arjuna import quick_ask
        
        assert quick_ask is not None


# =============================================================================
# ADAPTER FUNCTIONS TESTS
# =============================================================================

class TestAdapterFunctions:
    """Tests for module-level adapter functions."""
    
    def test_get_follow_up_suggestions_importable(self):
        """get_follow_up_suggestions should be importable."""
        from src.app.agents.arjuna import get_follow_up_suggestions
        
        assert get_follow_up_suggestions is not None
    
    def test_get_focus_recommendations_importable(self):
        """get_focus_recommendations should be importable."""
        from src.app.agents.arjuna import get_focus_recommendations
        
        assert get_focus_recommendations is not None
    
    def test_get_system_context_importable(self):
        """get_system_context should be importable."""
        from src.app.agents.arjuna import get_system_context
        
        assert get_system_context is not None
    
    def test_parse_assistant_intent_importable(self):
        """parse_assistant_intent should be importable."""
        from src.app.agents.arjuna import parse_assistant_intent
        
        assert parse_assistant_intent is not None
    
    def test_execute_intent_importable(self):
        """execute_intent should be importable."""
        from src.app.agents.arjuna import execute_intent
        
        assert execute_intent is not None


# =============================================================================
# MCP COMMANDS TESTS
# =============================================================================

class TestMCPCommands:
    """Tests for MCP command exports."""
    
    def test_mcp_commands_importable(self):
        """MCP_COMMANDS should be importable from arjuna."""
        from src.app.agents.arjuna import MCP_COMMANDS
        
        assert MCP_COMMANDS is not None
        assert isinstance(MCP_COMMANDS, dict)
    
    def test_mcp_inference_patterns_importable(self):
        """MCP_INFERENCE_PATTERNS should be importable from arjuna."""
        from src.app.agents.arjuna import MCP_INFERENCE_PATTERNS
        
        assert MCP_INFERENCE_PATTERNS is not None
    
    def test_parse_mcp_command_importable(self):
        """parse_mcp_command should be importable from arjuna."""
        from src.app.agents.arjuna import parse_mcp_command
        
        assert parse_mcp_command is not None
    
    def test_infer_mcp_command_importable(self):
        """infer_mcp_command should be importable from arjuna."""
        from src.app.agents.arjuna import infer_mcp_command
        
        assert infer_mcp_command is not None


# =============================================================================
# PACKAGE EXPORTS TESTS
# =============================================================================

class TestPackageExports:
    """Tests for arjuna package __all__ exports."""
    
    def test_all_exports_accessible(self):
        """All items in __all__ should be accessible."""
        from src.app.agents import arjuna
        
        for name in arjuna.__all__:
            assert hasattr(arjuna, name), f"Missing export: {name}"
    
    def test_package_has_docstring(self):
        """Package should have a docstring."""
        from src.app.agents import arjuna
        
        assert arjuna.__doc__ is not None
        assert "Arjuna" in arjuna.__doc__


# =============================================================================
# NEW MIXINS TESTS (Phase 2.3)
# =============================================================================

class TestMCPHandlerMixin:
    """Tests for ArjunaMCPMixin."""
    
    def test_mcp_mixin_importable(self):
        """ArjunaMCPMixin should be importable."""
        from src.app.agents.arjuna import ArjunaMCPMixin
        
        assert ArjunaMCPMixin is not None
    
    def test_mcp_mixin_has_methods(self):
        """ArjunaMCPMixin should have expected methods."""
        from src.app.agents.arjuna import ArjunaMCPMixin
        
        assert hasattr(ArjunaMCPMixin, '_handle_mcp_command')
        assert hasattr(ArjunaMCPMixin, '_route_agent_command')


class TestChainExecutorMixin:
    """Tests for ArjunaChainMixin."""
    
    def test_chain_mixin_importable(self):
        """ArjunaChainMixin should be importable."""
        from src.app.agents.arjuna import ArjunaChainMixin
        
        assert ArjunaChainMixin is not None
    
    def test_chain_definitions_importable(self):
        """CHAIN_DEFINITIONS should be importable."""
        from src.app.agents.arjuna import CHAIN_DEFINITIONS
        
        assert CHAIN_DEFINITIONS is not None
        assert isinstance(CHAIN_DEFINITIONS, dict)
    
    def test_chain_definitions_have_steps(self):
        """Each chain definition should have steps."""
        from src.app.agents.arjuna import CHAIN_DEFINITIONS
        
        for name, chain in CHAIN_DEFINITIONS.items():
            assert "steps" in chain, f"Chain {name} missing 'steps'"
            assert "description" in chain, f"Chain {name} missing 'description'"
            assert len(chain["steps"]) > 0, f"Chain {name} has no steps"
    
    def test_chain_mixin_has_methods(self):
        """ArjunaChainMixin should have expected methods."""
        from src.app.agents.arjuna import ArjunaChainMixin
        
        assert hasattr(ArjunaChainMixin, '_execute_chain_command')
        assert hasattr(ArjunaChainMixin, '_execute_chain_step')


class TestIntentMixin:
    """Tests for ArjunaIntentMixin."""
    
    def test_intent_mixin_importable(self):
        """ArjunaIntentMixin should be importable."""
        from src.app.agents.arjuna import ArjunaIntentMixin
        
        assert ArjunaIntentMixin is not None
    
    def test_intent_mixin_has_methods(self):
        """ArjunaIntentMixin should have expected methods."""
        from src.app.agents.arjuna import ArjunaIntentMixin
        
        assert hasattr(ArjunaIntentMixin, '_parse_intent')
        assert hasattr(ArjunaIntentMixin, '_build_intent_prompt')
        assert hasattr(ArjunaIntentMixin, '_execute_intent')


class TestTicketMixin:
    """Tests for ArjunaTicketMixin."""
    
    def test_ticket_mixin_importable(self):
        """ArjunaTicketMixin should be importable."""
        from src.app.agents.arjuna import ArjunaTicketMixin
        
        assert ArjunaTicketMixin is not None
    
    def test_ticket_mixin_has_methods(self):
        """ArjunaTicketMixin should have expected methods."""
        from src.app.agents.arjuna import ArjunaTicketMixin
        
        assert hasattr(ArjunaTicketMixin, '_create_ticket')
        assert hasattr(ArjunaTicketMixin, '_update_ticket')
        assert hasattr(ArjunaTicketMixin, '_list_tickets')
        assert hasattr(ArjunaTicketMixin, '_create_accountability')
        assert hasattr(ArjunaTicketMixin, '_handle_navigation')
        assert hasattr(ArjunaTicketMixin, '_change_model')
        assert hasattr(ArjunaTicketMixin, '_update_sprint')
        assert hasattr(ArjunaTicketMixin, '_reset_workflow')
        assert hasattr(ArjunaTicketMixin, '_search_meetings')


# =============================================================================
# CORE MODULE TESTS (Phase 2.3)
# =============================================================================

class TestArjunaCore:
    """Tests for ArjunaAgentCore class."""
    
    def test_core_importable(self):
        """ArjunaAgentCore should be importable."""
        from src.app.agents.arjuna import ArjunaAgentCore
        
        assert ArjunaAgentCore is not None
    
    def test_core_alias_importable(self):
        """ArjunaAgentComposed should be an alias for ArjunaAgentCore."""
        from src.app.agents.arjuna import ArjunaAgentCore, ArjunaAgentComposed
        
        assert ArjunaAgentComposed is ArjunaAgentCore
    
    def test_core_has_run_method(self):
        """ArjunaAgentCore should have run method."""
        from src.app.agents.arjuna import ArjunaAgentCore
        
        assert hasattr(ArjunaAgentCore, 'run')
    
    def test_core_has_get_system_prompt(self):
        """ArjunaAgentCore should have get_system_prompt method."""
        from src.app.agents.arjuna import ArjunaAgentCore
        
        assert hasattr(ArjunaAgentCore, 'get_system_prompt')
    
    def test_core_has_quick_ask(self):
        """ArjunaAgentCore should have quick_ask method."""
        from src.app.agents.arjuna import ArjunaAgentCore
        
        assert hasattr(ArjunaAgentCore, 'quick_ask')
    
    def test_core_has_ask_llm(self):
        """ArjunaAgentCore should have ask_llm method."""
        from src.app.agents.arjuna import ArjunaAgentCore
        
        assert hasattr(ArjunaAgentCore, 'ask_llm')
    
    def test_core_inherits_mixins(self):
        """ArjunaAgentCore should inherit from all mixins."""
        from src.app.agents.arjuna import (
            ArjunaAgentCore,
            ArjunaContextMixin,
            ArjunaFocusMixin,
            ArjunaMCPMixin,
            ArjunaChainMixin,
            ArjunaIntentMixin,
            ArjunaTicketMixin,
        )
        
        # Check MRO includes mixins
        mro = ArjunaAgentCore.__mro__
        mixin_names = [c.__name__ for c in mro]
        
        assert 'ArjunaContextMixin' in mixin_names
        assert 'ArjunaFocusMixin' in mixin_names
        assert 'ArjunaMCPMixin' in mixin_names
        assert 'ArjunaChainMixin' in mixin_names
        assert 'ArjunaIntentMixin' in mixin_names
        assert 'ArjunaTicketMixin' in mixin_names


# =============================================================================
# ADAPTERS MODULE TESTS (Phase 2.3)
# =============================================================================

class TestArjunaAdapters:
    """Tests for Arjuna adapter functions."""
    
    def test_simple_llm_client_importable(self):
        """SimpleLLMClient should be importable."""
        from src.app.agents.arjuna import SimpleLLMClient
        
        assert SimpleLLMClient is not None
    
    def test_get_arjuna_agent_importable(self):
        """get_arjuna_agent should be importable."""
        from src.app.agents.arjuna import get_arjuna_agent
        
        assert get_arjuna_agent is not None
        assert callable(get_arjuna_agent)
    
    def test_get_follow_up_suggestions_importable(self):
        """get_follow_up_suggestions should be importable."""
        from src.app.agents.arjuna import get_follow_up_suggestions
        
        assert get_follow_up_suggestions is not None
        assert callable(get_follow_up_suggestions)
    
    def test_get_focus_recommendations_importable(self):
        """get_focus_recommendations should be importable."""
        from src.app.agents.arjuna import get_focus_recommendations
        
        assert get_focus_recommendations is not None
        assert callable(get_focus_recommendations)
    
    def test_get_system_context_importable(self):
        """get_system_context should be importable."""
        from src.app.agents.arjuna import get_system_context
        
        assert get_system_context is not None
        assert callable(get_system_context)
    
    def test_parse_assistant_intent_importable(self):
        """parse_assistant_intent should be importable."""
        from src.app.agents.arjuna import parse_assistant_intent
        
        assert parse_assistant_intent is not None
        assert callable(parse_assistant_intent)
    
    def test_execute_intent_importable(self):
        """execute_intent should be importable."""
        from src.app.agents.arjuna import execute_intent
        
        assert execute_intent is not None
        assert callable(execute_intent)
    
    def test_quick_ask_importable(self):
        """quick_ask should be importable."""
        from src.app.agents.arjuna import quick_ask
        
        assert quick_ask is not None
        assert callable(quick_ask)
    
    def test_quick_ask_sync_importable(self):
        """quick_ask_sync should be importable."""
        from src.app.agents.arjuna import quick_ask_sync
        
        assert quick_ask_sync is not None
        assert callable(quick_ask_sync)
    
    def test_interpret_user_status_adapter_importable(self):
        """interpret_user_status_adapter should be importable."""
        from src.app.agents.arjuna import interpret_user_status_adapter
        
        assert interpret_user_status_adapter is not None
        assert callable(interpret_user_status_adapter)
