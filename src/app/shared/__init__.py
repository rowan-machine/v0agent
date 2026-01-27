# src/app/shared/__init__.py
"""
Shared Infrastructure Layer

This module contains shared infrastructure components used across the application:
- config: Application configuration and settings
- infrastructure: Database clients, external service connections
- repositories: Data access layer (ports and adapters pattern)
- services: Business logic services shared across domains
- utils: Common utilities and helpers

Architecture:
    shared/
    ├── config/          # Configuration management
    ├── infrastructure/  # Database clients, external APIs
    ├── repositories/    # Data access (abstract + implementations)
    ├── services/        # Shared business services
    └── utils/           # Utilities, helpers, file operations

Usage:
    from src.app.shared.repositories import get_meeting_repository
    from src.app.shared.infrastructure import get_supabase_client
    from src.app.shared.services import EmbeddingService
"""

# Re-export from submodules for convenience
from .repositories import (
    # Factories
    get_meeting_repository,
    get_document_repository,
    get_ticket_repository,
    get_signal_repository,
    get_settings_repository,
    get_ai_memory_repository,
    get_agent_messages_repository,
    get_mindmap_repository,
    get_notifications_repository,
    get_career_repository,
    get_dikw_repository,
)

__all__ = [
    # Repository factories
    "get_meeting_repository",
    "get_document_repository",
    "get_ticket_repository",
    "get_signal_repository",
    "get_settings_repository",
    "get_ai_memory_repository",
    "get_agent_messages_repository",
    "get_mindmap_repository",
    "get_notifications_repository",
    "get_career_repository",
    "get_dikw_repository",
]
