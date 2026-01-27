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

# Supabase services - read directly from Supabase
# Import with new names and provide backward-compatible aliases
from . import meeting_service as meetings_supabase
from . import document_service as documents_supabase
from . import ticket_service as tickets_supabase

# Also expose with new naming convention
from . import meeting_service
from . import document_service
from . import ticket_service

__all__ = [
    "EmbeddingService",
    "create_embedding_service",
    "EncryptionService",
    "create_encryption_service",
    "SignalLearningService",
    "get_signal_learning_service",
    "get_learning_context_for_extraction",
    "refresh_signal_learnings",
    # Backward-compatible aliases
    "meetings_supabase",
    "documents_supabase",
    "tickets_supabase",
    # New naming convention
    "meeting_service",
    "document_service",
    "ticket_service",
]
