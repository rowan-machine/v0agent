# src/app/services/jobs/overdue_encouragement.py
"""
F4f: Overdue Task Encouragement Job

Send encouraging gut-check messages when overdue on workflow tasks.

Reviews:
- Workflow checklist progress vs expected time
- Ticket implementation plans and task decomposition
- Generates contextual time-based questions

Schedule: Weekdays at 2 PM and 5 PM
"""

import json
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ...repositories import get_settings_repository
from .. import ticket_service
from ..notification_queue import (
    NotificationQueue,
    NotificationType,
    NotificationPriority,
    Notification,
)

logger = logging.getLogger(__name__)


def _get_settings_repo():
    """Get settings repository (lazy load)."""
    try:
        return get_settings_repository()
    except Exception:
        return None


class OverdueEncouragementJob:
    """
    Send encouraging gut-check messages when overdue on workflow tasks.
    
    Reviews:
    - Workflow checklist progress vs expected time
    - Ticket implementation plans and task decomposition
    - Generates contextual time-based questions
    
    Schedule: Weekdays at 2 PM and 5 PM
    """
    
    # Expected durations per mode (in minutes) - same as F4e
    MODE_DEFAULTS = {
        "mode-a": 60,   # Context Distillation
        "mode-b": 45,   # Implementation Planning
        "mode-c": 90,   # Assisted Draft Intake
        "mode-d": 60,   # Deep Review
        "mode-e": 30,   # Promotion Readiness
        "mode-f": 20,   # Controlled Sync
        "mode-g": 120,  # Execution
    }
    
    MODE_NAMES = {
        "mode-a": "Context Distillation",
        "mode-b": "Implementation Planning",
        "mode-c": "Assisted Draft Intake",
        "mode-d": "Deep Review & Validation",
        "mode-e": "Promotion Readiness",
        "mode-f": "Controlled Sync",
        "mode-g": "Execution",
    }
    
    # Gut-check question templates per mode
    GUT_CHECK_TEMPLATES = {
        "mode-a": [
            "How's the context gathering going? Found all the files you need?",
            "Are you feeling clear about the scope of what you're working on?",
            "Any dependencies or blockers surfacing that need attention?",
        ],
        "mode-b": [
            "How are you feeling about the implementation approach?",
            "Is the plan coming together, or are there unknowns blocking you?",
            "Any technical decisions you're wrestling with?",
        ],
        "mode-c": [
            "How's the drafting going? Making progress on the structure?",
            "Are you getting good output from the AI assistance?",
            "Any parts feeling stuck or unclear?",
        ],
        "mode-d": [
            "How's the review going? Finding issues or looking clean?",
            "Are you comfortable with the test coverage?",
            "Any edge cases you're worried about?",
        ],
        "mode-e": [
            "Feeling ready for promotion? Anything missing from the checklist?",
            "Is the documentation complete?",
            "Any last-minute concerns before delivery?",
        ],
        "mode-f": [
            "Sync going smoothly? Any merge conflicts or issues?",
            "PR ready for review?",
            "Any dependencies to coordinate?",
        ],
        "mode-g": [
            "How are you feeling about the {task_focus}?",
            "Making progress on the implementation?",
            "Any blockers or questions coming up?",
        ],
    }
    
    def __init__(self, queue: Optional[NotificationQueue] = None):
        self.queue = queue or NotificationQueue()
    
    def run(self) -> Dict[str, Any]:
        """Run the overdue encouragement check."""
        logger.info("Running OverdueEncouragementJob")
        
        result = {
            "notifications_created": 0,
            "mode_checked": None,
            "is_overdue": False,
            "message": "",
        }
        
        try:
            # Get current mode and tracking info
            mode_info = self._get_current_mode_info()
            result["mode_checked"] = mode_info.get("mode")
            
            if not mode_info.get("mode"):
                result["message"] = "No active mode found"
                return result
            
            # Check if overdue
            overdue_info = self._check_if_overdue(mode_info)
            result["is_overdue"] = overdue_info["is_overdue"]
            
            if not overdue_info["is_overdue"]:
                result["message"] = f"Not overdue in {mode_info['mode']}"
                return result
            
            # Get context for encouragement message
            context = self._get_task_context(mode_info)
            
            # Generate encouraging message
            notification = self._create_encouragement_notification(
                mode_info, overdue_info, context
            )
            
            notification_id = self.queue.create(notification)
            result["notifications_created"] = 1
            result["notification_id"] = notification_id
            result["message"] = f"Sent encouragement for {mode_info['mode']}"
            
        except Exception as e:
            logger.error(f"OverdueEncouragementJob error: {e}")
            result["error"] = str(e)
        
        return result
    
    def _get_current_mode_info(self) -> Dict[str, Any]:
        """Get current mode and tracking session info."""
        info = {
            "mode": None,
            "elapsed_seconds": 0,
            "started_at": None,
            "progress": [],
        }
        
        settings_repo = _get_settings_repo()
        if not settings_repo:
            return info
        
        # Get current mode from settings
        mode = settings_repo.get_setting("current_mode")
        if mode:
            info["mode"] = mode
        
        # Get active tracking session
        if info["mode"]:
            active_sessions = settings_repo.get_active_sessions()
            # Find active session for current mode
            mode_session = next(
                (s for s in active_sessions if s.get("mode") == info["mode"]),
                None
            )
            
            if mode_session:
                info["started_at"] = mode_session.get("started_at")
                # Calculate current elapsed time from started_at
                if mode_session.get("started_at"):
                    try:
                        started = datetime.fromisoformat(mode_session["started_at"])
                        info["elapsed_seconds"] = int((datetime.now() - started).total_seconds())
                    except:
                        info["elapsed_seconds"] = 0
            
            # Get workflow progress
            progress_value = settings_repo.get_setting(f"workflow_progress_{info['mode']}")
            if progress_value:
                try:
                    info["progress"] = json.loads(progress_value)
                except:
                    pass
        
        return info
    
    def _check_if_overdue(self, mode_info: Dict) -> Dict[str, Any]:
        """Check if current mode session is overdue."""
        mode = mode_info.get("mode", "mode-a")
        elapsed_seconds = mode_info.get("elapsed_seconds", 0)
        progress = mode_info.get("progress", [])
        
        expected_minutes = self.MODE_DEFAULTS.get(mode, 60)
        expected_seconds = expected_minutes * 60
        
        # Calculate completion percentage
        total_tasks = len(progress) if progress else 0
        completed_tasks = sum(1 for p in progress if p) if progress else 0
        completion_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Overdue conditions:
        # 1. Elapsed time > expected time
        # 2. AND at least some tasks remain incomplete
        is_overdue = (
            elapsed_seconds > expected_seconds and
            completion_pct < 100 and
            total_tasks > 0
        )
        
        # Calculate how much over
        overdue_seconds = max(0, elapsed_seconds - expected_seconds)
        overdue_minutes = int(overdue_seconds / 60)
        
        return {
            "is_overdue": is_overdue,
            "expected_minutes": expected_minutes,
            "elapsed_minutes": int(elapsed_seconds / 60),
            "overdue_minutes": overdue_minutes,
            "completion_pct": completion_pct,
            "tasks_remaining": total_tasks - completed_tasks,
        }
    
    def _get_task_context(self, mode_info: Dict) -> Dict[str, Any]:
        """Get context from tickets and implementation plans."""
        context = {
            "ticket_title": None,
            "task_focus": None,
            "implementation_hints": [],
            "pending_tasks": [],
        }
        
        # Get active tickets from Supabase
        all_tickets = ticket_service.get_active_tickets()
        
        # Sort: in_progress first, then todo
        def sort_priority(t):
            status = t.get("status", "")
            if status == "in_progress":
                return 0
            elif status == "todo":
                return 1
            return 2
        
        sorted_tickets = sorted(all_tickets, key=sort_priority)
        
        if sorted_tickets:
            ticket = sorted_tickets[0]
            context["ticket_title"] = ticket.get("title") or ""
            
            # Parse task decomposition for pending tasks
            task_decomp = ticket.get("task_decomposition")
            if task_decomp:
                try:
                    tasks = json.loads(task_decomp) if isinstance(task_decomp, str) else task_decomp
                    for task in tasks if isinstance(tasks, list) else []:
                        if isinstance(task, dict):
                            status = task.get("status", "pending")
                            if status not in ("done", "complete", "completed"):
                                title = task.get("title") or task.get("text") or str(task)
                                context["pending_tasks"].append(title[:50])
                        elif isinstance(task, str):
                            context["pending_tasks"].append(task[:50])
                except:
                    pass
            
            # Extract key topics from implementation plan
            impl_plan = ticket.get("implementation_plan")
            if impl_plan:
                plan = impl_plan
                # Find technical keywords
                keywords = re.findall(
                    r'\b(api|function|class|method|transform|logic|data|model|service|component|handler|endpoint)\b',
                    plan.lower()
                )
                if keywords:
                    # Use most common keyword as focus
                    from collections import Counter
                    focus = Counter(keywords).most_common(1)[0][0]
                    context["task_focus"] = f"the {focus}"
                
                # Extract hints (first sentences of paragraphs)
                paragraphs = plan.split('\n\n')[:3]
                for para in paragraphs:
                    first_sentence = para.split('.')[0].strip()[:80]
                    if first_sentence and len(first_sentence) > 10:
                        context["implementation_hints"].append(first_sentence)
        
        # Set default task focus if none found
        if not context["task_focus"]:
            if context["pending_tasks"]:
                context["task_focus"] = context["pending_tasks"][0]
            else:
                context["task_focus"] = "current work"
        
        return context
    
    def _create_encouragement_notification(
        self,
        mode_info: Dict,
        overdue_info: Dict,
        context: Dict,
    ) -> Notification:
        """Create the encouraging notification."""
        mode = mode_info.get("mode", "mode-a")
        mode_name = self.MODE_NAMES.get(mode, mode)
        
        # Pick a gut-check question
        templates = self.GUT_CHECK_TEMPLATES.get(mode, self.GUT_CHECK_TEMPLATES["mode-g"])
        question_template = random.choice(templates)
        
        # Format the question with context
        gut_check = question_template.format(
            task_focus=context.get("task_focus", "the current task")
        )
        
        # Build the message
        title = f"⏰ Check-in: {mode_name}"
        
        body_lines = [
            f"You've been in **{mode_name}** for {overdue_info['elapsed_minutes']} minutes.",
            f"(Expected ~{overdue_info['expected_minutes']} min)",
            "",
            f"💭 **{gut_check}**",
            "",
        ]
        
        # Add task context if available
        if context["pending_tasks"]:
            body_lines.append(f"**Remaining tasks:**")
            for task in context["pending_tasks"][:3]:
                body_lines.append(f"• {task}")
            body_lines.append("")
        
        # Add encouraging close
        encouragements = [
            "Take a moment to assess — you've got this! 💪",
            "No rush, just a friendly nudge. You're doing great!",
            "Sometimes stepping back helps. How can I help?",
            "Progress over perfection! Keep going! 🚀",
        ]
        body_lines.append(random.choice(encouragements))
        
        body = "\n".join(body_lines)
        
        return Notification(
            notification_type=NotificationType.COACH_RECOMMENDATION,
            title=title,
            body=body,
            data={
                "type": "overdue_encouragement",
                "mode": mode,
                "elapsed_minutes": overdue_info["elapsed_minutes"],
                "expected_minutes": overdue_info["expected_minutes"],
                "tasks_remaining": overdue_info["tasks_remaining"],
                "task_focus": context.get("task_focus"),
                "ticket_title": context.get("ticket_title"),
            },
            priority=NotificationPriority.NORMAL,
            expires_at=datetime.now() + timedelta(hours=4),
        )
