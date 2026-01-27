# src/app/core/container.py
"""
Dependency Injection Container

Central configuration for all dependencies in the application.
This allows easy switching between different adapters (Supabase ↔ SQLite, etc.)
without changing business logic.

Usage:
    from src.app.core.container import container
    
    # Get the database adapter
    db = container.database()
    
    # Get a specific repository
    meetings_repo = container.meetings_repository()
"""

import os
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class Container:
    """
    Dependency injection container.
    
    Provides factory methods for all adapters and repositories.
    Configuration is determined by environment variables.
    """
    
    def __init__(self):
        self._database_type = os.getenv("DATABASE_TYPE", "supabase")  # or "sqlite"
        self._embedding_type = os.getenv("EMBEDDING_TYPE", "openai")  # or "local"
        self._storage_type = os.getenv("STORAGE_TYPE", "supabase")  # or "local"
        
        # Cached instances
        self._db_instance = None
        self._embedding_instance = None
        self._storage_instance = None
        
        logger.info(f"Container initialized: db={self._database_type}, "
                   f"embedding={self._embedding_type}, storage={self._storage_type}")
    
    # =============================================================================
    # DATABASE
    # =============================================================================
    
    def database(self):
        """
        Get the database adapter instance.
        
        Returns SupabaseDatabaseAdapter or SQLiteDatabaseAdapter based on config.
        """
        if self._db_instance is None:
            if self._database_type == "supabase":
                from ..adapters.database.supabase import SupabaseDatabaseAdapter
                self._db_instance = SupabaseDatabaseAdapter()
            elif self._database_type == "sqlite":
                from ..adapters.database.sqlite import SQLiteDatabaseAdapter
                db_path = os.getenv("SQLITE_DB_PATH", "agent.db")
                self._db_instance = SQLiteDatabaseAdapter(db_path)
            else:
                raise ValueError(f"Unknown database type: {self._database_type}")
        return self._db_instance
    
    def meetings_repository(self):
        """Get the meetings repository."""
        if self._database_type == "supabase":
            from ..adapters.database.supabase import SupabaseMeetingsRepository
            return SupabaseMeetingsRepository(self.database())
        else:
            # SQLite uses the same repository pattern
            from ..adapters.database.supabase import SupabaseMeetingsRepository
            return SupabaseMeetingsRepository(self.database())
    
    def dikw_repository(self):
        """Get the DIKW repository."""
        from ..adapters.database.supabase import SupabaseDIKWRepository
        return SupabaseDIKWRepository(self.database())
    
    def signals_repository(self):
        """Get the signals repository."""
        from ..adapters.database.supabase import SupabaseSignalsRepository
        return SupabaseSignalsRepository(self.database())
    
    def settings_repository(self):
        """Get the settings repository."""
        from ..adapters.database.supabase import SupabaseSettingsRepository
        return SupabaseSettingsRepository(self.database())
    
    def notifications_repository(self):
        """Get the notifications repository."""
        from ..adapters.database.supabase import SupabaseNotificationsRepository
        return SupabaseNotificationsRepository(self.database())
    
    # =============================================================================
    # EMBEDDINGS
    # =============================================================================
    
    def embedding_provider(self):
        """
        Get the embedding provider instance.
        
        Returns OpenAI or local embedding adapter based on config.
        """
        if self._embedding_instance is None:
            if self._embedding_type == "openai":
                from ..adapters.embedding.openai import OpenAIEmbeddingAdapter
                self._embedding_instance = OpenAIEmbeddingAdapter()
            elif self._embedding_type == "local":
                from ..adapters.embedding.local import LocalEmbeddingAdapter
                self._embedding_instance = LocalEmbeddingAdapter()
            else:
                # Default to OpenAI
                from ..adapters.embedding.openai import OpenAIEmbeddingAdapter
                self._embedding_instance = OpenAIEmbeddingAdapter()
        return self._embedding_instance
    
    # =============================================================================
    # STORAGE
    # =============================================================================
    
    def storage_provider(self):
        """
        Get the storage provider instance.
        
        Returns Supabase or local storage adapter based on config.
        """
        if self._storage_instance is None:
            if self._storage_type == "supabase":
                from ..adapters.storage.supabase import SupabaseStorageAdapter
                self._storage_instance = SupabaseStorageAdapter()
            elif self._storage_type == "local":
                from ..adapters.storage.local import LocalStorageAdapter
                self._storage_instance = LocalStorageAdapter()
            else:
                # Default to Supabase
                from ..adapters.storage.supabase import SupabaseStorageAdapter
                self._storage_instance = SupabaseStorageAdapter()
        return self._storage_instance
    
    # =============================================================================
    # UTILITY
    # =============================================================================
    
    def reset(self):
        """Reset all cached instances (useful for testing)."""
        self._db_instance = None
        self._embedding_instance = None
        self._storage_instance = None
        logger.info("Container reset")
    
    def configure(
        self, 
        database: Optional[str] = None,
        embedding: Optional[str] = None,
        storage: Optional[str] = None
    ):
        """
        Reconfigure the container at runtime.
        
        Args:
            database: "supabase" or "sqlite"
            embedding: "openai" or "local"
            storage: "supabase" or "local"
        """
        if database:
            self._database_type = database
            self._db_instance = None
        if embedding:
            self._embedding_type = embedding
            self._embedding_instance = None
        if storage:
            self._storage_type = storage
            self._storage_instance = None
        logger.info(f"Container reconfigured: db={self._database_type}, "
                   f"embedding={self._embedding_type}, storage={self._storage_type}")


# Global container instance
container = Container()


# Convenience functions for common access patterns
def get_db():
    """Get the database adapter."""
    return container.database()


def get_meetings_repo():
    """Get the meetings repository."""
    return container.meetings_repository()


def get_dikw_repo():
    """Get the DIKW repository."""
    return container.dikw_repository()


def get_signals_repo():
    """Get the signals repository."""
    return container.signals_repository()


def get_settings_repo():
    """Get the settings repository."""
    return container.settings_repository()


def get_notifications_repo():
    """Get the notifications repository."""
    return container.notifications_repository()


def get_embedding_provider():
    """Get the embedding provider."""
    return container.embedding_provider()


def get_storage_provider():
    """Get the storage provider."""
    return container.storage_provider()
