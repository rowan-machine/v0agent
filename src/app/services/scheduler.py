"""
Background Job Scheduler for SignalFlow

Uses APScheduler to run background jobs at their scheduled times.
This provides reliable in-app scheduling without depending on external cron.

Jobs are defined in background_jobs.py and scheduled based on their cron expressions.
"""

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None


def get_scheduler():
    """Get the global scheduler instance."""
    global _scheduler
    return _scheduler


def init_scheduler():
    """
    Initialize the APScheduler with all background jobs.
    
    Only runs in production (ENVIRONMENT=production) to avoid
    duplicate job execution during development.
    """
    global _scheduler
    
    # Only run scheduler in production
    environment = os.environ.get("ENVIRONMENT", "development")
    if environment != "production":
        logger.info(f"Scheduler disabled in {environment} environment")
        return None
    
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        from .background_jobs import (
            OneOnOnePrepJob,
            StaleTicketAlertJob,
            GroomingMatchJob,
            SprintModeDetectJob,
            OverdueEncouragementJob,
            JOB_CONFIGS,
        )
        
        _scheduler = BackgroundScheduler(
            job_defaults={
                'coalesce': True,  # Combine missed executions
                'max_instances': 1,  # One instance at a time
                'misfire_grace_time': 60 * 30,  # 30 min grace period
            }
        )
        
        # Job wrapper functions
        def run_one_on_one_prep():
            """Run 1:1 prep job if it should run today."""
            try:
                job = OneOnOnePrepJob()
                if job.should_run_today():
                    result = job.run()
                    logger.info(f"OneOnOnePrepJob completed: {result}")
            except Exception as e:
                logger.error(f"OneOnOnePrepJob failed: {e}")
        
        def run_stale_ticket_alert():
            """Run stale ticket alert job."""
            try:
                job = StaleTicketAlertJob()
                result = job.run()
                logger.info(f"StaleTicketAlertJob completed: alerts={result.get('alerts_created', 0)}")
            except Exception as e:
                logger.error(f"StaleTicketAlertJob failed: {e}")
        
        def run_grooming_match():
            """Run grooming-to-ticket match job."""
            try:
                job = GroomingMatchJob()
                result = job.run()
                if result.get("matches"):
                    logger.info(f"GroomingMatchJob completed: matches={len(result['matches'])}")
            except Exception as e:
                logger.error(f"GroomingMatchJob failed: {e}")
        
        def run_sprint_mode_detect():
            """Run sprint mode detection job."""
            try:
                job = SprintModeDetectJob()
                result = job.run()
                logger.info(f"SprintModeDetectJob completed: suggested={result.get('suggested_mode')}")
            except Exception as e:
                logger.error(f"SprintModeDetectJob failed: {e}")
        
        def run_overdue_encouragement():
            """Run overdue encouragement job."""
            try:
                job = OverdueEncouragementJob()
                result = job.run()
                created = result.get("notifications_created", 0)
                if created > 0:
                    logger.info(f"OverdueEncouragementJob completed: notifications={created}")
            except Exception as e:
                logger.error(f"OverdueEncouragementJob failed: {e}")
        
        # Schedule jobs based on their cron expressions
        # 1:1 Prep - Every Tuesday at 7 AM (but job checks biweekly internally)
        _scheduler.add_job(
            run_one_on_one_prep,
            CronTrigger.from_crontab("0 7 * * 2"),  # Every Tuesday 7 AM
            id="one_on_one_prep",
            name="1:1 Prep Digest",
            replace_existing=True,
        )
        
        # Stale Ticket Alert - Weekdays at 9 AM
        _scheduler.add_job(
            run_stale_ticket_alert,
            CronTrigger.from_crontab("0 9 * * 1-5"),  # Weekdays 9 AM
            id="stale_ticket_alert",
            name="Stale Ticket Alert",
            replace_existing=True,
        )
        
        # Grooming Match - Every hour
        _scheduler.add_job(
            run_grooming_match,
            CronTrigger.from_crontab("0 * * * *"),  # Every hour
            id="grooming_match",
            name="Grooming-to-Ticket Match",
            replace_existing=True,
        )
        
        # Sprint Mode Detect - Daily at 8 AM
        _scheduler.add_job(
            run_sprint_mode_detect,
            CronTrigger.from_crontab("0 8 * * *"),  # Daily 8 AM
            id="sprint_mode_detect",
            name="Sprint Mode Auto-Detect",
            replace_existing=True,
        )
        
        # Overdue Encouragement - Weekdays at 2 PM and 5 PM
        _scheduler.add_job(
            run_overdue_encouragement,
            CronTrigger.from_crontab("0 14 * * 1-5"),  # Weekdays 2 PM
            id="overdue_encouragement_2pm",
            name="Overdue Encouragement (2 PM)",
            replace_existing=True,
        )
        _scheduler.add_job(
            run_overdue_encouragement,
            CronTrigger.from_crontab("0 17 * * 1-5"),  # Weekdays 5 PM
            id="overdue_encouragement_5pm",
            name="Overdue Encouragement (5 PM)",
            replace_existing=True,
        )
        
        # Start the scheduler
        _scheduler.start()
        logger.info("✅ Background job scheduler started")
        
        # Log scheduled jobs
        for job in _scheduler.get_jobs():
            logger.info(f"  📅 {job.name}: next run at {job.next_run_time}")
        
        return _scheduler
        
    except ImportError:
        logger.warning("APScheduler not installed. Background jobs will not run automatically.")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")
        return None


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shutdown complete")
        _scheduler = None


def get_next_job_runs() -> list:
    """Get the next scheduled run times for all jobs."""
    if not _scheduler:
        return []
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    return jobs
