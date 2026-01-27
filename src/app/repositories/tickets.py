# src/app/repositories/tickets.py
"""
Ticket Repository - Ports and Adapters

Port: TicketRepository (abstract interface)
Adapters: SupabaseTicketRepository
"""

import json
import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import BaseRepository, QueryOptions

logger = logging.getLogger(__name__)


class TicketRepository(BaseRepository[Dict[str, Any]]):
    """
    Ticket Repository Port - defines the interface for ticket data access.
    
    Extends BaseRepository with ticket-specific operations.
    """
    
    @abstractmethod
    def get_active(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get tickets with active statuses (todo, in_progress, etc.)."""
        pass
    
    @abstractmethod
    def get_blocked(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get blocked tickets."""
        pass
    
    @abstractmethod
    def get_stale(self, days: int = 3, limit: int = 5) -> List[Dict[str, Any]]:
        """Get tickets that haven't been updated in X days."""
        pass
    
    @abstractmethod
    def get_by_status(self, statuses: List[str], limit: int = 50) -> List[Dict[str, Any]]:
        """Get tickets filtered by status."""
        pass
    
    @abstractmethod
    def get_sprint_tickets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get tickets in the current sprint."""
        pass
    
    @abstractmethod
    def get_next_ticket_number(self, prefix: str = "SIG") -> str:
        """Generate the next ticket ID (e.g., SIG-42)."""
        pass


# =============================================================================
# SUPABASE ADAPTER
# =============================================================================

class SupabaseTicketRepository(TicketRepository):
    """
    Supabase adapter for ticket repository.
    """
    
    # Status priority for sorting
    STATUS_PRIORITY = {
        "in_progress": 1,
        "blocked": 2,
        "in_review": 3,
        "todo": 4,
        "backlog": 5,
        "done": 6,
        "closed": 7,
        "archived": 8,
    }
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from ..infrastructure.supabase_client import get_supabase_client
            self._client = get_supabase_client()
        return self._client
    
    def _format_row(self, row: Dict) -> Dict[str, Any]:
        """Format Supabase row to standard ticket dict."""
        return {
            "id": row.get("id"),
            "ticket_id": row.get("ticket_id"),
            "title": row.get("title", ""),
            "description": row.get("description", ""),
            "status": row.get("status", "backlog"),
            "priority": row.get("priority"),
            "sprint_points": row.get("sprint_points", 0),
            "in_sprint": row.get("in_sprint", True),
            "ai_summary": row.get("ai_summary"),
            "implementation_plan": row.get("implementation_plan"),
            "task_decomposition": row.get("task_decomposition"),
            "test_plan": row.get("test_plan"),
            "tags": row.get("tags", ""),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
    
    def get_all(self, options: Optional[QueryOptions] = None) -> List[Dict[str, Any]]:
        """Get all tickets from Supabase."""
        if not self.client:
            logger.warning("Supabase not available")
            return []
        
        options = options or QueryOptions()
        
        try:
            query = self.client.table("tickets").select("*")
            query = query.order(options.order_by, desc=options.order_desc)
            
            if options.offset:
                query = query.range(options.offset, options.offset + options.limit - 1)
            else:
                query = query.limit(options.limit)
            
            result = query.execute()
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            return []
    
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single ticket by UUID or ticket_id."""
        if not self.client:
            return None
        
        try:
            # Try UUID first
            result = self.client.table("tickets").select("*").eq("id", entity_id).execute()
            if result.data:
                return self._format_row(result.data[0])
            
            # Try ticket_id (e.g., "SIG-1")
            result = self.client.table("tickets").select("*").eq("ticket_id", entity_id).execute()
            if result.data:
                return self._format_row(result.data[0])
            
            return None
        except Exception as e:
            logger.error(f"Failed to get ticket {entity_id}: {e}")
            return None
    
    def get_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get count of tickets."""
        if not self.client:
            return 0
        
        try:
            query = self.client.table("tickets").select("id", count="exact")
            if filters and "statuses" in filters:
                query = query.in_("status", filters["statuses"])
            result = query.execute()
            return result.count or 0
        except Exception as e:
            logger.error(f"Failed to get ticket count: {e}")
            return 0
    
    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new ticket."""
        if not self.client:
            return None
        
        try:
            # Generate ticket_id if not provided
            if "ticket_id" not in data:
                data["ticket_id"] = self.get_next_ticket_number()
            
            result = self.client.table("tickets").insert(data).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return None
    
    def update(self, entity_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing ticket."""
        if not self.client:
            return None
        
        try:
            data["updated_at"] = datetime.utcnow().isoformat()
            result = self.client.table("tickets").update(data).eq("id", entity_id).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to update ticket {entity_id}: {e}")
            return None
    
    def delete(self, entity_id: str) -> bool:
        """Delete a ticket."""
        if not self.client:
            return False
        
        try:
            self.client.table("tickets").delete().eq("id", entity_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete ticket {entity_id}: {e}")
            return False
    
    def get_active(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get tickets with active statuses."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("tickets").select("*").in_(
                "status", ["todo", "in_progress", "in_review", "blocked"]
            ).order("updated_at", desc=True).limit(limit).execute()
            
            tickets = [self._format_row(row) for row in result.data]
            tickets.sort(key=lambda t: self.STATUS_PRIORITY.get(t["status"], 5))
            return tickets
        except Exception as e:
            logger.error(f"Failed to get active tickets: {e}")
            return []
    
    def get_blocked(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get blocked tickets."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("tickets").select("*").eq(
                "status", "blocked"
            ).order("updated_at", desc=True).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get blocked tickets: {e}")
            return []
    
    def get_stale(self, days: int = 3, limit: int = 5) -> List[Dict[str, Any]]:
        """Get tickets that haven't been updated in X days."""
        if not self.client:
            return []
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        try:
            result = self.client.table("tickets").select("*").not_.in_(
                "status", ["done", "closed", "archived"]
            ).lt("updated_at", cutoff).order("updated_at", desc=False).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get stale tickets: {e}")
            return []
    
    def get_by_status(self, statuses: List[str], limit: int = 50) -> List[Dict[str, Any]]:
        """Get tickets filtered by status."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("tickets").select("*").in_(
                "status", statuses
            ).order("updated_at", desc=True).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get tickets by status: {e}")
            return []
    
    def get_sprint_tickets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get tickets in the current sprint."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("tickets").select("*").eq(
                "in_sprint", True
            ).not_.in_(
                "status", ["done", "closed", "archived"]
            ).order("updated_at", desc=True).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get sprint tickets: {e}")
            return []
    
    def get_next_ticket_number(self, prefix: str = "SIG") -> str:
        """Generate the next ticket ID."""
        if not self.client:
            return f"{prefix}-1"
        
        try:
            result = self.client.table("tickets").select("ticket_id").like(
                "ticket_id", f"{prefix}-%"
            ).order("created_at", desc=True).limit(1).execute()
            
            if result.data and result.data[0].get("ticket_id"):
                last_id = result.data[0]["ticket_id"]
                try:
                    num = int(last_id.split("-")[1]) + 1
                except:
                    num = 1
            else:
                num = 1
            
            return f"{prefix}-{num}"
        except Exception as e:
            logger.error(f"Failed to get next ticket number: {e}")
            return f"{prefix}-1"
