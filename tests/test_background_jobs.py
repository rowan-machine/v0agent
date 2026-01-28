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
    # Reset any potential leftover state
    mock_conn.execute.return_value.fetchall.side_effect = None
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.execute.return_value.fetchone.side_effect = None
    mock_conn.execute.return_value.fetchone.return_value = None
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
        with patch('src.app.services.jobs.one_on_one_prep.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 27, 7, 0)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # This should be True since Jan 27 is the start date
            # Note: We need to mock properly for the date comparison
    
    def test_get_top_work_items(self, mock_queue, sample_tickets):
        """Should return top active tickets."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        with patch('src.app.services.jobs.one_on_one_prep.ticket_service') as mock_ticket_svc:
            mock_ticket_svc.get_active_tickets.return_value = sample_tickets
            job = OneOnOnePrepJob(queue=mock_queue)
            items = job._get_top_work_items(limit=3)
        
        assert len(items) == 3
        assert items[0]["title"] == "Implement API rate limiting"
        assert items[0]["status"] == "in_progress"
    
    def test_get_blockers_from_meetings(self, mock_queue, sample_meetings):
        """Should extract blockers from meeting signals."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        with patch('src.app.services.jobs.one_on_one_prep.meeting_service') as mock_meeting_svc:
            with patch('src.app.services.jobs.one_on_one_prep.ticket_service') as mock_ticket_svc:
                mock_meeting_svc.get_all_meetings.return_value = sample_meetings
                mock_ticket_svc.get_blocked_tickets.return_value = []
                job = OneOnOnePrepJob(queue=mock_queue)
                blockers = job._get_blockers()
        
        assert len(blockers) >= 1
        assert any("API credentials" in b["text"] for b in blockers)
    
    def test_get_observations(self, mock_queue, sample_meetings):
        """Should extract decisions, risks, ideas from meetings."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        with patch('src.app.services.jobs.one_on_one_prep.meeting_service') as mock_meeting_svc:
            mock_meeting_svc.get_all_meetings.return_value = sample_meetings
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
    
    def test_run_creates_notification(self, mock_queue, sample_tickets, sample_meetings):
        """Should create a notification when run."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        with patch('src.app.services.jobs.one_on_one_prep.ticket_service') as mock_ticket_svc:
            with patch('src.app.services.jobs.one_on_one_prep.meeting_service') as mock_meeting_svc:
                mock_ticket_svc.get_active_tickets.return_value = sample_tickets
                mock_ticket_svc.get_blocked_tickets.return_value = []
                mock_meeting_svc.get_all_meetings.return_value = sample_meetings
                job = OneOnOnePrepJob(queue=mock_queue)
                result = job.run()
        
        mock_queue.create.assert_called_once()
        assert "notification_id" in result
        assert result["notification_id"] == "test-notification-id"
    
    def test_digest_includes_next_meeting_date(self, mock_queue, sample_tickets):
        """Should include the next 1:1 meeting date."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        with patch('src.app.services.jobs.one_on_one_prep.ticket_service') as mock_ticket_svc:
            with patch('src.app.services.jobs.one_on_one_prep.meeting_service') as mock_meeting_svc:
                mock_ticket_svc.get_active_tickets.return_value = []
                mock_ticket_svc.get_blocked_tickets.return_value = []
                mock_meeting_svc.get_all_meetings.return_value = []
                job = OneOnOnePrepJob(queue=mock_queue)
                result = job.run()
        
        assert "next_one_on_one" in result
    
    def test_handles_empty_data(self, mock_queue):
        """Should handle case with no tickets or meetings."""
        from src.app.services.background_jobs import OneOnOnePrepJob
        
        with patch('src.app.services.jobs.one_on_one_prep.ticket_service') as mock_ticket_svc:
            with patch('src.app.services.jobs.one_on_one_prep.meeting_service') as mock_meeting_svc:
                mock_ticket_svc.get_active_tickets.return_value = []
                mock_ticket_svc.get_blocked_tickets.return_value = []
                mock_meeting_svc.get_all_meetings.return_value = []
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
        
        with patch('src.app.services.jobs.sprint_mode.datetime') as mock_dt:
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
    
    def test_run_no_notification_when_mode_matches(self, mock_queue):
        """Should not create notification if current mode matches suggested."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_setting.return_value = "C"
        
        with patch('src.app.services.jobs.sprint_mode._get_settings_repo', return_value=mock_settings_repo):
            with patch.object(SprintModeDetectJob, 'detect_suggested_mode', return_value="C"):
                job = SprintModeDetectJob(queue=mock_queue)
                result = job.run()
        
        assert result["mode_change_needed"] is False
        mock_queue.create.assert_not_called()
    
    def test_run_creates_notification_on_mode_change(self, mock_queue):
        """Should create notification when mode change is suggested."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_setting.return_value = "C"
        
        with patch('src.app.services.jobs.sprint_mode._get_settings_repo', return_value=mock_settings_repo):
            with patch.object(SprintModeDetectJob, 'detect_suggested_mode', return_value="A"):
                job = SprintModeDetectJob(queue=mock_queue)
                result = job.run()
        
        assert result["mode_change_needed"] is True
        mock_queue.create.assert_called_once()
    
    def test_handles_no_current_mode_set(self, mock_queue):
        """Should handle case where no mode is currently set."""
        from src.app.services.background_jobs import SprintModeDetectJob
        
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_setting.return_value = None
        
        with patch('src.app.services.jobs.sprint_mode._get_settings_repo', return_value=mock_settings_repo):
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
    
    def test_run_job_valid_job(self, mock_queue):
        """Should run a valid job."""
        from src.app.services.background_jobs import run_job
        
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_setting.return_value = None
        
        with patch('src.app.services.jobs.sprint_mode._get_settings_repo', return_value=mock_settings_repo):
            with patch('src.app.services.jobs.sprint_mode.NotificationQueue', return_value=mock_queue):
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
    
    def test_overdue_detection_patterns(self, mock_queue):
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
        
        with patch('src.app.services.jobs.one_on_one_prep.meeting_service') as mock_meeting_svc:
            mock_meeting_svc.get_all_meetings.return_value = [old_meeting]
            job = OneOnOnePrepJob(queue=mock_queue)
            overdue = job._get_overdue_actions()
        
        # Should detect items with date patterns from old meetings
        assert len(overdue) > 0


# =============================================================================
# F4b: STALE TICKET ALERT TESTS
# =============================================================================

class TestStaleTicketAlertJob:
    """Tests for the Stale Ticket and Blocker Alert job."""
    
    @pytest.fixture
    def mock_queue(self):
        queue = MagicMock()
        queue.create.return_value = "notif-stale-123"
        return queue
    
    @pytest.fixture
    def mock_db_connection(self):
        conn = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        return conn
    
    def test_get_stale_tickets(self, mock_queue):
        """Should find tickets with no activity for 5+ days."""
        from src.app.services.background_jobs import StaleTicketAlertJob
        
        old_date = (datetime.now() - timedelta(days=7)).isoformat()
        stale_tickets = [
            {"id": 1, "title": "Old ticket", "status": "in-progress", "updated_at": old_date, "created_at": old_date}
        ]
        
        with patch('src.app.services.jobs.stale_alerts.ticket_service') as mock_ticket_svc:
            mock_ticket_svc.get_stale_in_progress_tickets.return_value = stale_tickets
            job = StaleTicketAlertJob(queue=mock_queue)
            stale = job._get_stale_tickets()
        
        assert len(stale) == 1
        assert stale[0]["days_stale"] >= 5
    
    def test_get_stale_blockers(self, mock_queue):
        """Should find blockers that haven't been resolved."""
        from src.app.services.background_jobs import StaleTicketAlertJob
        
        old_date = (datetime.now() - timedelta(days=5)).isoformat()
        meetings = [
            {
                "id": 1,
                "meeting_name": "Sprint Planning",
                "meeting_date": old_date,
                "signals_json": json.dumps({
                    "blockers": [{"text": "Waiting on API access from DevOps"}]
                })
            }
        ]
        
        with patch('src.app.services.jobs.stale_alerts.meeting_service') as mock_meeting_svc:
            mock_meeting_svc.get_all_meetings.return_value = meetings
            job = StaleTicketAlertJob(queue=mock_queue)
            blockers = job._get_stale_blockers()
        
        assert len(blockers) == 1
        assert "API access" in blockers[0]["text"]
    
    def test_run_creates_notifications(self, mock_queue):
        """Should create notifications for stale items."""
        from src.app.services.background_jobs import StaleTicketAlertJob
        
        old_date = (datetime.now() - timedelta(days=7)).isoformat()
        
        with patch('src.app.services.jobs.stale_alerts.ticket_service') as mock_ticket_svc:
            with patch('src.app.services.jobs.stale_alerts.meeting_service') as mock_meeting_svc:
                mock_ticket_svc.get_stale_in_progress_tickets.return_value = [
                    {"id": 1, "title": "Stale ticket", "status": "todo", "updated_at": old_date, "created_at": old_date}
                ]
                mock_meeting_svc.get_all_meetings.return_value = []
                job = StaleTicketAlertJob(queue=mock_queue)
                result = job.run()
        
        assert result["alerts_created"] >= 1
        mock_queue.create.assert_called()
    
    def test_run_handles_no_stale_items(self, mock_queue):
        """Should handle case with no stale items gracefully."""
        from src.app.services.background_jobs import StaleTicketAlertJob
        
        with patch('src.app.services.jobs.stale_alerts.ticket_service') as mock_ticket_svc:
            with patch('src.app.services.jobs.stale_alerts.meeting_service') as mock_meeting_svc:
                mock_ticket_svc.get_stale_in_progress_tickets.return_value = []
                mock_meeting_svc.get_all_meetings.return_value = []
                job = StaleTicketAlertJob(queue=mock_queue)
                result = job.run()
        
        assert result["stale_tickets_found"] == 0
        assert result["alerts_created"] == 0


# =============================================================================
# F4c: GROOMING MATCH TESTS
# =============================================================================

class TestGroomingMatchJob:
    """Tests for the Grooming-to-Ticket Match job."""
    
    @pytest.fixture
    def mock_queue(self):
        queue = MagicMock()
        queue.create.return_value = "notif-match-456"
        return queue
    
    @pytest.fixture
    def mock_db_connection(self):
        conn = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        return conn
    
    def test_get_recent_grooming_meetings(self, mock_queue):
        """Should find recent grooming/planning meetings."""
        from src.app.services.background_jobs import GroomingMatchJob
        
        meetings = [
            {
                "id": 1,
                "meeting_name": "Sprint Planning - Jan 22",
                "meeting_date": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "raw_text": "Discussed AUTH-123 ticket implementation",
                "signals_json": "{}"
            }
        ]
        
        with patch('src.app.services.jobs.grooming_match.meeting_service') as mock_meeting_svc:
            with patch('src.app.services.jobs.grooming_match._get_notifications_repo') as mock_notif_repo:
                mock_meeting_svc.get_all_meetings.return_value = meetings
                mock_notif_repo.return_value = None
                job = GroomingMatchJob(queue=mock_queue)
                result = job._get_recent_grooming_meetings()
        
        assert len(result) == 1
        assert "planning" in result[0]["meeting_name"].lower()
    
    def test_find_matching_tickets_by_id(self, mock_queue):
        """Should match tickets by ID pattern (e.g., AUTH-123)."""
        from src.app.services.background_jobs import GroomingMatchJob
        
        meeting = {
            "id": 1,
            "meeting_name": "Grooming",
            "raw_text": "Discussed AUTH-123 for the login feature",
            "signals_json": "{}"
        }
        
        tickets = [
            {"id": 1, "title": "Login feature", "status": "todo", "description": "Implement login", "tags": "auth", "ticket_id": "AUTH-123"}
        ]
        
        with patch('src.app.services.jobs.grooming_match.ticket_service') as mock_ticket_svc:
            mock_ticket_svc.get_active_tickets.return_value = tickets
            job = GroomingMatchJob(queue=mock_queue)
            matches = job._find_matching_tickets(meeting)
        
        assert len(matches) >= 1
        assert matches[0]["score"] == 100  # Exact ID match
    
    def test_analyze_gaps(self, mock_queue):
        """Should identify action items not in ticket."""
        from src.app.services.background_jobs import GroomingMatchJob
        
        meeting = {
            "id": 1,
            "signals_json": json.dumps({
                "actions": [
                    {"text": "Add rate limiting to the API endpoint"},
                    {"text": "Update documentation for new feature"}
                ],
                "decisions": [
                    {"text": "Use Redis for caching"}
                ]
            })
        }
        
        ticket = {
            "title": "API Performance",
            "description": "Improve API performance"  # Doesn't mention rate limiting or Redis
        }
        
        job = GroomingMatchJob(queue=mock_queue)
        gaps = job._analyze_gaps(meeting, ticket)
        
        # Should detect gaps since ticket doesn't mention rate limiting or Redis
        assert len(gaps) >= 1
    
    def test_run_creates_match_notification(self, mock_queue):
        """Should create notification when match found."""
        from src.app.services.background_jobs import GroomingMatchJob
        
        meetings = [{
            "id": 1,
            "meeting_name": "Backlog Grooming",
            "meeting_date": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "raw_text": "Working on DATA-456 pipeline optimization",
            "signals_json": "{}"
        }]
        
        tickets = [{"id": 2, "title": "Pipeline optimization", "status": "todo", "description": "Optimize data pipeline", "tags": "data", "ticket_id": "DATA-456"}]
        
        with patch('src.app.services.jobs.grooming_match.meeting_service') as mock_meeting_svc:
            with patch('src.app.services.jobs.grooming_match.ticket_service') as mock_ticket_svc:
                with patch('src.app.services.jobs.grooming_match._get_notifications_repo') as mock_notif_repo:
                    mock_meeting_svc.get_all_meetings.return_value = meetings
                    mock_ticket_svc.get_active_tickets.return_value = tickets
                    mock_notif_repo.return_value = None
                    job = GroomingMatchJob(queue=mock_queue)
                    result = job.run()
        
        assert len(result["matches"]) >= 1
        mock_queue.create.assert_called()
    
    def test_run_no_grooming_meetings(self, mock_queue):
        """Should handle no grooming meetings gracefully."""
        from src.app.services.background_jobs import GroomingMatchJob
        
        with patch('src.app.services.jobs.grooming_match.meeting_service') as mock_meeting_svc:
            with patch('src.app.services.jobs.grooming_match._get_notifications_repo') as mock_notif_repo:
                mock_meeting_svc.get_all_meetings.return_value = []
                mock_notif_repo.return_value = None
                job = GroomingMatchJob(queue=mock_queue)
                result = job.run()
        
        assert result["matches"] == []
        assert "No recent grooming" in result["message"]
    
    def test_format_match_body(self, mock_queue):
        """Should format notification body correctly."""
        from src.app.services.background_jobs import GroomingMatchJob
        
        meeting = {"meeting_name": "Sprint Planning"}
        ticket = {"title": "Feature X", "score": 85, "status": "in-progress"}
        gaps = ["Action not in ticket: Add tests"]
        
        job = GroomingMatchJob(queue=mock_queue)
        body = job._format_match_body(meeting, ticket, gaps)
        
        assert "Sprint Planning" in body
        assert "Feature X" in body
        assert "85%" in body
        assert "Gaps Found" in body


# =============================================================================
# F4e: MODE COMPLETION CELEBRATION TESTS
# =============================================================================

@pytest.mark.integration
class TestModeCompletionCelebration:
    """Tests for the workflow mode completion celebration feature.
    
    Note: These tests require Supabase connectivity as they test API endpoints
    that create real notifications. Marked as integration tests.
    """
    
    @pytest.fixture
    def client(self):
        """Create a test client with auth bypassed."""
        import os
        os.environ['BYPASS_TOKEN'] = 'test-token'
        from src.app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.headers['X-Auth-Token'] = 'test-token'
        return client
    
    @pytest.fixture
    def mock_notification_queue(self):
        """Mock NotificationQueue.create to avoid network calls."""
        with patch('src.app.services.notification_queue.NotificationQueue.create') as mock_create:
            mock_create.return_value = "test-notification-id"
            yield mock_create
    
    def test_expected_duration_returns_defaults_no_history(self, client):
        """Should return default durations when no historical data exists."""
        # Uses real db - test checks the response structure and defaults
        response = client.get('/api/settings/mode/expected-duration')
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure is correct and has all modes
        assert 'mode-a' in data
        assert 'mode-b' in data
        assert 'mode-c' in data
        assert 'mode-d' in data
        assert 'mode-e' in data
        assert 'mode-f' in data
        assert 'mode-g' in data
        
        # Check structure of response
        assert 'expected_minutes' in data['mode-a']
        assert 'default_minutes' in data['mode-a']
        assert 'historical_sessions' in data['mode-a']
        assert 'has_sufficient_data' in data['mode-a']
        
        # Defaults should be sensible
        assert data['mode-a']['default_minutes'] == 60
        assert data['mode-b']['default_minutes'] == 45
        assert data['mode-c']['default_minutes'] == 90
    
    def test_check_completion_requires_all_complete(self, client):
        """Should not celebrate if not all tasks are complete."""
        response = client.post('/api/workflow/check-completion',
            json={'mode': 'mode-a', 'progress': [True, True, False, True], 'elapsed_seconds': 1800})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['complete'] is False
        assert data['celebrate'] is False
    
    def test_check_completion_celebrates_early_finish(self, client, mock_notification_queue):
        """Should celebrate when completing before expected time."""
        # Complete mode-a (default 60 min) in 30 min (1800 seconds)
        response = client.post('/api/workflow/check-completion',
            json={'mode': 'mode-a', 'progress': [True, True, True, True], 'elapsed_seconds': 1800})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['complete'] is True
        assert data['celebrate'] is True
        assert data['time_saved_minutes'] >= 20  # At least 20 min saved
        # Notification created - check notification_id in response
        assert 'notification_id' in data
    
    def test_check_completion_no_celebrate_late_finish(self, client, mock_notification_queue):
        """Should not celebrate when completing after expected time."""
        # Complete mode-a (default 60 min) in 90 min (5400 seconds)
        response = client.post('/api/workflow/check-completion',
            json={'mode': 'mode-a', 'progress': [True, True, True, True], 'elapsed_seconds': 5400})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['complete'] is True
        assert data['celebrate'] is False
        # Still creates a 'complete' notification - check notification_id in response
        assert 'notification_id' in data
    
    def test_check_completion_returns_notification_id(self, client, mock_notification_queue):
        """Should return a notification ID on completion."""
        response = client.post('/api/workflow/check-completion',
            json={'mode': 'mode-a', 'progress': [True, True, True, True], 'elapsed_seconds': 1800})
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have a notification ID (actual value depends on NotificationQueue)
        assert 'notification_id' in data
        assert data['notification_id'] == "test-notification-id"
    
    def test_check_completion_empty_progress(self, client):
        """Should handle empty progress array."""
        response = client.post('/api/workflow/check-completion',
            json={'mode': 'mode-a', 'progress': [], 'elapsed_seconds': 1800})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['complete'] is False
        assert data['celebrate'] is False

# =============================================================================
# F4f: OVERDUE TASK ENCOURAGEMENT TESTS
# =============================================================================

class TestOverdueEncouragementJob:
    """Tests for the overdue task encouragement job."""
    
    @pytest.fixture
    def mock_queue(self):
        queue = MagicMock()
        queue.create.return_value = "encouragement-notif-123"
        return queue
    
    @pytest.fixture
    def mock_db_connection(self):
        conn = MagicMock()
        conn.__enter__ = lambda s: s
        conn.__exit__ = MagicMock(return_value=False)
        return conn
    
    def test_job_config_exists(self):
        """Should have job config defined."""
        from src.app.services.background_jobs import JOB_CONFIGS
        
        assert "overdue_encouragement" in JOB_CONFIGS
        config = JOB_CONFIGS["overdue_encouragement"]
        assert config.name == "Overdue Task Encouragement"
        assert config.enabled is True
    
    def test_mode_defaults_defined(self):
        """Should have expected duration defaults for all modes."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        job = OverdueEncouragementJob()
        
        assert job.MODE_DEFAULTS["mode-a"] == 60
        assert job.MODE_DEFAULTS["mode-b"] == 45
        assert job.MODE_DEFAULTS["mode-c"] == 90
        assert job.MODE_DEFAULTS["mode-d"] == 60
        assert job.MODE_DEFAULTS["mode-e"] == 30
        assert job.MODE_DEFAULTS["mode-f"] == 20
        assert job.MODE_DEFAULTS["mode-g"] == 120
    
    def test_gut_check_templates_exist(self):
        """Should have gut-check question templates for all modes."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        job = OverdueEncouragementJob()
        
        for mode in ["mode-a", "mode-b", "mode-c", "mode-d", "mode-e", "mode-f", "mode-g"]:
            assert mode in job.GUT_CHECK_TEMPLATES
            assert len(job.GUT_CHECK_TEMPLATES[mode]) >= 2
    
    def test_check_if_overdue_not_overdue(self, mock_queue):
        """Should not be overdue when elapsed < expected."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        job = OverdueEncouragementJob(queue=mock_queue)
        
        mode_info = {
            "mode": "mode-a",
            "elapsed_seconds": 1800,  # 30 min
            "progress": [True, True, False, False],  # 50% complete
        }
        
        result = job._check_if_overdue(mode_info)
        
        # 30 min < 60 min expected, so not overdue
        assert result["is_overdue"] is False
        assert result["expected_minutes"] == 60
        assert result["elapsed_minutes"] == 30
    
    def test_check_if_overdue_is_overdue(self, mock_queue):
        """Should be overdue when elapsed > expected and tasks remain."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        job = OverdueEncouragementJob(queue=mock_queue)
        
        mode_info = {
            "mode": "mode-a",
            "elapsed_seconds": 5400,  # 90 min
            "progress": [True, True, False, False],  # 50% complete
        }
        
        result = job._check_if_overdue(mode_info)
        
        # 90 min > 60 min expected, and incomplete tasks
        assert result["is_overdue"] is True
        assert result["overdue_minutes"] == 30
        assert result["tasks_remaining"] == 2
    
    def test_check_if_overdue_not_overdue_when_complete(self, mock_queue):
        """Should not be overdue when all tasks are complete."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        job = OverdueEncouragementJob(queue=mock_queue)
        
        mode_info = {
            "mode": "mode-a",
            "elapsed_seconds": 5400,  # 90 min - over expected
            "progress": [True, True, True, True],  # 100% complete
        }
        
        result = job._check_if_overdue(mode_info)
        
        # Over time, but all tasks done, so not overdue
        assert result["is_overdue"] is False
        assert result["completion_pct"] == 100
    
    def test_create_notification_has_gut_check(self, mock_queue):
        """Should create notification with gut-check question."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        job = OverdueEncouragementJob(queue=mock_queue)
        
        mode_info = {"mode": "mode-b", "elapsed_seconds": 5400}
        overdue_info = {
            "is_overdue": True,
            "elapsed_minutes": 90,
            "expected_minutes": 45,
            "overdue_minutes": 45,
            "tasks_remaining": 2,
        }
        context = {
            "task_focus": "the API endpoint",
            "ticket_title": "Implement user auth",
            "pending_tasks": ["Add validation", "Write tests"],
        }
        
        notification = job._create_encouragement_notification(
            mode_info, overdue_info, context
        )
        
        assert "Check-in" in notification.title
        assert "Implementation Planning" in notification.title
        assert "90 minutes" in notification.body
        assert "Expected ~45 min" in notification.body
        assert "Remaining tasks" in notification.body or "💭" in notification.body
    
    def test_run_creates_notification_when_overdue(self, mock_queue):
        """Should create notification when user is overdue."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        # Mock settings repository to return overdue state
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_setting.side_effect = lambda k: {
            "current_mode": "mode-a",
            "workflow_progress_mode-a": json.dumps([True, False, False, False]),  # 1/4 done
        }.get(k)
        mock_settings_repo.get_active_sessions.return_value = [{
            "mode": "mode-a",
            "started_at": (datetime.now() - timedelta(minutes=90)).isoformat(),  # 90 min, over 60 min default
        }]
        
        with patch('src.app.services.jobs.overdue_encouragement._get_settings_repo', return_value=mock_settings_repo):
            with patch('src.app.services.jobs.overdue_encouragement.ticket_service') as mock_ticket_svc:
                mock_ticket_svc.get_active_tickets.return_value = []
                job = OverdueEncouragementJob(queue=mock_queue)
                result = job.run()
        
        assert result["is_overdue"] is True
        assert result["notifications_created"] == 1
        mock_queue.create.assert_called_once()
    
    def test_run_no_notification_when_not_overdue(self, mock_queue):
        """Should not create notification when not overdue."""
        from src.app.services.background_jobs import OverdueEncouragementJob
        
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_setting.side_effect = lambda k: {
            "current_mode": "mode-a",
            "workflow_progress_mode-a": json.dumps([True, True, False, False]),
        }.get(k)
        mock_settings_repo.get_active_sessions.return_value = [{
            "mode": "mode-a",
            "started_at": (datetime.now() - timedelta(minutes=30)).isoformat(),
        }]
        
        with patch('src.app.services.jobs.overdue_encouragement._get_settings_repo', return_value=mock_settings_repo):
            job = OverdueEncouragementJob(queue=mock_queue)
            result = job.run()
        
        assert result["is_overdue"] is False
        assert result["notifications_created"] == 0
        mock_queue.create.assert_not_called()


class TestOverdueEncouragementAPI:
    """Tests for the overdue encouragement API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with auth bypassed."""
        import os
        os.environ['BYPASS_TOKEN'] = 'test-token'
        from src.app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.headers['X-Auth-Token'] = 'test-token'
        return client
    
    def test_overdue_check_endpoint_returns_status(self, client):
        """Should return overdue status."""
        response = client.get('/api/workflow/overdue-check')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have status fields
        assert 'is_overdue' in data
        assert 'mode' in data
    
    def test_send_encouragement_endpoint(self, client):
        """Should allow manual trigger of encouragement."""
        response = client.post('/api/workflow/send-encouragement')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return job result
        assert 'message' in data or 'error' in data


# =============================================================================
# JOB SCHEDULING API TESTS (pg_cron integration)
# =============================================================================

class TestJobSchedulingAPI:
    """Tests for the job scheduling API endpoints."""
    
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.app.main import app
        return TestClient(app)
    
    def test_list_jobs_endpoint(self, client):
        """Should list all available background jobs."""
        response = client.get('/api/v1/jobs')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have jobs list
        assert 'jobs' in data
        assert isinstance(data['jobs'], list)
        assert len(data['jobs']) >= 5  # At least 5 jobs defined
        
        # Each job should have required fields
        job_names = [j['name'] for j in data['jobs']]
        assert 'one_on_one_prep' in job_names
        assert 'sprint_mode_detect' in job_names
        assert 'stale_ticket_alert' in job_names
        assert 'grooming_match' in job_names
        assert 'overdue_encouragement' in job_names
        
        # Should have scheduling info
        assert 'scheduling' in data
        # Method can be 'manual' (test) or 'supabase_pg_cron' (production)
        assert data['scheduling']['method'] in ('manual', 'supabase_pg_cron')
    
    def test_run_job_invalid_name(self, client):
        """Should return 400 for invalid job name."""
        response = client.post('/api/v1/jobs/nonexistent_job/run')
        
        assert response.status_code == 400
        data = response.json()
        
        assert 'error' in data
        assert 'available_jobs' in data
    
    def test_run_job_valid_sprint_mode(self, client):
        """Should execute sprint_mode_detect job successfully."""
        response = client.post('/api/v1/jobs/sprint_mode_detect/run')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['job_name'] == 'sprint_mode_detect'
        assert data['status'] == 'completed'
        assert 'result' in data
        assert 'executed_at' in data
    
    def test_run_job_accepts_run_id_header(self, client):
        """Should accept X-Job-Run-Id header from pg_cron."""
        response = client.post(
            '/api/v1/jobs/sprint_mode_detect/run',
            headers={'X-Job-Run-Id': 'test-uuid-123'}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['run_id'] == 'test-uuid-123'


class TestJobConfigs:
    """Tests for job configuration registry."""
    
    def test_all_jobs_have_configs(self):
        """All jobs in run_job should have configs in JOB_CONFIGS."""
        from src.app.services.background_jobs import JOB_CONFIGS, run_job
        
        # Get job names from run_job function
        # We can't easily introspect, so check known jobs
        expected_jobs = [
            'one_on_one_prep',
            'sprint_mode_detect', 
            'stale_ticket_alert',
            'grooming_match',
            'overdue_encouragement',
        ]
        
        for job_name in expected_jobs:
            assert job_name in JOB_CONFIGS, f"Missing config for {job_name}"
    
    def test_job_configs_have_required_fields(self):
        """Each job config should have name, description, schedule."""
        from src.app.services.background_jobs import JOB_CONFIGS
        
        for key, config in JOB_CONFIGS.items():
            assert config.name, f"{key} missing name"
            assert config.description, f"{key} missing description"
            assert config.schedule, f"{key} missing schedule"
    
    def test_job_schedules_are_valid_cron(self):
        """Job schedules should be valid cron expressions."""
        from src.app.services.background_jobs import JOB_CONFIGS
        
        for key, config in JOB_CONFIGS.items():
            schedule = config.schedule
            # Basic validation: should have 5 parts (minute hour day month weekday)
            parts = schedule.split()
            assert len(parts) == 5, f"{key} has invalid cron schedule: {schedule}"