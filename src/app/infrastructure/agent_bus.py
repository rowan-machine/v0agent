# src/app/infrastructure/agent_bus.py
"""
Agent Communication Bus

A message-based communication system for agent-to-agent interactions.
Supports priority routing, context preservation, and human-in-loop review.

This is the foundation layer - not yet connected to actual agents or APIs.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels for routing."""
    CRITICAL = 1    # Immediate processing required
    HIGH = 2        # Process within minutes
    NORMAL = 3      # Standard processing
    LOW = 4         # Background/batch processing
    DEFERRED = 5    # Process when idle


class MessageStatus(Enum):
    """Message lifecycle status."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AWAITING_REVIEW = "awaiting_review"  # Human-in-loop


class AgentType(Enum):
    """Types of agents in the system."""
    ORCHESTRATOR = "orchestrator"
    SIGNAL_EXTRACTOR = "signal_extractor"
    DIKW_SYNTHESIZER = "dikw_synthesizer"
    CAREER_COACH = "career_coach"
    DOCUMENTATION_READER = "documentation_reader"
    MEETING_ANALYZER = "meeting_analyzer"
    NOTIFICATION_AGENT = "notification_agent"
    HUMAN = "human"  # For human-in-loop


@dataclass
class AgentMessage:
    """
    A message passed between agents.
    
    Attributes:
        id: Unique message identifier
        source: Agent that sent the message
        target: Intended recipient agent
        message_type: Type of message (request, response, event, command)
        payload: Message content
        priority: Processing priority
        status: Current status
        context: Preserved context from conversation/thread
        metadata: Additional tracking info
        created_at: When message was created
        expires_at: When message expires (optional)
        requires_review: Whether human review is needed
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: AgentType = AgentType.ORCHESTRATOR
    target: AgentType = AgentType.ORCHESTRATOR
    message_type: str = "request"
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    requires_review: bool = False
    parent_id: Optional[str] = None  # For threading
    correlation_id: Optional[str] = None  # For request-response pairs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.value,
            "target": self.target.value,
            "message_type": self.message_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "context": self.context,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "requires_review": self.requires_review,
            "parent_id": self.parent_id,
            "correlation_id": self.correlation_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            source=AgentType(data.get("source", "orchestrator")),
            target=AgentType(data.get("target", "orchestrator")),
            message_type=data.get("message_type", "request"),
            payload=data.get("payload", {}),
            priority=MessagePriority(data.get("priority", 3)),
            status=MessageStatus(data.get("status", "pending")),
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            requires_review=data.get("requires_review", False),
            parent_id=data.get("parent_id"),
            correlation_id=data.get("correlation_id"),
        )


@dataclass
class AgentSubscription:
    """Subscription for an agent to receive messages."""
    agent_type: AgentType
    message_types: Set[str]
    handler: Callable[[AgentMessage], Any]
    priority_filter: Optional[MessagePriority] = None
    active: bool = True


class MessageQueue:
    """
    Priority-based message queue.
    
    Messages are sorted by priority and creation time.
    """
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queues: Dict[MessagePriority, List[AgentMessage]] = {
            p: [] for p in MessagePriority
        }
        self._lock = asyncio.Lock()
    
    async def push(self, message: AgentMessage) -> bool:
        """Add message to queue."""
        async with self._lock:
            queue = self._queues[message.priority]
            if len(queue) >= self.max_size:
                logger.warning(f"Queue full for priority {message.priority}")
                return False
            queue.append(message)
            message.status = MessageStatus.QUEUED
            return True
    
    async def pop(self, priority: Optional[MessagePriority] = None) -> Optional[AgentMessage]:
        """Get next message from queue (highest priority first)."""
        async with self._lock:
            if priority:
                queue = self._queues[priority]
                if queue:
                    return queue.pop(0)
                return None
            
            # Get from highest priority queue with messages
            for p in MessagePriority:
                if self._queues[p]:
                    return self._queues[p].pop(0)
            return None
    
    async def peek(self) -> Optional[AgentMessage]:
        """View next message without removing."""
        async with self._lock:
            for p in MessagePriority:
                if self._queues[p]:
                    return self._queues[p][0]
            return None
    
    def size(self) -> int:
        """Total messages across all queues."""
        return sum(len(q) for q in self._queues.values())
    
    def stats(self) -> Dict[str, int]:
        """Queue statistics by priority."""
        return {p.name: len(q) for p, q in self._queues.items()}


class AgentBus:
    """
    Central message bus for agent communication.
    
    Features:
    - Priority-based message routing
    - Subscription-based message delivery
    - Context preservation across messages
    - Human-in-loop review workflow
    - Message expiration and cleanup
    
    Example:
        ```python
        bus = AgentBus()
        
        # Subscribe to messages
        bus.subscribe(
            agent_type=AgentType.DIKW_SYNTHESIZER,
            message_types={"signal_extracted", "knowledge_ready"},
            handler=handle_dikw_messages
        )
        
        # Send a message
        await bus.send(AgentMessage(
            source=AgentType.SIGNAL_EXTRACTOR,
            target=AgentType.DIKW_SYNTHESIZER,
            message_type="signal_extracted",
            payload={"signals": [...]}
        ))
        
        # Start processing
        await bus.start()
        ```
    """
    
    def __init__(self):
        self._queue = MessageQueue()
        self._subscriptions: Dict[AgentType, List[AgentSubscription]] = defaultdict(list)
        self._message_history: List[AgentMessage] = []
        self._review_queue: List[AgentMessage] = []
        self._running = False
        self._processors: List[asyncio.Task] = []
        self._stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "messages_expired": 0,
            "reviews_pending": 0,
        }
    
    def subscribe(
        self,
        agent_type: AgentType,
        message_types: Set[str],
        handler: Callable[[AgentMessage], Any],
        priority_filter: Optional[MessagePriority] = None,
    ) -> str:
        """
        Subscribe an agent to receive messages.
        
        Returns subscription ID.
        """
        subscription = AgentSubscription(
            agent_type=agent_type,
            message_types=message_types,
            handler=handler,
            priority_filter=priority_filter,
        )
        self._subscriptions[agent_type].append(subscription)
        logger.info(f"Agent {agent_type.value} subscribed to {message_types}")
        return f"{agent_type.value}_{len(self._subscriptions[agent_type])}"
    
    def unsubscribe(self, agent_type: AgentType, subscription_id: str) -> bool:
        """Remove a subscription."""
        # Simplified - in production would use actual subscription ID tracking
        if agent_type in self._subscriptions:
            self._subscriptions[agent_type] = []
            return True
        return False
    
    async def send(self, message: AgentMessage) -> str:
        """
        Send a message through the bus.
        
        Returns message ID.
        """
        # Validate message
        if message.expires_at and message.expires_at < datetime.now():
            message.status = MessageStatus.EXPIRED
            self._stats["messages_expired"] += 1
            return message.id
        
        # Check if requires review
        if message.requires_review:
            message.status = MessageStatus.AWAITING_REVIEW
            self._review_queue.append(message)
            self._stats["reviews_pending"] += 1
            logger.info(f"Message {message.id} queued for human review")
            return message.id
        
        # Add to queue
        await self._queue.push(message)
        self._stats["messages_sent"] += 1
        self._message_history.append(message)
        
        # Trim history
        if len(self._message_history) > 1000:
            self._message_history = self._message_history[-500:]
        
        logger.debug(f"Message {message.id} queued: {message.source.value} -> {message.target.value}")
        return message.id
    
    async def send_and_wait(
        self,
        message: AgentMessage,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """
        Send a message and wait for response.
        
        Uses correlation_id to match response.
        """
        message.correlation_id = message.correlation_id or str(uuid.uuid4())
        await self.send(message)
        
        # Wait for response (simplified - in production would use proper async waiting)
        start = datetime.now()
        while (datetime.now() - start).total_seconds() < timeout:
            for msg in reversed(self._message_history):
                if (msg.correlation_id == message.correlation_id and 
                    msg.source == message.target and
                    msg.message_type == "response"):
                    return msg
            await asyncio.sleep(0.1)
        
        return None
    
    async def _process_message(self, message: AgentMessage) -> bool:
        """Process a single message by delivering to subscribers."""
        target_subs = self._subscriptions.get(message.target, [])
        
        delivered = False
        for sub in target_subs:
            if not sub.active:
                continue
            if message.message_type not in sub.message_types and "*" not in sub.message_types:
                continue
            if sub.priority_filter and message.priority != sub.priority_filter:
                continue
            
            try:
                message.status = MessageStatus.PROCESSING
                result = sub.handler(message)
                if asyncio.iscoroutine(result):
                    await result
                message.status = MessageStatus.DELIVERED
                delivered = True
                self._stats["messages_delivered"] += 1
            except Exception as e:
                logger.error(f"Handler error for message {message.id}: {e}")
                message.status = MessageStatus.FAILED
                self._stats["messages_failed"] += 1
        
        return delivered
    
    async def _processor_loop(self):
        """Main processing loop."""
        while self._running:
            message = await self._queue.pop()
            if message:
                await self._process_message(message)
            else:
                await asyncio.sleep(0.01)  # Avoid busy waiting
    
    async def start(self, num_processors: int = 3):
        """Start the message bus processors."""
        self._running = True
        for i in range(num_processors):
            task = asyncio.create_task(self._processor_loop())
            self._processors.append(task)
        logger.info(f"Agent bus started with {num_processors} processors")
    
    async def stop(self):
        """Stop the message bus."""
        self._running = False
        for task in self._processors:
            task.cancel()
        self._processors = []
        logger.info("Agent bus stopped")
    
    # Human-in-loop methods
    
    def get_pending_reviews(self) -> List[AgentMessage]:
        """Get messages awaiting human review."""
        return [m for m in self._review_queue if m.status == MessageStatus.AWAITING_REVIEW]
    
    async def approve_review(self, message_id: str) -> bool:
        """Approve a message for processing."""
        for msg in self._review_queue:
            if msg.id == message_id:
                msg.status = MessageStatus.PENDING
                msg.requires_review = False
                await self._queue.push(msg)
                self._review_queue.remove(msg)
                self._stats["reviews_pending"] -= 1
                return True
        return False
    
    async def reject_review(self, message_id: str, reason: str = "") -> bool:
        """Reject a message."""
        for msg in self._review_queue:
            if msg.id == message_id:
                msg.status = MessageStatus.REJECTED
                msg.metadata["rejection_reason"] = reason
                self._review_queue.remove(msg)
                self._stats["reviews_pending"] -= 1
                return True
        return False
    
    # Diagnostics
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bus statistics."""
        return {
            **self._stats,
            "queue_size": self._queue.size(),
            "queue_by_priority": self._queue.stats(),
            "subscriptions": {
                agent.value: len(subs) 
                for agent, subs in self._subscriptions.items()
            },
            "history_size": len(self._message_history),
        }
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict]:
        """Get recent message history."""
        return [m.to_dict() for m in self._message_history[-limit:]]


# Singleton instance
_bus_instance: Optional[AgentBus] = None


def get_agent_bus() -> AgentBus:
    """Get or create the global agent bus instance."""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = AgentBus()
    return _bus_instance


# Convenience functions for common message patterns

def create_signal_message(
    signals: List[Dict],
    meeting_id: str,
    source: AgentType = AgentType.SIGNAL_EXTRACTOR,
) -> AgentMessage:
    """Create a message for extracted signals."""
    return AgentMessage(
        source=source,
        target=AgentType.DIKW_SYNTHESIZER,
        message_type="signals_extracted",
        payload={
            "signals": signals,
            "meeting_id": meeting_id,
            "count": len(signals),
        },
        priority=MessagePriority.NORMAL,
    )


def create_dikw_promotion_message(
    item_id: str,
    from_level: str,
    to_level: str,
    source: AgentType = AgentType.DIKW_SYNTHESIZER,
) -> AgentMessage:
    """Create a message for DIKW level promotion."""
    return AgentMessage(
        source=source,
        target=AgentType.ORCHESTRATOR,
        message_type="dikw_promoted",
        payload={
            "item_id": item_id,
            "from_level": from_level,
            "to_level": to_level,
        },
        priority=MessagePriority.HIGH,
    )


def create_notification_message(
    title: str,
    body: str,
    target_user: str = "default",
    priority: MessagePriority = MessagePriority.NORMAL,
) -> AgentMessage:
    """Create a notification message."""
    return AgentMessage(
        source=AgentType.ORCHESTRATOR,
        target=AgentType.NOTIFICATION_AGENT,
        message_type="send_notification",
        payload={
            "title": title,
            "body": body,
            "target_user": target_user,
        },
        priority=priority,
    )
