"""
SignalFlow services - Business logic layer between API and agents.
Includes embeddings, encryption, sync, and other utilities.

MIGRATION NOTE (2026-01-27):
- Old names (meetings_supabase, documents_supabase, tickets_supabase) are DEPRECATED
- Use new names: meeting_service, document_service, ticket_service
- Or use shared layer: from src.app.shared.repositories import get_meeting_repository
"""
import warnings

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

# Services with new naming convention (Supabase-only)
from . import meeting_service
from . import document_service
from . import ticket_service

# ============================================================================
# DEPRECATED ALIASES - Will be removed in future release
# These allow gradual migration from old naming convention
# ============================================================================
# TODO: Remove once all imports are updated to new names

# Backward compatibility aliases (deprecated)
meetings_supabase = meeting_service
documents_supabase = document_service
tickets_supabase = ticket_service

__all__ = [
    "EmbeddingService",
    "create_embedding_service",
    "EncryptionService",
    "create_encryption_service",
    "SignalLearningService",
    "get_signal_learning_service",
    "get_learning_context_for_extraction",
    "refresh_signal_learnings",
    # New naming convention (preferred)
    "meeting_service",
    "document_service",
    "ticket_service",
    # Deprecated aliases (will be removed)
    "meetings_supabase",
    "documents_supabase",
    "tickets_supabase",
]

