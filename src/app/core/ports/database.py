# src/app/core/ports/database.py
"""
Database Port Interface

Abstract interface for all database operations.
Implementations can be:
- SupabaseDatabaseAdapter (production)
- SQLiteDatabaseAdapter (local/privacy)
- PostgresDatabaseAdapter (self-hosted)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypeVar, Generic
from datetime import datetime

T = TypeVar('T')


class DatabasePort(ABC):
    """
    Abstract port interface for database operations.
    
    All database adapters must implement this interface.
    This allows seamless switching between different database backends.
    """
    
    # =============================================================================
    # GENERIC CRUD OPERATIONS
    # =============================================================================
    
    @abstractmethod
    def get_by_id(self, table: str, id: Any) -> Optional[Dict[str, Any]]:
        """Get a single record by ID."""
        pass
    
    @abstractmethod
    def get_all(
        self, 
        table: str, 
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all records from a table with optional filters."""
        pass
    
    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record and return it with generated ID."""
        pass
    
    @abstractmethod
    def insert_many(self, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert multiple records."""
        pass
    
    @abstractmethod
    def update(self, table: str, id: Any, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record by ID."""
        pass
    
    @abstractmethod
    def upsert(
        self, 
        table: str, 
        data: Dict[str, Any], 
        conflict_columns: List[str]
    ) -> Dict[str, Any]:
        """Insert or update based on conflict columns."""
        pass
    
    @abstractmethod
    def delete(self, table: str, id: Any) -> bool:
        """Delete a record by ID."""
        pass
    
    @abstractmethod
    def delete_where(self, table: str, filters: Dict[str, Any]) -> int:
        """Delete records matching filters. Returns count deleted."""
        pass
    
    # =============================================================================
    # QUERY OPERATIONS
    # =============================================================================
    
    @abstractmethod
    def count(self, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records in a table with optional filters."""
        pass
    
    @abstractmethod
    def exists(self, table: str, filters: Dict[str, Any]) -> bool:
        """Check if any records match the filters."""
        pass
    
    @abstractmethod
    def query(
        self,
        table: str,
        select: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Flexible query builder.
        
        Args:
            table: Table name
            select: Columns to select (None = all)
            filters: Dictionary of column: value filters
            order_by: Column to order by
            order_desc: If True, order descending
            limit: Max records to return
            offset: Records to skip
        """
        pass
    
    # =============================================================================
    # ADVANCED QUERIES
    # =============================================================================
    
    @abstractmethod
    def search_text(
        self, 
        table: str, 
        column: str, 
        search_term: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Full-text search on a column."""
        pass
    
    @abstractmethod
    def execute_raw(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query (use sparingly, prefer typed methods).
        
        WARNING: This bypasses the abstraction layer and may not be portable
        between database backends. Use only when necessary.
        """
        pass
    
    # =============================================================================
    # TRANSACTION SUPPORT
    # =============================================================================
    
    @abstractmethod
    def begin_transaction(self):
        """Begin a transaction."""
        pass
    
    @abstractmethod
    def commit(self):
        """Commit the current transaction."""
        pass
    
    @abstractmethod
    def rollback(self):
        """Rollback the current transaction."""
        pass
    
    # =============================================================================
    # CONNECTION MANAGEMENT
    # =============================================================================
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        pass
    
    @abstractmethod
    def close(self):
        """Close the database connection."""
        pass


class MeetingsRepository(ABC):
    """Repository interface for meetings domain."""
    
    @abstractmethod
    def get_meeting(self, meeting_id: int) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_meetings(
        self, 
        limit: int = 50,
        with_signals: bool = False,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def create_meeting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def update_meeting(self, meeting_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def delete_meeting(self, meeting_id: int) -> bool:
        pass


class DocumentsRepository(ABC):
    """Repository interface for documents domain."""
    
    @abstractmethod
    def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def create_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def update_document(self, doc_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def delete_document(self, doc_id: int) -> bool:
        pass


class TicketsRepository(ABC):
    """Repository interface for tickets domain."""
    
    @abstractmethod
    def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_tickets(
        self, 
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def create_ticket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def update_ticket(self, ticket_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def delete_ticket(self, ticket_id: int) -> bool:
        pass


class DIKWRepository(ABC):
    """Repository interface for DIKW items domain."""
    
    @abstractmethod
    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_items(
        self,
        level: Optional[str] = None,
        status: str = "active",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_pyramid(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all items organized by DIKW level."""
        pass
    
    @abstractmethod
    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def update_item(self, item_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def promote_item(self, item_id: int, to_level: str) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def delete_item(self, item_id: int) -> bool:
        pass


class SignalsRepository(ABC):
    """Repository interface for signals domain."""
    
    @abstractmethod
    def get_feedback(
        self, 
        meeting_id: Optional[int] = None,
        signal_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def save_feedback(
        self, 
        meeting_id: int, 
        signal_type: str, 
        signal_text: str, 
        feedback: str
    ) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_status(
        self, 
        meeting_id: int, 
        signal_type: str, 
        signal_text: str
    ) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def update_status(
        self, 
        meeting_id: int, 
        signal_type: str, 
        signal_text: str, 
        status: str
    ) -> Dict[str, Any]:
        pass


class ConversationsRepository(ABC):
    """Repository interface for chat conversations domain."""
    
    @abstractmethod
    def get_conversation(self, conv_id: int) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_conversations(
        self, 
        include_archived: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def create_conversation(self, title: Optional[str] = None) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def update_conversation(self, conv_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def delete_conversation(self, conv_id: int) -> bool:
        pass
    
    @abstractmethod
    def get_messages(self, conv_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def add_message(
        self, 
        conv_id: int, 
        role: str, 
        content: str,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        pass


class SettingsRepository(ABC):
    """Repository interface for settings."""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        pass
    
    @abstractmethod
    def get_all(self) -> Dict[str, Any]:
        pass


class NotificationsRepository(ABC):
    """Repository interface for notifications."""
    
    @abstractmethod
    def get_notifications(
        self, 
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def create_notification(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def mark_read(self, notification_id: int) -> bool:
        pass
    
    @abstractmethod
    def mark_all_read(self) -> int:
        pass
    
    @abstractmethod
    def delete_notification(self, notification_id: int) -> bool:
        pass
