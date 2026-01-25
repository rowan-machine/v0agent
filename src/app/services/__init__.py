"""
SignalFlow services - Business logic layer between API and agents.
Includes embeddings, encryption, sync, and other utilities.
"""

# Make chromadb optional since we're migrating to Supabase pgvector
try:
    from .embeddings import EmbeddingService, create_embedding_service
except ImportError:
    EmbeddingService = None
    create_embedding_service = None

from .encryption import EncryptionService, create_encryption_service
from .signal_learning import (
    SignalLearningService,
    get_signal_learning_service,
    get_learning_context_for_extraction,
    refresh_signal_learnings,
)

# Meetings service - reads directly from Supabase
from . import meetings_supabase

__all__ = [
    "EmbeddingService",
    "create_embedding_service",
    "EncryptionService",
    "create_encryption_service",
    "SignalLearningService",
    "get_signal_learning_service",
    "get_learning_context_for_extraction",
    "refresh_signal_learnings",
    "meetings_supabase",
]
