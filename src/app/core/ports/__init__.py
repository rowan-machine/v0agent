# src/app/core/ports/__init__.py
"""
Port Interfaces for Dependency Inversion

Protocol-based interfaces that adapters must implement.
Using Protocols (structural subtyping) instead of ABC for:
- No inheritance required - just implement the methods
- Better IDE support and type checking
- Easier mocking in tests
"""

# New Protocol-based interfaces (preferred)
from .protocols import (
    # Database
    DatabaseProtocol,
    
    # Repositories
    MeetingRepositoryProtocol,
    DocumentRepositoryProtocol,
    TicketRepositoryProtocol,
    DIKWRepositoryProtocol,
    SignalRepositoryProtocol,
    ConversationRepositoryProtocol,
    CareerRepositoryProtocol,
    NotificationRepositoryProtocol,
    
    # Services
    EmbeddingProtocol,
    StorageProtocol,
    LLMProtocol,
    PocketClientProtocol,
    
    # Settings
    SettingsProtocol,
    
    # Transactions
    UnitOfWorkProtocol,
)

# Legacy ABC-based interfaces (deprecated, for backward compatibility)
from .database import (
    DatabasePort,
    MeetingsRepository,
    DocumentsRepository,
    TicketsRepository,
    DIKWRepository,
    SignalsRepository,
    ConversationsRepository,
    SettingsRepository,
    NotificationsRepository,
)
from .embedding import EmbeddingPort
from .storage import StoragePort

__all__ = [
    # New Protocol-based (preferred)
    "DatabaseProtocol",
    "MeetingRepositoryProtocol",
    "DocumentRepositoryProtocol", 
    "TicketRepositoryProtocol",
    "DIKWRepositoryProtocol",
    "SignalRepositoryProtocol",
    "ConversationRepositoryProtocol",
    "CareerRepositoryProtocol",
    "NotificationRepositoryProtocol",
    "EmbeddingProtocol",
    "StorageProtocol",
    "LLMProtocol",
    "PocketClientProtocol",
    "SettingsProtocol",
    "UnitOfWorkProtocol",
    
    # Legacy (deprecated)
    "DatabasePort",
    "MeetingsRepository",
    "DocumentsRepository",
    "TicketsRepository",
    "DIKWRepository",
    "SignalsRepository",
    "ConversationsRepository",
    "SettingsRepository",
    "NotificationsRepository",
    "EmbeddingPort",
    "StoragePort",
]
