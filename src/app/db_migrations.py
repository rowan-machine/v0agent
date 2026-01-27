"""
Database Migrations - DEPRECATED

DEPRECATED: SQLite migrations are no longer needed.
All database migrations should be handled through Supabase.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

def _emit_deprecation():
    warnings.warn("SQLite migrations deprecated. Use Supabase.", DeprecationWarning, stacklevel=2)

def migrate_meeting_documents():
    _emit_deprecation()

def migrate_add_import_columns():
    _emit_deprecation()

def migrate_conversation_mindmaps():
    _emit_deprecation()

def migrate_mindmap_syntheses():
    _emit_deprecation()

def migrate_mindmap_synthesis_history():
    _emit_deprecation()

def migrate_mindmap_titles():
    _emit_deprecation()

def run_all_migrations():
    _emit_deprecation()
    logger.info("SQLite migrations skipped - using Supabase-only mode")

