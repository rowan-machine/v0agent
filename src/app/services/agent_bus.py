"""
Multi-agent system - Agent Bus service for inter-agent communication.

This service provides a message queue for agents to communicate with each other,
similar to a pub/sub system but with directed messages and persistence.

Architecture:
- Messages are stored in SQLite for persistence
- Agents poll their message queue periodically
- Messages have priority, TTL, and retry logic
- Supports both direct (agent-to-agent) and broadcast messages
"""

import uuid
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


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
    
    def __init__(self, db_path: str = "agent.db"):
        """Initialize agent bus with database.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._initialize_tables()
        logger.info(f"AgentBus initialized with database: {db_path}")
    
    def _initialize_tables(self):
        """Create message queue table if not exists."""
        # Import here to avoid circular imports
        from src.app.db import connect
        
        with connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 2,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    ttl_seconds INTEGER DEFAULT 3600,
                    error_message TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_messages_status 
                ON agent_messages(status, priority DESC, created_at ASC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_messages_target 
                ON agent_messages(target_agent, status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_messages_created 
                ON agent_messages(created_at DESC)
            """)
            conn.commit()
    
    def send(self, msg: AgentMessage) -> str:
        """Send a message from one agent to another (or broadcast).
        
        Args:
            msg: AgentMessage to send
            
        Returns:
            Message ID
        """
        from src.app.db import connect
        
        if msg.created_at is None:
            msg.created_at = datetime.now()
        
        with connect(self.db_path) as conn:
            data = msg.to_dict()
            placeholders = ", ".join(["?"] * len(data))
            columns = ", ".join(data.keys())
            
            conn.execute(f"""
                INSERT INTO agent_messages ({columns})
                VALUES ({placeholders})
            """, tuple(data.values()))
            conn.commit()
        
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
        from src.app.db import connect
        
        with connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT * FROM agent_messages
                WHERE (target_agent = ? OR target_agent IS NULL)
                AND status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (agent_name, limit)).fetchall()
        
        messages = [AgentMessage.from_dict(dict(row)) for row in rows]
        logger.debug(f"Agent {agent_name} received {len(messages)} messages")
        return messages
    
    def mark_processing(self, message_id: str):
        """Mark a message as being processed.
        
        Args:
            message_id: ID of message
        """
        from src.app.db import connect
        
        with connect(self.db_path) as conn:
            conn.execute("""
                UPDATE agent_messages
                SET status = 'processing'
                WHERE id = ?
            """, (message_id,))
            conn.commit()
        
        logger.debug(f"Message {message_id} marked as processing")
    
    def mark_completed(self, message_id: str, result: Optional[Dict] = None):
        """Mark a message as completed.
        
        Args:
            message_id: ID of message
            result: Optional result data to store
        """
        from src.app.db import connect
        
        with connect(self.db_path) as conn:
            conn.execute("""
                UPDATE agent_messages
                SET status = 'completed', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (message_id,))
            conn.commit()
        
        logger.info(f"Message {message_id} completed")
    
    def mark_failed(self, message_id: str, error: str):
        """Mark a message as failed (with retry logic).
        
        Args:
            message_id: ID of message
            error: Error message
        """
        from src.app.db import connect
        
        with connect(self.db_path) as conn:
            msg = conn.execute(
                "SELECT * FROM agent_messages WHERE id = ?",
                (message_id,)
            ).fetchone()
            
            if msg is None:
                logger.warning(f"Message {message_id} not found")
                return
            
            if msg["retry_count"] < msg["max_retries"]:
                # Retry: reset to pending
                conn.execute("""
                    UPDATE agent_messages
                    SET status = 'pending', retry_count = retry_count + 1, 
                        error_message = ?
                    WHERE id = ?
                """, (error, message_id))
                logger.warning(
                    f"Message retry: {message_id} "
                    f"(attempt {msg['retry_count'] + 1}/{msg['max_retries']})"
                )
            else:
                # Max retries exceeded
                conn.execute("""
                    UPDATE agent_messages
                    SET status = 'failed', error_message = ?
                    WHERE id = ?
                """, (error, message_id))
                logger.error(
                    f"Message failed after {msg['max_retries']} retries: "
                    f"{message_id} - {error}"
                )
            
            conn.commit()
    
    def archive_old_messages(self, days: int = 7):
        """Archive/delete messages older than specified days.
        
        Args:
            days: Age in days to consider "old"
        """
        from src.app.db import connect
        
        cutoff = datetime.now() - timedelta(days=days)
        
        with connect(self.db_path) as conn:
            conn.execute("""
                UPDATE agent_messages
                SET status = 'archived'
                WHERE status IN ('completed', 'failed')
                AND created_at < ?
            """, (cutoff.isoformat(),))
            conn.commit()
        
        logger.info(f"Archived messages older than {days} days")
    
    def get_message_stats(self) -> Dict[str, Any]:
        """Get statistics about messages in the queue.
        
        Returns:
            Dictionary with message statistics
        """
        from src.app.db import connect
        
        with connect(self.db_path) as conn:
            stats = {}
            
            # Count by status
            for status in ["pending", "processing", "completed", "failed", "archived"]:
                count = conn.execute(
                    "SELECT COUNT(*) as count FROM agent_messages WHERE status = ?",
                    (status,)
                ).fetchone()
                stats[f"{status}_count"] = count["count"]
            
            # Average processing time
            avg_time = conn.execute("""
                SELECT AVG(
                    CAST((julianday(processed_at) - julianday(created_at)) * 24 * 60 * 60 AS INT)
                ) as avg_seconds
                FROM agent_messages
                WHERE processed_at IS NOT NULL
            """).fetchone()
            stats["avg_processing_seconds"] = avg_time["avg_seconds"]
        
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


def initialize_agent_bus(db_path: str = "agent.db") -> AgentBus:
    """Initialize agent bus with specific database path.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        AgentBus instance
    """
    global _bus
    _bus = AgentBus(db_path=db_path)
    return _bus
