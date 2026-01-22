# src/app/db_migrations.py
"""
Database Migrations - Phase 4.1 Infrastructure.

Handles schema evolution with backward compatibility:
1. Create new tables alongside old
2. Migrate data incrementally  
3. Create compatibility views
4. Retire old tables when safe

Migration Pattern:
- V2 tables have sync metadata (device_id, sync_version, etc.)
- Views unify old and new data for backward compatibility
- Feature flags control which tables are used
"""

import sqlite3
from .db import connect


# -------------------------
# Migration Version Tracking
# -------------------------

MIGRATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY,
    version TEXT NOT NULL UNIQUE,
    description TEXT,
    applied_at TEXT DEFAULT (datetime('now'))
);
"""


def get_applied_migrations() -> set:
    """Get set of already applied migration versions."""
    with connect() as conn:
        conn.execute(MIGRATIONS_SCHEMA)
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def mark_migration_applied(version: str, description: str):
    """Mark a migration as applied."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, description)
        )
        conn.commit()


# -------------------------
# Migration: V4.1.1 - Device Registry
# -------------------------

MIGRATION_4_1_1 = """
-- Device registry for multi-device sync (Phase 4.1)
CREATE TABLE IF NOT EXISTS device_registry (
    id INTEGER PRIMARY KEY,
    device_id TEXT UNIQUE NOT NULL,
    device_name TEXT NOT NULL,
    device_type TEXT NOT NULL,          -- 'laptop', 'desktop', 'mobile', 'tablet'
    app_version TEXT,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    mdns_name TEXT,                      -- e.g., "rowan-macbook.local"
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_registry_device_id ON device_registry(device_id);
CREATE INDEX IF NOT EXISTS idx_device_registry_last_seen ON device_registry(last_seen);
"""


def migrate_4_1_1_device_registry():
    """Create device_registry table for multi-device sync."""
    version = "4.1.1"
    if version in get_applied_migrations():
        return False
    
    with connect() as conn:
        conn.executescript(MIGRATION_4_1_1)
        conn.commit()
    
    mark_migration_applied(version, "Device registry for multi-device sync")
    return True


# -------------------------
# Migration: V4.1.2 - Agent Task Queue
# -------------------------

MIGRATION_4_1_2 = """
-- Agent task queue for agent-to-agent communication (Phase 4.1)
CREATE TABLE IF NOT EXISTS agent_task_queue (
    id INTEGER PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    source_agent TEXT NOT NULL,         -- which agent created this task
    target_agent TEXT NOT NULL,         -- which agent should handle it
    priority INTEGER DEFAULT 0,         -- 0=low, 5=high
    status TEXT DEFAULT 'pending',      -- 'pending', 'processing', 'complete', 'failed'
    payload TEXT,                       -- JSON payload
    result TEXT,                        -- JSON result when complete
    error_message TEXT,                 -- error message if failed
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_task_queue_status ON agent_task_queue(status);
CREATE INDEX IF NOT EXISTS idx_agent_task_queue_target ON agent_task_queue(target_agent);
CREATE INDEX IF NOT EXISTS idx_agent_task_queue_priority ON agent_task_queue(priority DESC);
"""


def migrate_4_1_2_agent_task_queue():
    """Create agent_task_queue table for agent communication."""
    version = "4.1.2"
    if version in get_applied_migrations():
        return False
    
    with connect() as conn:
        conn.executescript(MIGRATION_4_1_2)
        conn.commit()
    
    mark_migration_applied(version, "Agent task queue for inter-agent communication")
    return True


# -------------------------
# Migration: V4.1.3 - Sync Log
# -------------------------

MIGRATION_4_1_3 = """
-- Sync log for tracking changes (Phase 4.1)
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,          -- 'meeting', 'document', 'signal', 'ticket'
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,               -- 'create', 'update', 'delete'
    device_id TEXT,                     -- which device made this change
    timestamp REAL NOT NULL,            -- Unix timestamp
    data TEXT,                          -- JSON snapshot of changed data
    synced_to TEXT DEFAULT '',          -- comma-separated device IDs that have synced
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sync_log_entity ON sync_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_timestamp ON sync_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_sync_log_device ON sync_log(device_id);

-- Device sync state (last sync timestamp per device)
CREATE TABLE IF NOT EXISTS device_sync_state (
    id INTEGER PRIMARY KEY,
    device_id TEXT UNIQUE NOT NULL,
    last_sync_timestamp REAL NOT NULL,
    pending_count INTEGER DEFAULT 0,
    sync_errors INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_sync_state_device ON device_sync_state(device_id);
"""


def migrate_4_1_3_sync_log():
    """Create sync_log and device_sync_state tables."""
    version = "4.1.3"
    if version in get_applied_migrations():
        return False
    
    with connect() as conn:
        conn.executescript(MIGRATION_4_1_3)
        conn.commit()
    
    mark_migration_applied(version, "Sync log and device sync state tables")
    return True


# -------------------------
# Migration: V4.1.4 - Meeting V2 with Sync Metadata
# -------------------------

MIGRATION_4_1_4 = """
-- Enhanced meeting table with sync metadata (Phase 4.1)
-- Adds columns to existing meeting_summaries table

-- Add sync columns if they don't exist
-- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE, 
-- so these are handled in Python with try/except
"""

MEETING_SYNC_COLUMNS = [
    ("synced_from_device", "TEXT DEFAULT 'local'"),
    ("last_modified_device", "TEXT DEFAULT 'local'"),
    ("last_modified_at", "TIMESTAMP"),
    ("sync_version", "INTEGER DEFAULT 0"),
    ("embedding_status", "TEXT DEFAULT 'pending'"),
]


def migrate_4_1_4_meeting_sync():
    """Add sync metadata columns to meeting_summaries."""
    version = "4.1.4"
    if version in get_applied_migrations():
        return False
    
    with connect() as conn:
        for col_name, col_def in MEETING_SYNC_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE meeting_summaries ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        # Create indexes for sync queries
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_meeting_sync_device ON meeting_summaries(synced_from_device)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_meeting_sync_status ON meeting_summaries(embedding_status)")
        except Exception:
            pass  # Indexes may already exist
        
        conn.commit()
    
    mark_migration_applied(version, "Added sync metadata to meeting_summaries")
    return True


# -------------------------
# Migration: V4.1.5 - Document/Ticket Sync Metadata
# -------------------------

DOC_SYNC_COLUMNS = [
    ("synced_from_device", "TEXT DEFAULT 'local'"),
    ("last_modified_device", "TEXT DEFAULT 'local'"),
    ("last_modified_at", "TIMESTAMP"),
    ("sync_version", "INTEGER DEFAULT 0"),
]

TICKET_SYNC_COLUMNS = [
    ("synced_from_device", "TEXT DEFAULT 'local'"),
    ("last_modified_device", "TEXT DEFAULT 'local'"),
    ("sync_version", "INTEGER DEFAULT 0"),
]


def migrate_4_1_5_doc_ticket_sync():
    """Add sync metadata columns to docs and tickets."""
    version = "4.1.5"
    if version in get_applied_migrations():
        return False
    
    with connect() as conn:
        # Add columns to docs
        for col_name, col_def in DOC_SYNC_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE docs ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass
        
        # Add columns to tickets
        for col_name, col_def in TICKET_SYNC_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass
        
        conn.commit()
    
    mark_migration_applied(version, "Added sync metadata to docs and tickets")
    return True


# -------------------------
# Run All Migrations
# -------------------------

def run_all_migrations() -> dict:
    """
    Run all pending migrations in order.
    
    Returns dict with migration results.
    """
    results = {
        "4.1.1_device_registry": migrate_4_1_1_device_registry(),
        "4.1.2_agent_task_queue": migrate_4_1_2_agent_task_queue(),
        "4.1.3_sync_log": migrate_4_1_3_sync_log(),
        "4.1.4_meeting_sync": migrate_4_1_4_meeting_sync(),
        "4.1.5_doc_ticket_sync": migrate_4_1_5_doc_ticket_sync(),
    }
    
    applied = sum(1 for v in results.values() if v)
    skipped = sum(1 for v in results.values() if not v)
    
    return {
        "migrations": results,
        "applied": applied,
        "skipped": skipped,
        "total": len(results),
    }


def get_migration_status() -> dict:
    """Get current migration status."""
    applied = get_applied_migrations()
    all_migrations = ["4.1.1", "4.1.2", "4.1.3", "4.1.4", "4.1.5"]
    
    return {
        "applied": list(applied),
        "pending": [m for m in all_migrations if m not in applied],
        "total": len(all_migrations),
        "applied_count": len(applied),
    }
