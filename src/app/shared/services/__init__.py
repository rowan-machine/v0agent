# src/app/shared/services/__init__.py
"""
Shared Services - Business logic services used across domains

This module contains services that are shared across multiple domains.
Domain-specific services should live in their respective domain folders.

Available services:
- EmbeddingService: Vector embeddings for semantic search
- EncryptionService: Data encryption/decryption
- SignalLearningService: ML signal extraction learning
"""

# Re-export from legacy location during migration
from ...services.encryption import (
    EncryptionService,
    create_encryption_service,
)

from ...services.signal_learning import (
    SignalLearningService,
    get_signal_learning_service,
    get_learning_context_for_extraction,
    refresh_signal_learnings,
)

# Embedding service (optional - depends on chromadb)
try:
    from ...services.embeddings import (
        EmbeddingService,
        create_embedding_service,
    )
except ImportError:
    EmbeddingService = None
    create_embedding_service = None

__all__ = [
    # Encryption
    "EncryptionService",
    "create_encryption_service",
    # Signal Learning
    "SignalLearningService",
    "get_signal_learning_service",
    "get_learning_context_for_extraction",
    "refresh_signal_learnings",
    # Embeddings (optional)
    "EmbeddingService",
    "create_embedding_service",
]
