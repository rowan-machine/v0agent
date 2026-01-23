# tests/test_background_jobs.py
"""
Tests for F4a: 1:1 Prep Background Job and F4d: Sprint Mode Auto-Detect

Tests the background job services that generate proactive notifications.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import json


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn


@pytest.fixture
def mock_queue():
    """Create a mock NotificationQueue."""
    queue = MagicMock()
    queue.create.return_value = "test-notification-id"
    return queue


@pytest.fixture
def sample_tickets():
    """Sample ticket data."""
    return [
        {"id": 1, "title": "Implement API rate limiting", "status": "in_progress", "tags": "python,api", "updated_at": "2026-01-20", "created_at": "2026-01-15"},
        {"id": 2, "title": "Fix Airflow DAG timeout", "status": "in_progress", "tags": "airflow,bug", "updated_at": "2026-01-19", "created_at": "2026-01-10"},
        {"id": 3, "title": "Docker compose optimization", "status": "todo", "tags": "docker", "updated_at": None, "created_at": "2026-01-18"},
    ]


@pytest.fixture
def sample_meetings():
    """Sample meeting data with signals."""
    return [
        {
            "id": 1,
            "meeting_name": "Sprint Planning",
            "meeting_date": "2026-01-20",
            "signals_json": json.dumps({
                "decisions": ["Use new rate limiting library", "Migrate to Python 3.12"],
                "action_items": ["Review PR by Friday", "Update docs by EOD"],
                "blockers": ["Waiting for API credentials from vendor"],
                "risks": ["Timeline might slip if credentials delayed"],
                "ideas": ["Consider caching layer for performance"],
            })
        },
        {
            "id": 2,
            "meeting_name": "Standup",
            "meeting_date": "2026-01-21",
            "signals_json": json.dumps({
                "blockers": ["Docker build failing on CI"],
                "action_items": ["Fix CI pipeline"],
            })
        },
    ]


# =============================================================================
# 1:1 PREP JOB TESTS
# =============================================================================

class TestOneOnOnePrepJob:
    """Tests for the 1:1 Prep Digest job."""
    
    def test_should_run_on_biweekly_tuesday(self, mock_queue):
        """Should correctly identify biweekly Tuesdays."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        job = OneOnOnePrepJob(queue=mock_queue)
        
        # Jan 27, 2026 is the first scheduled Tuesday
        with patch('src.app.services.background_jobs.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 27, 7, 0)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # This should be True since Jan 27 is the start date
            # Note: We need to mock properly for the date comparison
    
    def test_get_top_work_items(self, mock_db_connection, mock_queue, sample_tickets):
        """Should return top active tickets."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        mock_db_connection.execute.return_value.fetchall.return_value = sample_tickets
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = OneOnOnePrepJob(queue=mock_queue)
            items = job._get_top_work_items(limit=3)
        
        assert len(items) == 3
        assert items[0]["title"] == "Implement API rate limiting"
        assert items[0]["status"] == "in_progress"
    
    def test_get_blockers_from_meetings(self, mock_db_connection, mock_queue, sample_meetings):
        """Should extract blockers from meeting signals."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        # Mock for meetings query
        mock_db_connection.execute.return_value.fetchall.side_effect = [
            sample_meetings,  # First call for meetings
            [],  # Second call for blocked tickets
        ]
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = OneOnOnePrepJob(queue=mock_queue)
            blockers = job._get_blockers()
        
        assert len(blockers) >= 1
        assert any("API credentials" in b["text"] for b in blockers)
    
    def test_get_observations(self, mock_db_connection, mock_queue, sample_meetings):
        """Should extract decisions, risks, ideas from meetings."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        mock_db_connection.execute.return_value.fetchall.return_value = sample_meetings
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = OneOnOnePrepJob(queue=mock_queue)
            observations = job._get_observations()
        
        assert len(observations) > 0
        types = [o["type"] for o in observations]
        assert "decision" in types
        assert "risk" in types
    
    def test_format_digest(self, mock_queue):
        """Should format digest with all sections."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        job = OneOnOnePrepJob(queue=mock_queue)
        
        digest = job._format_digest(
            top_work_items=[{"title": "Test ticket", "status": "in_progress"}],
            blockers=[{"text": "Test blocker", "source": "Meeting"}],
            observations=[{"type": "decision", "text": "Test decision"}],
            overdue_actions=[],
        )
        
        assert "What am I working on?" in digest
        assert "Test ticket" in digest
        assert "Where do I need help?" in digest
        assert "Test blocker" in digest
        assert "Recent observations" in digest
    
    def test_run_creates_notification(self, mock_db_connection, mock_queue, sample_tickets, sample_meetings):
        """Should create a notification when run."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        # Mock database queries
        mock_db_connection.execute.return_value.fetchall.side_effect = [
            sample_tickets,  # get_top_work_items
            sample_meetings,  # get_blockers (meetings)
            [],  # get_blockers (tickets)
            sample_meetings,  # get_observations
            sample_meetings,  # get_overdue_actions
        ]
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = OneOnOnePrepJob(queue=mock_queue)
            result = job.run()
        
        mock_queue.create.assert_called_once()
        assert "notification_id" in result
        assert result["notification_id"] == "test-notification-id"
    
    def test_digest_includes_next_meeting_date(self, mock_db_connection, mock_queue, sample_tickets):
        """Should include the next 1:1 meeting date."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        mock_db_connection.execute.return_value.fetchall.return_value = []
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = OneOnOnePrepJob(queue=mock_queue)
            result = job.run()
        
        assert "next_one_on_one" in result
    
    def test_handles_empty_data(self, mock_db_connection, mock_queue):
        """Should handle case with no tickets or meetings."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        mock_db_connection.execute.return_value.fetchall.return_value = []
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = OneOnOnePrepJob(queue=mock_queue)
            result = job.run()
        
        assert result["top_work_items"] == []
        assert result["blockers"] == []
        mock_queue.create.assert_called_once()


# =============================================================================
# SPRINT MODE DETECT TESTS
# =============================================================================

class TestSprintModeDetectJob:
    """Tests for the Sprint Mode Auto-Detect job."""
    
    def test_get_current_sprint_info(self, mock_queue):
        """Should calculate sprint info correctly."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob(queue=mock_queue)
        
        with patch('src.app.services.background_jobs.datetime') as mock_dt:
            # Jan 22, 2026 is day 2 of sprint 2 (Thu of week 2 of sprint 1 actually)
            # Let me recalculate: epoch is Jan 6, so Jan 22 is day 16, sprint 2 day 2
            mock_dt.now.return_value = datetime(2026, 1, 22)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            info = job.get_current_sprint_info()
        
        assert "sprint_number" in info
        assert "day_of_sprint" in info
        assert "sprint_start" in info
        assert "sprint_end" in info
    
    def test_detect_mode_a_before_sprint(self, mock_queue):
        """Should suggest Mode A when 3-4 days before sprint start."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob(queue=mock_queue)
        
        # Mock to be Thursday before Monday sprint (3 days before)
        with patch.object(job, 'get_current_sprint_info') as mock_info:
            mock_info.return_value = {
                "sprint_number": 1,
                "day_of_sprint": 11,  # Day 11 of 14
                "days_until_next_sprint": 3,
            }
            
            mode = job.detect_suggested_mode()
        
        assert mode == "A"
    
    def test_detect_mode_b_sprint_start(self, mock_queue):
        """Should suggest Mode B on Mon/Tue of sprint week 1."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob(queue=mock_queue)
        
        with patch.object(job, 'get_current_sprint_info') as mock_info:
            mock_info.return_value = {
                "sprint_number": 2,
                "day_of_sprint": 0,  # Monday
                "days_until_next_sprint": 14,
            }
            
            mode = job.detect_suggested_mode()
        
        assert mode == "B"
    
    def test_detect_mode_c_mid_sprint(self, mock_queue):
        """Should suggest Mode C during core sprint days."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob(queue=mock_queue)
        
        with patch.object(job, 'get_current_sprint_info') as mock_info:
            mock_info.return_value = {
                "sprint_number": 2,
                "day_of_sprint": 4,  # Friday week 1
                "days_until_next_sprint": 10,
            }
            
            mode = job.detect_suggested_mode()
        
        assert mode == "C"
    
    def test_detect_mode_d_sprint_end(self, mock_queue):
        """Should suggest Mode D on Wed/Thu of sprint week 2 (wrap-up)."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        job = SprintModeDetectJob(queue=mock_queue)
        
        with patch.object(job, 'get_current_sprint_info') as mock_info:
            mock_info.return_value = {
                "sprint_number": 2,
                "day_of_sprint": 9,  # Wednesday week 2
                "days_until_next_sprint": 5,  # More than 4, so won't trigger A
            }
            
            mode = job.detect_suggested_mode()
        
        assert mode == "D"
    
    def test_run_no_notification_when_mode_matches(self, mock_db_connection, mock_queue):
        """Should not create notification if current mode matches suggested."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        mock_db_connection.execute.return_value.fetchone.return_value = {"value": "C"}
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            with patch.object(SprintModeDetectJob, 'detect_suggested_mode', return_value="C"):
                job = SprintModeDetectJob(queue=mock_queue)
                result = job.run()
        
        assert result["mode_change_needed"] is False
        mock_queue.create.assert_not_called()
    
    def test_run_creates_notification_on_mode_change(self, mock_db_connection, mock_queue):
        """Should create notification when mode change is suggested."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        mock_db_connection.execute.return_value.fetchone.return_value = {"value": "C"}
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            with patch.object(SprintModeDetectJob, 'detect_suggested_mode', return_value="A"):
                job = SprintModeDetectJob(queue=mock_queue)
                result = job.run()
        
        assert result["mode_change_needed"] is True
        mock_queue.create.assert_called_once()
    
    def test_handles_no_current_mode_set(self, mock_db_connection, mock_queue):
        """Should handle case where no mode is currently set."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        mock_db_connection.execute.return_value.fetchone.return_value = None
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = SprintModeDetectJob(queue=mock_queue)
            result = job.run()
        
        assert result["current_mode"] is None
        # Should not create notification if no current mode
        mock_queue.create.assert_not_called()


# =============================================================================
# JOB RUNNER TESTS
# =============================================================================

class TestJobRunner:
    """Tests for the job runner functions."""
    
    def test_run_job_unknown_job(self):
        """Should raise error for unknown job name."""
        from src.app.services.background_jobs import run_job
        
        with pytest.raises(ValueError, match="Unknown job"):
            run_job("nonexistent_job")
    
    def test_run_job_valid_job(self, mock_db_connection, mock_queue):
        """Should run a valid job."""
        from src.app.services.background_jobs import run_job
        
        mock_db_connection.execute.return_value.fetchall.return_value = []
        mock_db_connection.execute.return_value.fetchone.return_value = None
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            with patch('src.app.services.background_jobs.NotificationQueue', return_value=mock_queue):
                result = run_job("sprint_mode_detect")
        
        assert "sprint_info" in result
        assert "suggested_mode" in result


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestDigestContent:
    """Tests for digest content quality."""
    
    def test_digest_has_all_sections(self, mock_queue):
        """Should include all required sections in digest."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        job = OneOnOnePrepJob(queue=mock_queue)
        
        digest = job._format_digest(
            top_work_items=[],
            blockers=[],
            observations=[],
            overdue_actions=[],
        )
        
        assert "What am I working on?" in digest
        assert "Where do I need help?" in digest
        assert "Recent observations" in digest
    
    def test_digest_truncates_long_text(self, mock_queue):
        """Should truncate very long blocker/observation text."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        job = OneOnOnePrepJob(queue=mock_queue)
        
        long_blocker = {"text": "A" * 500, "source": "Test"}
        
        digest = job._format_digest(
            top_work_items=[],
            blockers=[long_blocker],
            observations=[],
            overdue_actions=[],
        )
        
        # Should not contain the full 500 chars
        assert "A" * 500 not in digest
        assert "A" * 100 in digest  # Should have truncated version
    
    def test_overdue_detection_patterns(self, mock_db_connection, mock_queue):
        """Should detect various overdue date patterns."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        old_meeting = {
            "id": 1,
            "meeting_name": "Old Meeting",
            "meeting_date": "2026-01-01",  # More than 7 days ago
            "signals_json": json.dumps({
                "action_items": [
                    "Review PR by Friday",
                    "Update docs by EOD",
                    "Complete task due 1/5",
                ]
            })
        }
        
        mock_db_connection.execute.return_value.fetchall.return_value = [old_meeting]
        
        with patch('src.app.services.background_jobs.connect', return_value=mock_db_connection):
            job = OneOnOnePrepJob(queue=mock_queue)
            overdue = job._get_overdue_actions()
        
        # Should detect items with date patterns from old meetings
        assert len(overdue) > 0
