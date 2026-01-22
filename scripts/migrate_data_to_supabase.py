#!/usr/bin/env python3
"""
SQLite to Supabase Data Migration Script
Migrates all data from SQLite (agent.db) to Supabase PostgreSQL.

Audit Results (tables with data):
- accountability_items: 7
- ai_memory: 7
- conversations: 7
- messages: 32
- dikw_items: 37
- tickets: 6
- docs: 16
- meeting_summaries: 14
- embeddings: 28
- career_memories: 11
- career_profile: 1
- standup_updates: 7
- skill_tracker: 37
- workflow_modes: 7
- mode_sessions: 6
- settings: 10
"""

import sqlite3
import os
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

# Add src/app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "app"))

from supabase import create_client, Client

# Configuration
SQLITE_DB_PATH = Path(__file__).parent.parent / "agent.db"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Use service role key for migration


def get_sqlite_connection() -> sqlite3.Connection:
    """Get SQLite connection with row factory."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_supabase_client() -> Client:
    """Get Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_KEY environment variables. "
            "Please set them before running the migration."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert SQLite row to dictionary."""
    return {key: row[key] for key in row.keys()}


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    supabase: Client,
    sqlite_table: str,
    supabase_table: str,
    column_mapping: Optional[Dict[str, str]] = None,
    transform_fn: Optional[callable] = None
) -> int:
    """
    Migrate data from SQLite table to Supabase table.
    
    Args:
        sqlite_conn: SQLite connection
        supabase: Supabase client
        sqlite_table: Source SQLite table name
        supabase_table: Target Supabase table name
        column_mapping: Optional mapping of SQLite columns to Supabase columns
        transform_fn: Optional function to transform each row before insert
    
    Returns:
        Number of rows migrated
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {sqlite_table}")
    rows = cursor.fetchall()
    
    if not rows:
        print(f"  ⏭️  {sqlite_table}: No data to migrate")
        return 0
    
    migrated_count = 0
    errors = []
    
    for row in rows:
        row_dict = row_to_dict(row)
        
        # Apply column mapping if provided
        if column_mapping:
            mapped_row = {}
            for sqlite_col, supabase_col in column_mapping.items():
                if sqlite_col in row_dict:
                    mapped_row[supabase_col] = row_dict[sqlite_col]
            # Include unmapped columns that exist in both
            for key, value in row_dict.items():
                if key not in column_mapping and key != 'id':
                    mapped_row[key] = value
            row_dict = mapped_row
        else:
            # Remove SQLite auto-increment id to let Supabase generate new one
            # unless we need to preserve IDs for foreign key relationships
            pass
        
        # Apply transformation if provided
        if transform_fn:
            row_dict = transform_fn(row_dict)
        
        try:
            result = supabase.table(supabase_table).upsert(row_dict).execute()
            migrated_count += 1
        except Exception as e:
            errors.append(f"Row {row_dict.get('id', 'unknown')}: {str(e)}")
    
    if errors:
        print(f"  ⚠️  {sqlite_table} → {supabase_table}: {migrated_count}/{len(rows)} migrated, {len(errors)} errors")
        for error in errors[:3]:  # Show first 3 errors
            print(f"      Error: {error}")
        if len(errors) > 3:
            print(f"      ... and {len(errors) - 3} more errors")
    else:
        print(f"  ✅ {sqlite_table} → {supabase_table}: {migrated_count} rows migrated")
    
    return migrated_count


def transform_datetime(row: Dict[str, Any]) -> Dict[str, Any]:
    """Transform SQLite datetime strings to ISO format for Supabase."""
    datetime_fields = ['created_at', 'updated_at', 'started_at', 'ended_at', 
                       'completed_at', 'promoted_at', 'archived_at']
    for field in datetime_fields:
        if field in row and row[field]:
            # SQLite datetime format: 'YYYY-MM-DD HH:MM:SS'
            # Supabase expects ISO format or 'now()'
            try:
                dt = datetime.fromisoformat(row[field].replace(' ', 'T'))
                row[field] = dt.isoformat()
            except (ValueError, AttributeError):
                pass  # Keep original if already valid
    return row


def transform_json_fields(row: Dict[str, Any], json_fields: List[str]) -> Dict[str, Any]:
    """Parse JSON string fields into actual JSON."""
    for field in json_fields:
        if field in row and row[field] and isinstance(row[field], str):
            try:
                row[field] = json.loads(row[field])
            except json.JSONDecodeError:
                pass  # Keep as string if not valid JSON
    return row


def migrate_docs(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate docs table."""
    def transform(row):
        row = transform_datetime(row)
        return row
    
    return migrate_table(sqlite_conn, supabase, "docs", "docs", transform_fn=transform)


def migrate_meeting_summaries(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate meeting_summaries table."""
    def transform(row):
        row = transform_datetime(row)
        row = transform_json_fields(row, ['signals_json'])
        return row
    
    return migrate_table(sqlite_conn, supabase, "meeting_summaries", "meeting_summaries", transform_fn=transform)


def migrate_tickets(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate tickets table."""
    def transform(row):
        row = transform_datetime(row)
        row = transform_json_fields(row, ['task_decomposition'])
        return row
    
    return migrate_table(sqlite_conn, supabase, "tickets", "tickets", transform_fn=transform)


def migrate_dikw_items(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate dikw_items table."""
    def transform(row):
        row = transform_datetime(row)
        row = transform_json_fields(row, ['source_ref_ids'])
        return row
    
    return migrate_table(sqlite_conn, supabase, "dikw_items", "dikw_items", transform_fn=transform)


def migrate_dikw_evolution(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate dikw_evolution table."""
    def transform(row):
        row = transform_datetime(row)
        row = transform_json_fields(row, ['source_item_ids'])
        return row
    
    return migrate_table(sqlite_conn, supabase, "dikw_evolution", "dikw_evolution", transform_fn=transform)


def migrate_embeddings(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate embeddings table - convert JSON vector to pgvector format."""
    def transform(row):
        row = transform_datetime(row)
        # Convert JSON array string to actual array for pgvector
        if 'vector' in row and row['vector'] and isinstance(row['vector'], str):
            try:
                row['vector'] = json.loads(row['vector'])
            except json.JSONDecodeError:
                pass
        return row
    
    return migrate_table(sqlite_conn, supabase, "embeddings", "embeddings", transform_fn=transform)


def migrate_entity_links(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate entity_links table."""
    def transform(row):
        row = transform_datetime(row)
        row = transform_json_fields(row, ['metadata'])
        return row
    
    return migrate_table(sqlite_conn, supabase, "entity_links", "entity_links", transform_fn=transform)


def migrate_signal_feedback(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate signal_feedback table."""
    return migrate_table(sqlite_conn, supabase, "signal_feedback", "signal_feedback", 
                        transform_fn=transform_datetime)


def migrate_signal_status(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate signal_status table."""
    return migrate_table(sqlite_conn, supabase, "signal_status", "signal_status", 
                        transform_fn=transform_datetime)


def migrate_ai_memory(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate ai_memory table."""
    return migrate_table(sqlite_conn, supabase, "ai_memory", "ai_memory", 
                        transform_fn=transform_datetime)


def migrate_accountability_items(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate accountability_items table."""
    return migrate_table(sqlite_conn, supabase, "accountability_items", "accountability_items", 
                        transform_fn=transform_datetime)


def migrate_workflow_modes(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate workflow_modes table."""
    def transform(row):
        row = transform_datetime(row)
        row = transform_json_fields(row, ['steps_json'])
        return row
    
    return migrate_table(sqlite_conn, supabase, "workflow_modes", "workflow_modes", transform_fn=transform)


def migrate_mode_sessions(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate mode_sessions table."""
    return migrate_table(sqlite_conn, supabase, "mode_sessions", "mode_sessions", 
                        transform_fn=transform_datetime)


def migrate_mode_statistics(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate mode_statistics table."""
    return migrate_table(sqlite_conn, supabase, "mode_statistics", "mode_statistics", 
                        transform_fn=transform_datetime)


def migrate_archived_mode_sessions(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate archived_mode_sessions table."""
    return migrate_table(sqlite_conn, supabase, "archived_mode_sessions", "archived_mode_sessions", 
                        transform_fn=transform_datetime)


def migrate_settings(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate settings table."""
    return migrate_table(sqlite_conn, supabase, "settings", "settings", 
                        transform_fn=transform_datetime)


def migrate_user_status(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate user_status table."""
    return migrate_table(sqlite_conn, supabase, "user_status", "user_status", 
                        transform_fn=transform_datetime)


def migrate_career_profile(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate career_profile table."""
    return migrate_table(sqlite_conn, supabase, "career_profile", "career_profile", 
                        transform_fn=transform_datetime)


def migrate_career_suggestions(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate career_suggestions table."""
    return migrate_table(sqlite_conn, supabase, "career_suggestions", "career_suggestions", 
                        transform_fn=transform_datetime)


def migrate_career_memories(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate career_memories table."""
    return migrate_table(sqlite_conn, supabase, "career_memories", "career_memories", 
                        transform_fn=transform_datetime)


def migrate_standup_updates(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate standup_updates table."""
    return migrate_table(sqlite_conn, supabase, "standup_updates", "standup_updates", 
                        transform_fn=transform_datetime)


def migrate_skill_tracker(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate skill_tracker table."""
    return migrate_table(sqlite_conn, supabase, "skill_tracker", "skill_tracker", 
                        transform_fn=transform_datetime)


def migrate_attachments(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate attachments table."""
    return migrate_table(sqlite_conn, supabase, "attachments", "attachments", 
                        transform_fn=transform_datetime)


def migrate_meeting_screenshots(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate meeting_screenshots table."""
    return migrate_table(sqlite_conn, supabase, "meeting_screenshots", "meeting_screenshots", 
                        transform_fn=transform_datetime)


def migrate_ticket_files(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate ticket_files table."""
    return migrate_table(sqlite_conn, supabase, "ticket_files", "ticket_files", 
                        transform_fn=transform_datetime)


def migrate_code_locker(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate code_locker table."""
    return migrate_table(sqlite_conn, supabase, "code_locker", "code_locker", 
                        transform_fn=transform_datetime)


def migrate_sprint_settings(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """Migrate sprint_settings table."""
    return migrate_table(sqlite_conn, supabase, "sprint_settings", "sprint_settings", 
                        transform_fn=transform_datetime)


def migrate_conversations_and_messages(sqlite_conn: sqlite3.Connection, supabase: Client) -> int:
    """
    Migrate conversations and messages tables.
    These may not exist in Supabase yet - we'll create them.
    """
    total = 0
    
    # Check if conversations table exists in SQLite
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
    if cursor.fetchone():
        total += migrate_table(sqlite_conn, supabase, "conversations", "conversations",
                              transform_fn=transform_datetime)
    
    # Check if messages table exists in SQLite
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    if cursor.fetchone():
        total += migrate_table(sqlite_conn, supabase, "messages", "messages",
                              transform_fn=transform_datetime)
    
    return total


def run_migration():
    """Run the complete data migration."""
    print("=" * 60)
    print("SQLite to Supabase Data Migration")
    print("=" * 60)
    print()
    
    # Verify SQLite database exists
    if not SQLITE_DB_PATH.exists():
        print(f"❌ SQLite database not found: {SQLITE_DB_PATH}")
        return False
    
    print(f"📂 Source: {SQLITE_DB_PATH}")
    print(f"☁️  Target: {SUPABASE_URL}")
    print()
    
    try:
        sqlite_conn = get_sqlite_connection()
        supabase = get_supabase_client()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    total_migrated = 0
    
    print("Starting migration...")
    print("-" * 40)
    
    # Core document tables
    print("\n📄 Documents & Meetings:")
    total_migrated += migrate_docs(sqlite_conn, supabase)
    total_migrated += migrate_meeting_summaries(sqlite_conn, supabase)
    total_migrated += migrate_meeting_screenshots(sqlite_conn, supabase)
    total_migrated += migrate_attachments(sqlite_conn, supabase)
    
    # Tickets
    print("\n🎫 Tickets:")
    total_migrated += migrate_tickets(sqlite_conn, supabase)
    total_migrated += migrate_ticket_files(sqlite_conn, supabase)
    
    # DIKW Knowledge System
    print("\n🧠 DIKW Knowledge:")
    total_migrated += migrate_dikw_items(sqlite_conn, supabase)
    total_migrated += migrate_dikw_evolution(sqlite_conn, supabase)
    total_migrated += migrate_entity_links(sqlite_conn, supabase)
    
    # Embeddings
    print("\n🔢 Embeddings:")
    total_migrated += migrate_embeddings(sqlite_conn, supabase)
    
    # Signals
    print("\n📡 Signals:")
    total_migrated += migrate_signal_feedback(sqlite_conn, supabase)
    total_migrated += migrate_signal_status(sqlite_conn, supabase)
    
    # AI Memory
    print("\n💾 AI Memory:")
    total_migrated += migrate_ai_memory(sqlite_conn, supabase)
    
    # Accountability
    print("\n✅ Accountability:")
    total_migrated += migrate_accountability_items(sqlite_conn, supabase)
    
    # Workflow & Sessions
    print("\n⚙️  Workflow:")
    total_migrated += migrate_workflow_modes(sqlite_conn, supabase)
    total_migrated += migrate_mode_sessions(sqlite_conn, supabase)
    total_migrated += migrate_mode_statistics(sqlite_conn, supabase)
    total_migrated += migrate_archived_mode_sessions(sqlite_conn, supabase)
    
    # Settings
    print("\n🔧 Settings:")
    total_migrated += migrate_settings(sqlite_conn, supabase)
    total_migrated += migrate_sprint_settings(sqlite_conn, supabase)
    total_migrated += migrate_user_status(sqlite_conn, supabase)
    
    # Career
    print("\n📈 Career:")
    total_migrated += migrate_career_profile(sqlite_conn, supabase)
    total_migrated += migrate_career_suggestions(sqlite_conn, supabase)
    total_migrated += migrate_career_memories(sqlite_conn, supabase)
    total_migrated += migrate_standup_updates(sqlite_conn, supabase)
    total_migrated += migrate_skill_tracker(sqlite_conn, supabase)
    
    # Code Locker
    print("\n🔐 Code Locker:")
    total_migrated += migrate_code_locker(sqlite_conn, supabase)
    
    # Conversations (optional)
    print("\n💬 Conversations:")
    total_migrated += migrate_conversations_and_messages(sqlite_conn, supabase)
    
    sqlite_conn.close()
    
    print()
    print("=" * 60)
    print(f"✨ Migration Complete! Total rows migrated: {total_migrated}")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
