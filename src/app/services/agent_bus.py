"""
Multi-agent system - Agent Bus service for inter-agent communication.

This service provides a message queue for agents to communicate with each other,
similar to a pub/sub system but with directed messages and persistence.

Architecture:
- Messages are stored via AgentMessagesRepository for persistence
- Agents poll their message queue periodically
- Messages have priority, TTL, and retry logic
- Supports both direct (agent-to-agent) and broadcast messages
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..repositories import (
    AgentMessage,
    AgentMessagesRepository,
    MessagePriority,
    MessageType,
    get_agent_messages_repository,
)

logger = logging.getLogger(__name__)


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
    
    def __init__(self, repository: Optional[AgentMessagesRepository] = None):
        """Initialize agent bus with repository."""
        self._repo = repository or get_agent_messages_repository()
        logger.info("AgentBus initialized with repository")
    
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
        message_id = self._repo.insert(msg)
        
        target = msg.target_agent or "broadcast"
        logger.info(
            f"Message sent: {msg.source_agent} → {target} "
            f"({msg.message_type.value}, priority={msg.priority.value})"
        )
        return message_id
    
    def receive(self, agent_name: str, limit: int = 10) -> List[AgentMessage]:
        """Get pending messages for an agent.
        
        Args:
            agent_name: Name of agent receiving messages
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of AgentMessage objects
        """
        messages = self._repo.get_pending_for_agent(agent_name, limit)
        logger.debug(f"Agent {agent_name} received {len(messages)} messages")
        return messages
    
    def mark_processing(self, message_id: str):
        """Mark a message as being processed.
        
        Args:
            message_id: ID of message
        """
        self._repo.update_status(message_id, "processing")
        logger.debug(f"Message {message_id} marked as processing")
    
    def mark_completed(self, message_id: str, result: Optional[Dict] = None):
        """Mark a message as completed.
        
        Args:
            message_id: ID of message
            result: Optional result data to store
        """
        self._repo.update_status(
            message_id, 
            "completed", 
            processed_at=datetime.now()
        )
        logger.info(f"Message {message_id} completed")
    
    def mark_failed(self, message_id: str, error: str):
        """Mark a message as failed (with retry logic).
        
        Args:
            message_id: ID of message
            error: Error message
        """
        # Get current message state
        msg = self._repo.get_by_id(message_id)
        
        if not msg:
            logger.warning(f"Message {message_id} not found")
            return
        
        if msg.retry_count < msg.max_retries:
            # Retry: reset to pending
            self._repo.update_status(
                message_id,
                "pending",
                error_message=error,
                retry_count=msg.retry_count + 1,
            )
            logger.warning(
                f"Message retry: {message_id} "
                f"(attempt {msg.retry_count + 1}/{msg.max_retries})"
            )
        else:
            # Max retries exceeded
            self._repo.update_status(
                message_id,
                "failed",
                error_message=error,
            )
            logger.error(
                f"Message failed after {msg.max_retries} retries: "
                f"{message_id} - {error}"
            )
    
    def archive_old_messages(self, days: int = 7):
        """Archive/delete messages older than specified days.
        
        Args:
            days: Age in days to consider "old"
        """
        archived_count = self._repo.archive_old(days)
        logger.info(f"Archived {archived_count} messages older than {days} days")
    
    def get_message_stats(self) -> Dict[str, Any]:
        """Get statistics about messages in the queue.
        
        Returns:
            Dictionary with message statistics
        """
        stats = {}
        
        # Count by status
        for status in ["pending", "processing", "completed", "failed", "archived"]:
            stats[f"{status}_count"] = self._repo.get_count_by_status(status)
        
        # Note: Average processing time would require additional repository method
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
