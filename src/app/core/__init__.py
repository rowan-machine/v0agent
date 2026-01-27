# src/app/core/__init__.py
"""
Core domain layer - interfaces and abstractions.

This package contains:
- Port interfaces (abstract base classes) for database, embeddings, etc.
- Domain models and entities
- Service interfaces

Following Ports and Adapters (Hexagonal Architecture):
- Ports are the interfaces that define how the domain interacts with the outside world
- Adapters are the concrete implementations of those ports
"""

from .ports import (
    DatabasePort,
    EmbeddingPort,
    StoragePort,
)
from .models import (
    Meeting,
    Document,
    Ticket,
    DIKWItem,
    Signal,
    Conversation,
    Message,
)

__all__ = [
    # Ports
    "DatabasePort",
    "EmbeddingPort", 
    "StoragePort",
    # Models
    "Meeting",
    "Document",
    "Ticket",
    "DIKWItem",
    "Signal",
    "Conversation",
    "Message",
]
