# src/app/core/ports/protocols.py
"""
Protocol-based Interfaces for V0Agent

Using typing.Protocol for structural subtyping instead of ABC.
Benefits:
- No inheritance required - just implement the methods
- Better IDE support and type checking
- Easier mocking in tests
- More Pythonic (duck typing with type safety)
"""

from typing import Protocol, List, Dict, Any, Optional, Tuple, TypeVar, runtime_checkable
from datetime import datetime

T = TypeVar('T')


# =============================================================================
# DATABASE PROTOCOLS
# =============================================================================

@runtime_checkable
class DatabaseProtocol(Protocol):
    """
    Protocol for generic database operations.
    
    Implementations: SupabaseAdapter, SQLiteAdapter
    """
    
    def get_by_id(self, table: str, id: Any) -> Optional[Dict[str, Any]]:
        """Get a single record by ID."""
        ...
    
    def get_all(
        self, 
        table: str, 
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all records with optional filtering."""
        ...
    
    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record."""
        ...
    
    def update(self, table: str, id: Any, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record by ID."""
        ...
    
    def upsert(
        self, 
        table: str, 
        data: Dict[str, Any], 
        conflict_columns: List[str]
    ) -> Dict[str, Any]:
        """Insert or update based on conflict columns."""
        ...
    
    def delete(self, table: str, id: Any) -> bool:
        """Delete a record by ID."""
        ...
    
    def count(self, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching filters."""
        ...
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
        ...


# =============================================================================
# REPOSITORY PROTOCOLS (Domain-specific)
# =============================================================================

@runtime_checkable
class MeetingRepositoryProtocol(Protocol):
    """Protocol for meeting persistence operations."""
    
    def get(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get meeting by ID."""
        ...
    
    def list(
        self, 
        limit: int = 50,
        offset: int = 0,
        with_signals: bool = False,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """List meetings with optional filters."""
        ...
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new meeting."""
        ...
    
    def update(self, meeting_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update meeting."""
        ...
    
    def delete(self, meeting_id: str) -> bool:
        """Delete meeting."""
        ...
    
    def get_signals(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get all signals for a meeting."""
        ...


@runtime_checkable
class DocumentRepositoryProtocol(Protocol):
    """Protocol for document persistence operations."""
    
    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        ...
    
    def list(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List documents."""
        ...
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new document."""
        ...
    
    def update(self, doc_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update document."""
        ...
    
    def delete(self, doc_id: str) -> bool:
        """Delete document."""
        ...
    
    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search documents by content."""
        ...


@runtime_checkable
class TicketRepositoryProtocol(Protocol):
    """Protocol for ticket persistence operations."""
    
    def get(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get ticket by ID."""
        ...
    
    def list(
        self, 
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List tickets with optional status filter."""
        ...
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new ticket."""
        ...
    
    def update(self, ticket_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update ticket."""
        ...
    
    def delete(self, ticket_id: str) -> bool:
        """Delete ticket."""
        ...
    
    def get_decomposition(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get task decomposition for a ticket."""
        ...


@runtime_checkable
class DIKWRepositoryProtocol(Protocol):
    """Protocol for DIKW pyramid item operations."""
    
    def get(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get DIKW item by ID."""
        ...
    
    def list(
        self,
        level: Optional[str] = None,
        status: str = "active",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List DIKW items with optional filters."""
        ...
    
    def get_pyramid(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all items organized by DIKW level."""
        ...
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new DIKW item."""
        ...
    
    def update(self, item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update DIKW item."""
        ...
    
    def promote(self, item_id: str, to_level: str) -> Optional[Dict[str, Any]]:
        """Promote item to a higher DIKW level."""
        ...
    
    def delete(self, item_id: str) -> bool:
        """Delete DIKW item."""
        ...


@runtime_checkable
class SignalRepositoryProtocol(Protocol):
    """Protocol for signal feedback and status operations."""
    
    def get_feedback(
        self, 
        meeting_id: Optional[str] = None,
        signal_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get signal feedback."""
        ...
    
    def save_feedback(
        self, 
        meeting_id: str, 
        signal_type: str, 
        signal_text: str, 
        feedback: str
    ) -> Dict[str, Any]:
        """Save feedback for a signal."""
        ...
    
    def get_status(
        self, 
        meeting_id: str, 
        signal_type: str, 
        signal_text: str
    ) -> Optional[Dict[str, Any]]:
        """Get status for a specific signal."""
        ...
    
    def update_status(
        self, 
        meeting_id: str, 
        signal_type: str, 
        signal_text: str, 
        status: str
    ) -> Dict[str, Any]:
        """Update signal status."""
        ...


@runtime_checkable
class ConversationRepositoryProtocol(Protocol):
    """Protocol for chat conversation operations."""
    
    def get(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by ID."""
        ...
    
    def list(
        self, 
        include_archived: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List conversations."""
        ...
    
    def create(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Create a new conversation."""
        ...
    
    def update(self, conv_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update conversation."""
        ...
    
    def delete(self, conv_id: str) -> bool:
        """Delete conversation."""
        ...
    
    def get_messages(self, conv_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages for a conversation."""
        ...
    
    def add_message(
        self, 
        conv_id: str, 
        role: str, 
        content: str,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a message to a conversation."""
        ...


@runtime_checkable
class CareerRepositoryProtocol(Protocol):
    """Protocol for career tracking operations."""
    
    def get_profile(self) -> Optional[Dict[str, Any]]:
        """Get the career profile."""
        ...
    
    def update_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the career profile."""
        ...
    
    def list_memories(
        self,
        importance_min: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List career memories."""
        ...
    
    def add_memory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a career memory."""
        ...
    
    def list_suggestions(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List career suggestions."""
        ...
    
    def add_suggestion(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a career suggestion."""
        ...
    
    def update_suggestion(self, suggestion_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a suggestion."""
        ...


@runtime_checkable 
class NotificationRepositoryProtocol(Protocol):
    """Protocol for notification operations."""
    
    def list(
        self, 
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List notifications."""
        ...
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a notification."""
        ...
    
    def mark_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        ...
    
    def mark_all_read(self) -> int:
        """Mark all notifications as read."""
        ...
    
    def delete(self, notification_id: str) -> bool:
        """Delete notification."""
        ...


# =============================================================================
# SERVICE PROTOCOLS (External Services)
# =============================================================================

@runtime_checkable
class EmbeddingProtocol(Protocol):
    """Protocol for embedding/vector operations."""
    
    def generate(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        ...
    
    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        ...
    
    def similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between embeddings."""
        ...
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar items."""
        ...
    
    def store(
        self,
        id: Any,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store an embedding."""
        ...
    
    def delete(self, id: Any) -> bool:
        """Delete an embedding."""
        ...


@runtime_checkable
class StorageProtocol(Protocol):
    """Protocol for file storage operations."""
    
    def upload(
        self,
        content: bytes,
        filename: str,
        bucket: str = "uploads",
        path: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a file."""
        ...
    
    def download(self, path: str, bucket: str = "uploads") -> Optional[bytes]:
        """Download a file."""
        ...
    
    def delete(self, path: str, bucket: str = "uploads") -> bool:
        """Delete a file."""
        ...
    
    def get_url(
        self,
        path: str,
        bucket: str = "uploads",
        expires_in: Optional[int] = None
    ) -> Optional[str]:
        """Get public URL for a file."""
        ...
    
    def list(
        self,
        path: str = "",
        bucket: str = "uploads",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List files in a path."""
        ...
    
    def exists(self, path: str, bucket: str = "uploads") -> bool:
        """Check if file exists."""
        ...


@runtime_checkable
class LLMProtocol(Protocol):
    """Protocol for LLM/AI operations."""
    
    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text completion."""
        ...
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate chat completion."""
        ...
    
    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7
    ):
        """Stream chat completion."""
        ...


@runtime_checkable
class PocketClientProtocol(Protocol):
    """Protocol for Pocket integration."""
    
    def get_recordings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get list of recordings."""
        ...
    
    def get_recording(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific recording."""
        ...
    
    def get_transcript(self, recording_id: str) -> Optional[str]:
        """Get transcript for a recording."""
        ...
    
    def get_mindmap(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Get mindmap for a recording."""
        ...


# =============================================================================
# SETTINGS PROTOCOLS
# =============================================================================

@runtime_checkable
class SettingsProtocol(Protocol):
    """Protocol for settings operations."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        ...
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        ...
    
    def all(self) -> Dict[str, Any]:
        """Get all settings."""
        ...


# =============================================================================
# COMPOSITE PROTOCOLS (Aggregated interfaces)
# =============================================================================

class UnitOfWorkProtocol(Protocol):
    """Protocol for transaction management."""
    
    def begin(self) -> None:
        """Begin a transaction."""
        ...
    
    def commit(self) -> None:
        """Commit the transaction."""
        ...
    
    def rollback(self) -> None:
        """Rollback the transaction."""
        ...
    
    def __enter__(self):
        """Context manager entry."""
        ...
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        ...
