# src/app/domains/tickets/services/workflow_service.py
"""
Workflow Service

Business logic for ticket workflow and status transitions.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..constants import TICKET_STATUSES

logger = logging.getLogger(__name__)


# Valid status transitions
STATUS_TRANSITIONS = {
    "backlog": ["todo", "cancelled"],
    "todo": ["in_progress", "backlog", "cancelled"],
    "in_progress": ["in_review", "blocked", "todo", "cancelled"],
    "in_review": ["done", "in_progress", "cancelled"],
    "blocked": ["in_progress", "todo", "cancelled"],
    "done": ["in_progress"],  # Allow reopening
    "cancelled": ["backlog", "todo"],  # Allow restoration
}


class WorkflowService:
    """Service for managing ticket workflow and transitions."""
    
    def can_transition(self, from_status: str, to_status: str) -> bool:
        """
        Check if a status transition is valid.
        
        Args:
            from_status: Current status
            to_status: Target status
            
        Returns:
            True if transition is allowed
        """
        if from_status not in STATUS_TRANSITIONS:
            return False
        return to_status in STATUS_TRANSITIONS[from_status]
    
    def get_available_transitions(self, current_status: str) -> List[str]:
        """
        Get available status transitions from current status.
        
        Args:
            current_status: Current ticket status
            
        Returns:
            List of valid target statuses
        """
        return STATUS_TRANSITIONS.get(current_status, [])
    
    def calculate_cycle_time(
        self, 
        ticket: Dict[str, Any]
    ) -> Optional[int]:
        """
        Calculate cycle time in days (in_progress to done).
        
        Args:
            ticket: Ticket data dict
            
        Returns:
            Days or None if not applicable
        """
        started = ticket.get("started_at")
        completed = ticket.get("completed_at")
        
        if not started or not completed:
            return None
        
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            return (end_dt - start_dt).days
        except Exception:
            return None
    
    def calculate_lead_time(
        self, 
        ticket: Dict[str, Any]
    ) -> Optional[int]:
        """
        Calculate lead time in days (created to done).
        
        Args:
            ticket: Ticket data dict
            
        Returns:
            Days or None if not applicable
        """
        created = ticket.get("created_at")
        completed = ticket.get("completed_at")
        
        if not created or not completed:
            return None
        
        try:
            create_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            return (end_dt - create_dt).days
        except Exception:
            return None
    
    def get_workflow_metrics(
        self, 
        tickets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate workflow metrics for a set of tickets.
        
        Args:
            tickets: List of ticket dicts
            
        Returns:
            Metrics dict
        """
        completed = [t for t in tickets if t.get("status") == "done"]
        
        cycle_times = [self.calculate_cycle_time(t) for t in completed]
        cycle_times = [ct for ct in cycle_times if ct is not None]
        
        lead_times = [self.calculate_lead_time(t) for t in completed]
        lead_times = [lt for lt in lead_times if lt is not None]
        
        return {
            "total_tickets": len(tickets),
            "completed_tickets": len(completed),
            "avg_cycle_time": round(sum(cycle_times) / len(cycle_times), 1) if cycle_times else None,
            "avg_lead_time": round(sum(lead_times) / len(lead_times), 1) if lead_times else None,
            "throughput": len(completed),
            "wip": len([t for t in tickets if t.get("status") == "in_progress"]),
            "blocked": len([t for t in tickets if t.get("status") == "blocked"]),
        }


def get_workflow_service() -> WorkflowService:
    """Get the workflow service instance."""
    return WorkflowService()
