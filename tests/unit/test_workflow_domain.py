# tests/unit/test_workflow_domain.py
"""
Unit tests for Workflow Domain.

Tests the workflow domain API routes:
- Modes: workflow mode settings, suggested mode detection
- Progress: checklist progress tracking
- Timer: timer session management
- Jobs: background job execution
- Tracing: LangSmith status
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import json


# =============================================================================
# ROUTER STRUCTURE TESTS
# =============================================================================

class TestWorkflowRouterStructure:
    """Tests for workflow router structure and mounting."""
    
    def test_workflow_router_imports(self):
        """Workflow router should be importable."""
        from src.app.domains.workflow import workflow_router
        
        assert workflow_router is not None
    
    def test_sub_routers_combined(self):
        """Combined router should include all sub-routers."""
        from src.app.domains.workflow.api import router
        
        # Router should have routes (at least from sub-routers)
        assert router is not None
    
    def test_modes_router_exists(self):
        """Modes sub-router should exist."""
        from src.app.domains.workflow.api.modes import router
        
        assert router is not None
    
    def test_progress_router_exists(self):
        """Progress sub-router should exist."""
        from src.app.domains.workflow.api.progress import router
        
        assert router is not None
    
    def test_timer_router_exists(self):
        """Timer sub-router should exist."""
        from src.app.domains.workflow.api.timer import router
        
        assert router is not None
    
    def test_jobs_router_exists(self):
        """Jobs sub-router should exist."""
        from src.app.domains.workflow.api.jobs import router
        
        assert router is not None
    
    def test_tracing_router_exists(self):
        """Tracing sub-router should exist."""
        from src.app.domains.workflow.api.tracing import router
        
        assert router is not None


# =============================================================================
# TIMER UTILITY TESTS
# =============================================================================

class TestTimerUtilities:
    """Tests for timer utility functions."""
    
    def test_format_duration_seconds(self):
        """Should format seconds correctly."""
        from src.app.domains.workflow.api.timer import _format_duration
        
        assert _format_duration(30) == "30s"
        assert _format_duration(59) == "59s"
    
    def test_format_duration_minutes(self):
        """Should format minutes correctly."""
        from src.app.domains.workflow.api.timer import _format_duration
        
        result = _format_duration(90)
        assert "1m" in result
        assert "30s" in result
    
    def test_format_duration_hours(self):
        """Should format hours correctly."""
        from src.app.domains.workflow.api.timer import _format_duration
        
        result = _format_duration(3700)  # 1h 1m 40s
        assert "1h" in result


# =============================================================================
# JOBS CONFIGURATION TESTS
# =============================================================================

class TestJobsConfiguration:
    """Tests for background jobs configuration."""
    
    def test_job_configs_importable(self):
        """JOB_CONFIGS should be importable."""
        from src.app.services.background_jobs import JOB_CONFIGS
        
        assert JOB_CONFIGS is not None
        assert isinstance(JOB_CONFIGS, dict)
    
    def test_job_configs_have_required_fields(self):
        """Each job config should have required fields."""
        from src.app.services.background_jobs import JOB_CONFIGS
        
        for name, config in JOB_CONFIGS.items():
            assert hasattr(config, 'name'), f"Job {name} missing 'name'"
            assert hasattr(config, 'description'), f"Job {name} missing 'description'"
            assert hasattr(config, 'enabled'), f"Job {name} missing 'enabled'"


# =============================================================================
# SPRINT MODE DETECT TESTS
# =============================================================================

class TestSprintModeDetect:
    """Tests for sprint mode detection logic."""
    
    def test_sprint_mode_detect_job_exists(self):
        """SprintModeDetectJob should be importable."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob()
        assert job is not None
    
    def test_sprint_mode_detect_has_modes(self):
        """SprintModeDetectJob should have MODES defined."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob()
        assert hasattr(job, 'MODES')
        assert isinstance(job.MODES, dict)
    
    def test_detect_suggested_mode_returns_valid(self):
        """detect_suggested_mode should return a valid mode letter."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob()
        mode = job.detect_suggested_mode()
        
        # Should return A, B, C, or D
        assert mode in ["A", "B", "C", "D"]
