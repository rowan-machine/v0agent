# tests/unit/test_search_domain.py
"""
Tests for Search Domain

Validates the search domain structure and exports.
"""

import pytest


class TestSearchDomainStructure:
    """Test search domain module structure."""

    def test_search_domain_exists(self):
        """Test search domain package exists."""
        from src.app.domains import search
        assert search is not None

    def test_search_api_exists(self):
        """Test search API subpackage exists."""
        from src.app.domains.search import api
        assert api is not None

    def test_search_domain_router_exists(self):
        """Test search domain has router."""
        from src.app.domains.search.api import router
        assert router is not None


class TestSearchAPIModules:
    """Test search API module structure."""

    def test_keyword_module_exists(self):
        """Test keyword search module exists."""
        from src.app.domains.search.api import keyword
        assert keyword is not None

    def test_keyword_router_exists(self):
        """Test keyword module has router."""
        from src.app.domains.search.api.keyword import router
        assert router is not None

    def test_semantic_module_exists(self):
        """Test semantic search module exists."""
        from src.app.domains.search.api import semantic
        assert semantic is not None

    def test_semantic_router_exists(self):
        """Test semantic module has router."""
        from src.app.domains.search.api.semantic import router
        assert router is not None

    def test_unified_module_exists(self):
        """Test unified search module exists."""
        from src.app.domains.search.api import unified
        assert unified is not None

    def test_unified_router_exists(self):
        """Test unified module has router."""
        from src.app.domains.search.api.unified import router
        assert router is not None


class TestSearchRouterRoutes:
    """Test search domain router has expected routes."""

    def test_keyword_router_has_routes(self):
        """Test keyword router has registered routes."""
        from src.app.domains.search.api.keyword import router
        routes = [route.path for route in router.routes]
        assert len(routes) > 0

    def test_semantic_router_has_routes(self):
        """Test semantic router has registered routes."""
        from src.app.domains.search.api.semantic import router
        routes = [route.path for route in router.routes]
        assert len(routes) > 0

    def test_unified_router_has_routes(self):
        """Test unified router has registered routes."""
        from src.app.domains.search.api.unified import router
        routes = [route.path for route in router.routes]
        assert len(routes) > 0


class TestCareerRepositoryStructure:
    """Test career repository exists and is well-structured."""

    def test_career_repository_module_exists(self):
        """Test career_repository module exists."""
        from src.app.repositories import career_repository
        assert career_repository is not None

    def test_career_repository_class_exists(self):
        """Test CareerRepository abstract class exists."""
        from src.app.repositories.career_repository import CareerRepository
        assert CareerRepository is not None

    def test_supabase_career_repository_exists(self):
        """Test SupabaseCareerRepository implementation exists."""
        from src.app.repositories.career_repository import SupabaseCareerRepository
        assert SupabaseCareerRepository is not None

    def test_get_career_repository_factory_exists(self):
        """Test factory function exists."""
        from src.app.repositories import get_career_repository
        assert callable(get_career_repository)


class TestCareerDataClasses:
    """Test career data classes."""

    def test_career_profile_dataclass_exists(self):
        """Test CareerProfile dataclass exists."""
        from src.app.repositories.career_repository import CareerProfile
        assert CareerProfile is not None

    def test_career_profile_from_dict(self):
        """Test CareerProfile.from_dict creates instance correctly."""
        from src.app.repositories.career_repository import CareerProfile
        
        data = {
            "id": 1,
            "current_role": "Software Engineer",
            "target_role": "Senior Engineer",
            "strengths": "Python, FastAPI",
            "goals": "Architecture mastery"
        }
        
        profile = CareerProfile.from_dict(data)
        
        assert profile.id == 1
        assert profile.current_role == "Software Engineer"
        assert profile.target_role == "Senior Engineer"

    def test_career_memory_dataclass_exists(self):
        """Test CareerMemory dataclass exists."""
        from src.app.repositories.career_repository import CareerMemory
        assert CareerMemory is not None

    def test_standup_update_dataclass_exists(self):
        """Test StandupUpdate dataclass exists."""
        from src.app.repositories.career_repository import StandupUpdate
        assert StandupUpdate is not None

    def test_skill_entry_dataclass_exists(self):
        """Test SkillEntry dataclass exists."""
        from src.app.repositories.career_repository import SkillEntry
        assert SkillEntry is not None

    def test_career_suggestion_dataclass_exists(self):
        """Test CareerSuggestion dataclass exists."""
        from src.app.repositories.career_repository import CareerSuggestion
        assert CareerSuggestion is not None


class TestCareerRepositoryInterface:
    """Test career repository abstract interface."""

    def test_repository_has_get_profile_method(self):
        """Test repository has get_profile method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "get_profile")

    def test_repository_has_update_profile_method(self):
        """Test repository has update_profile method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "update_profile")

    def test_repository_has_get_memories_method(self):
        """Test repository has get_memories method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "get_memories")

    def test_repository_has_delete_memory_method(self):
        """Test repository has delete_memory method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "delete_memory")

    def test_repository_has_get_skills_method(self):
        """Test repository has get_skills method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "get_skills")

    def test_repository_has_get_standups_method(self):
        """Test repository has get_standups method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "get_standups")

    def test_repository_has_get_standup_by_date_method(self):
        """Test repository has get_standup_by_date method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "get_standup_by_date")

    def test_repository_has_get_suggestions_method(self):
        """Test repository has get_suggestions method."""
        from src.app.repositories.career_repository import CareerRepository
        assert hasattr(CareerRepository, "get_suggestions")


class TestCareerDomainStructure:
    """Test career domain module structure."""

    def test_career_domain_exists(self):
        """Test career domain package exists."""
        from src.app.domains import career
        assert career is not None

    def test_career_api_exists(self):
        """Test career API subpackage exists."""
        from src.app.domains.career import api
        assert api is not None

    def test_career_domain_router_exists(self):
        """Test career domain has router."""
        from src.app.domains.career.api import router
        assert router is not None


class TestCareerAPIModules:
    """Test career API module structure."""

    def test_profile_module_exists(self):
        """Test profile module exists."""
        from src.app.domains.career.api import profile
        assert profile is not None

    def test_skills_module_exists(self):
        """Test skills module exists."""
        from src.app.domains.career.api import skills
        assert skills is not None

    def test_standups_module_exists(self):
        """Test standups module exists."""
        from src.app.domains.career.api import standups
        assert standups is not None

    def test_suggestions_module_exists(self):
        """Test suggestions module exists."""
        from src.app.domains.career.api import suggestions
        assert suggestions is not None

    def test_memories_module_exists(self):
        """Test memories module exists."""
        from src.app.domains.career.api import memories
        assert memories is not None

    def test_chat_module_exists(self):
        """Test chat module exists."""
        from src.app.domains.career.api import chat
        assert chat is not None

    def test_insights_module_exists(self):
        """Test insights module exists."""
        from src.app.domains.career.api import insights
        assert insights is not None

    def test_code_locker_module_exists(self):
        """Test code_locker module exists."""
        from src.app.domains.career.api import code_locker
        assert code_locker is not None

    def test_projects_module_exists(self):
        """Test projects module exists."""
        from src.app.domains.career.api import projects
        assert projects is not None
