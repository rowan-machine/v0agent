# src/app/repositories/agent_messages_repository.py
"""
Agent Messages Repository - Data Access for Agent-to-Agent Communication

Handles all agent message persistence:
- Message queue operations (send, receive, process)
- Status management (pending, processing, completed, failed, archived)
- Retry logic for failed messages
- Archival of old messages
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageType(Enum):
    """Types of messages agents can send."""
    QUERY = "query"              # Request information
    TASK = "task"                # Assign work
    RESULT = "result"            # Return results
    NOTIFICATION = "notification"  # Broadcast info
    STATUS = "status"            # Status update
    ERROR = "error"              # Error notification


@dataclass
class AgentMessage:
    """Agent message entity."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str = ""
    target_agent: Optional[str] = None  # None = broadcast
    message_type: MessageType = MessageType.QUERY
    content: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    status: str = "pending"  # pending, processing, completed, failed, archived
    retry_count: int = 0
    max_retries: int = 3
    ttl_seconds: int = 3600  # 1 hour default
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "message_type": self.message_type.value,
            "content": json.dumps(self.content),
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "ttl_seconds": self.ttl_seconds,
            "error_message": self.error_message,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        """Create from database row."""
        return cls(
            id=data["id"],
            source_agent=data["source_agent"],
            target_agent=data["target_agent"],
            message_type=MessageType(data["message_type"]),
            content=json.loads(data["content"]) if isinstance(data["content"], str) else data["content"],
            priority=MessagePriority(data["priority"]),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
            processed_at=datetime.fromisoformat(data["processed_at"]) if data["processed_at"] and isinstance(data["processed_at"], str) else data["processed_at"],
            status=data["status"],
            retry_count=data["retry_count"],
            max_retries=data["max_retries"],
            ttl_seconds=data["ttl_seconds"],
            error_message=data["error_message"],
        )


class AgentMessagesRepository(ABC):
    """
    Abstract interface (Port) for agent message data access.
    
    Defines all agent message operations without implementation details.
    """
    
    @abstractmethod
    def insert(self, message: AgentMessage) -> str:
        """Insert a new message into the queue.
        
        Args:
            message: AgentMessage to insert
            
        Returns:
            Message ID
        """
        pass
    
    @abstractmethod
    def get_pending_for_agent(
        self, 
        agent_name: str, 
        limit: int = 10
    ) -> List[AgentMessage]:
        """Get pending messages for an agent (direct or broadcast).
        
        Args:
            agent_name: Name of the receiving agent
            limit: Maximum messages to retrieve
            
        Returns:
            List of AgentMessage objects
        """
        pass
    
    @abstractmethod
    def get_by_id(self, message_id: str) -> Optional[AgentMessage]:
        """Get a specific message by ID.
        
        Args:
            message_id: Message ID
            
        Returns:
            AgentMessage or None if not found
        """
        pass
    
    @abstractmethod
    def update_status(
        self, 
        message_id: str, 
        status: str,
        processed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        retry_count: Optional[int] = None,
    ) -> bool:
        """Update message status and related fields.
        
        Args:
            message_id: Message ID
            status: New status value
            processed_at: When processed (for completed)
            error_message: Error details (for failed/retry)
            retry_count: Updated retry count
            
        Returns:
            True if update succeeded
        """
        pass
    
    @abstractmethod
    def archive_old(self, days: int = 7) -> int:
        """Archive messages older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of messages archived
        """
        pass
    
    @abstractmethod
    def get_count_by_status(self, status: str) -> int:
        """Get count of messages with a specific status.
        
        Args:
            status: Status to count
            
        Returns:
            Count of matching messages
        """
        pass


class SupabaseAgentMessagesRepository(AgentMessagesRepository):
    """
    Supabase implementation (Adapter) for agent message data access.
    """
    
    def __init__(self):
        from ..infrastructure.supabase_client import get_supabase_client
        self._supabase = get_supabase_client()
    
    def insert(self, message: AgentMessage) -> str:
        """Insert a new message into the queue."""
        try:
            if message.created_at is None:
                message.created_at = datetime.now()
            
            data = message.to_dict()
            self._supabase.table("agent_messages").insert(data).execute()
            return message.id
        except Exception as e:
            raise RuntimeError(f"Failed to insert agent message: {e}")
    
    def get_pending_for_agent(
        self, 
        agent_name: str, 
        limit: int = 10
    ) -> List[AgentMessage]:
        """Get pending messages for an agent (direct or broadcast)."""
        try:
            result = self._supabase.table("agent_messages")\
                .select("*")\
                .eq("status", "pending")\
                .or_(f"target_agent.eq.{agent_name},target_agent.is.null")\
                .order("priority", desc=True)\
                .order("created_at", desc=False)\
                .limit(limit)\
                .execute()
            
            return [AgentMessage.from_dict(row) for row in (result.data or [])]
        except Exception:
            return []
    
    def get_by_id(self, message_id: str) -> Optional[AgentMessage]:
        """Get a specific message by ID."""
        try:
            result = self._supabase.table("agent_messages")\
                .select("*")\
                .eq("id", message_id)\
                .execute()
            
            if result.data:
                return AgentMessage.from_dict(result.data[0])
            return None
        except Exception:
            return None
    
    def update_status(
        self, 
        message_id: str, 
        status: str,
        processed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        retry_count: Optional[int] = None,
    ) -> bool:
        """Update message status and related fields."""
        try:
            update_data = {"status": status}
            
            if processed_at:
                update_data["processed_at"] = processed_at.isoformat()
            if error_message is not None:
                update_data["error_message"] = error_message
            if retry_count is not None:
                update_data["retry_count"] = retry_count
            
            self._supabase.table("agent_messages")\
                .update(update_data)\
                .eq("id", message_id)\
                .execute()
            return True
        except Exception:
            return False
    
    def archive_old(self, days: int = 7) -> int:
        """Archive messages older than specified days."""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            result = self._supabase.table("agent_messages")\
                .update({"status": "archived"})\
                .in_("status", ["completed", "failed"])\
                .lt("created_at", cutoff)\
                .execute()
            
            # Return count of affected rows (approximation)
            return len(result.data) if result.data else 0
        except Exception:
            return 0
    
    def get_count_by_status(self, status: str) -> int:
        """Get count of messages with a specific status."""
        try:
            result = self._supabase.table("agent_messages")\
                .select("id", count="exact")\
                .eq("status", status)\
                .execute()
            return result.count or 0
        except Exception:
            return 0


# Factory function
def get_agent_messages_repository() -> AgentMessagesRepository:
    """Get agent messages repository instance.
    
    Returns:
        AgentMessagesRepository implementation
    """
    return SupabaseAgentMessagesRepository()
