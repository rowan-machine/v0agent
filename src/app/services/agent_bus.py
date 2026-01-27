"""
Multi-agent system - Agent Bus service for inter-agent communication.

This service provides a message queue for agents to communicate with each other,
similar to a pub/sub system but with directed messages and persistence.

Architecture:
- Messages are stored in Supabase for persistence
- Agents poll their message queue periodically
- Messages have priority, TTL, and retry logic
- Supports both direct (agent-to-agent) and broadcast messages
"""

import os
import uuid
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Supabase client - lazy initialization
_supabase_client = None

def get_supabase():
    """Get Supabase client instance."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        _supabase_client = create_client(url, key)
    return _supabase_client


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
    """Message passed between agents."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str = ""        # Who sent this
    target_agent: Optional[str] = None  # None = broadcast
    message_type: MessageType = MessageType.QUERY
    content: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    status: str = "pending"       # pending, processing, completed, failed, archived
    retry_count: int = 0
    max_retries: int = 3
    ttl_seconds: int = 3600      # 1 hour default
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
            content=json.loads(data["content"]),
            priority=MessagePriority(data["priority"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            processed_at=datetime.fromisoformat(data["processed_at"]) if data["processed_at"] else None,
            status=data["status"],
            retry_count=data["retry_count"],
            max_retries=data["max_retries"],
            ttl_seconds=data["ttl_seconds"],
            error_message=data["error_message"],
        )


class AgentBus:
    """Central message bus for agent communication.
    
    Usage:
        bus = AgentBus()
        
        # Send a query from one agent to another
        msg = AgentMessage(
            source_agent="agent_1",
            target_agent="agent_2",
            message_type=MessageType.QUERY,
            content={"question": "What's the status?"}
        )
        bus.send(msg)
        
        # Receive messages as agent_2
        messages = bus.receive("agent_2")
        for msg in messages:
            result = process_message(msg)
            bus.mark_completed(msg.id, result)
    """
    
    def __init__(self):
        """Initialize agent bus with Supabase."""
        self._supabase = None
        logger.info("AgentBus initialized with Supabase")
    
    @property
    def supabase(self):
        """Lazy initialization of Supabase client."""
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase
    
    def _initialize_tables(self):
        """Table creation is handled by Supabase migrations."""
        # No-op: Tables are created via Supabase migrations
        pass
    
    def send(self, msg: AgentMessage) -> str:
        """Send a message from one agent to another (or broadcast).
        
        Args:
            msg: AgentMessage to send
            
        Returns:
            Message ID
        """
        if msg.created_at is None:
            msg.created_at = datetime.now()
        
        data = msg.to_dict()
        self.supabase.table("agent_messages").insert(data).execute()
        
        target = msg.target_agent or "broadcast"
        logger.info(
            f"Message sent: {msg.source_agent} → {target} "
            f"({msg.message_type.value}, priority={msg.priority.value})"
        )
        return msg.id
    
    def receive(self, agent_name: str, limit: int = 10) -> List[AgentMessage]:
        """Get pending messages for an agent.
        
        Args:
            agent_name: Name of agent receiving messages
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of AgentMessage objects
        """
        # Get messages targeted to this agent or broadcasts (target_agent is null)
        result = self.supabase.table("agent_messages")\
            .select("*")\
            .eq("status", "pending")\
            .or_(f"target_agent.eq.{agent_name},target_agent.is.null")\
            .order("priority", desc=True)\
            .order("created_at", desc=False)\
            .limit(limit)\
            .execute()
        
        messages = [AgentMessage.from_dict(row) for row in (result.data or [])]
        logger.debug(f"Agent {agent_name} received {len(messages)} messages")
        return messages
    
    def mark_processing(self, message_id: str):
        """Mark a message as being processed.
        
        Args:
            message_id: ID of message
        """
        self.supabase.table("agent_messages")\
            .update({"status": "processing"})\
            .eq("id", message_id)\
            .execute()
        
        logger.debug(f"Message {message_id} marked as processing")
    
    def mark_completed(self, message_id: str, result: Optional[Dict] = None):
        """Mark a message as completed.
        
        Args:
            message_id: ID of message
            result: Optional result data to store
        """
        self.supabase.table("agent_messages")\
            .update({
                "status": "completed",
                "processed_at": datetime.now().isoformat()
            })\
            .eq("id", message_id)\
            .execute()
        
        logger.info(f"Message {message_id} completed")
    
    def mark_failed(self, message_id: str, error: str):
        """Mark a message as failed (with retry logic).
        
        Args:
            message_id: ID of message
            error: Error message
        """
        # Get current message state
        result = self.supabase.table("agent_messages")\
            .select("*")\
            .eq("id", message_id)\
            .execute()
        
        if not result.data:
            logger.warning(f"Message {message_id} not found")
            return
        
        msg = result.data[0]
        
        if msg["retry_count"] < msg["max_retries"]:
            # Retry: reset to pending
            self.supabase.table("agent_messages")\
                .update({
                    "status": "pending",
                    "retry_count": msg["retry_count"] + 1,
                    "error_message": error
                })\
                .eq("id", message_id)\
                .execute()
            logger.warning(
                f"Message retry: {message_id} "
                f"(attempt {msg['retry_count'] + 1}/{msg['max_retries']})"
            )
        else:
            # Max retries exceeded
            self.supabase.table("agent_messages")\
                .update({
                    "status": "failed",
                    "error_message": error
                })\
                .eq("id", message_id)\
                .execute()
            logger.error(
                f"Message failed after {msg['max_retries']} retries: "
                f"{message_id} - {error}"
            )
    
    def archive_old_messages(self, days: int = 7):
        """Archive/delete messages older than specified days.
        
        Args:
            days: Age in days to consider "old"
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        self.supabase.table("agent_messages")\
            .update({"status": "archived"})\
            .in_("status", ["completed", "failed"])\
            .lt("created_at", cutoff)\
            .execute()
        
        logger.info(f"Archived messages older than {days} days")
    
    def get_message_stats(self) -> Dict[str, Any]:
        """Get statistics about messages in the queue.
        
        Returns:
            Dictionary with message statistics
        """
        stats = {}
        
        # Count by status
        for status in ["pending", "processing", "completed", "failed", "archived"]:
            result = self.supabase.table("agent_messages")\
                .select("id", count="exact")\
                .eq("status", status)\
                .execute()
            stats[f"{status}_count"] = result.count or 0
        
        # Note: Supabase doesn't have julianday, average is computed differently
        # For now, just return basic counts
        stats["avg_processing_seconds"] = None
        
        return stats


# Global bus instance
_bus: Optional[AgentBus] = None


def get_agent_bus() -> AgentBus:
    """Get global agent bus instance (singleton).
    
    Returns:
        AgentBus instance
    """
    global _bus
    if _bus is None:
        _bus = AgentBus()
    return _bus


def initialize_agent_bus() -> AgentBus:
    """Initialize agent bus.
    
    Returns:
        AgentBus instance
    """
    global _bus
    _bus = AgentBus()
    return _bus
