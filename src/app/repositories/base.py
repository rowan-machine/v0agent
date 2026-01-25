# src/app/repositories/base.py
"""
Base Repository - Abstract Interface (Port)

Defines the contract that all repository implementations must follow.
This is the "port" in ports and adapters terminology.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


@dataclass
class QueryOptions:
    """Options for repository queries."""
    limit: int = 100
    offset: int = 0
    order_by: str = "created_at"
    order_desc: bool = True
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult(Generic[T]):
    """Result wrapper for repository queries."""
    data: List[T]
    total_count: int = 0
    has_more: bool = False
    
    @property
    def count(self) -> int:
        return len(self.data)


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository defining the interface for all data access.
    
    This is the PORT that defines what operations are available.
    Concrete implementations (adapters) provide the actual behavior.
    """
    
    @abstractmethod
    def get_all(self, options: Optional[QueryOptions] = None) -> List[T]:
        """
        Get all entities with optional filtering and pagination.
        
        Args:
            options: Query options for filtering, sorting, pagination
            
        Returns:
            List of entities
        """
        pass
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Get a single entity by its ID.
        
        Args:
            entity_id: The unique identifier
            
        Returns:
            The entity or None if not found
        """
        pass
    
    @abstractmethod
    def get_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Get the count of entities matching optional filters.
        
        Args:
            filters: Optional filter criteria
            
        Returns:
            Count of matching entities
        """
        pass
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Optional[T]:
        """
        Create a new entity.
        
        Args:
            data: Entity data
            
        Returns:
            The created entity or None on failure
        """
        pass
    
    @abstractmethod
    def update(self, entity_id: str, data: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity.
        
        Args:
            entity_id: The ID of the entity to update
            data: Fields to update
            
        Returns:
            The updated entity or None on failure
        """
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by ID.
        
        Args:
            entity_id: The ID of the entity to delete
            
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    def exists(self, entity_id: str) -> bool:
        """Check if an entity exists."""
        return self.get_by_id(entity_id) is not None
    
    def get_recent(self, limit: int = 5) -> List[T]:
        """Get the most recent entities."""
        options = QueryOptions(limit=limit, order_by="created_at", order_desc=True)
        return self.get_all(options)


class ReadOnlyRepository(ABC, Generic[T]):
    """
    Read-only repository for cases where write operations are not needed.
    Useful for reporting, analytics, or external data sources.
    """
    
    @abstractmethod
    def get_all(self, options: Optional[QueryOptions] = None) -> List[T]:
        pass
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        pass
    
    @abstractmethod
    def get_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        pass
