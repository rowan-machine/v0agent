#!/usr/bin/env python3
"""
Migrate data from SQLite to Supabase for tables that were missing.

Migrates:
- code_locker (20 rows)
- workflow_modes (7 rows)
- conversation_mindmaps (4 rows)
- mindmap_syntheses (9 rows)

Usage:
    python scripts/migrate_missing_tables.py [--dry-run]
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
from uuid import uuid4

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()


def get_supabase_client():
    """Get Supabase client."""
    from src.app.infrastructure.supabase_client import get_supabase_client as _get
    return _get()


def get_sqlite_connection():
    """Get SQLite connection."""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'agent.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_code_locker(client, conn, dry_run=False):
    """Migrate code_locker table."""
    print("\n=== Migrating code_locker ===")
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM code_locker")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} rows in SQLite")
    
    if dry_run:
        print("[DRY RUN] Would migrate:")
        for row in rows[:3]:
            print(f"  - {row['filename']} (ticket: {row['ticket_id']})")
        return
    
    # Clear existing data first
    try:
        client.table('code_locker').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        print("Cleared existing code_locker data")
    except Exception as e:
        print(f"Warning: Could not clear existing data: {e}")
    
    migrated = 0
    for row in rows:
        try:
            data = {
                'ticket_id': row['ticket_id'],  # Already a UUID
                'filename': row['filename'],
                'content': row['content'],
                'version': row['version'] or 1,
                'notes': row['notes'],
                'is_initial': bool(row['is_initial']),
                'created_at': row['created_at'] or datetime.utcnow().isoformat(),
            }
            
            client.table('code_locker').insert(data).execute()
            migrated += 1
            print(f"  ✓ Migrated: {row['filename'][:60]}...")
        except Exception as e:
            print(f"  ✗ Failed: {row['filename'][:40]}... - {e}")
    
    print(f"Migrated {migrated}/{len(rows)} code_locker entries")


def migrate_workflow_modes(client, conn, dry_run=False):
    """Migrate workflow_modes table."""
    print("\n=== Migrating workflow_modes ===")
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workflow_modes")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} rows in SQLite")
    
    if dry_run:
        print("[DRY RUN] Would migrate:")
        for row in rows:
            print(f"  - {row['mode_key']}: {row['name']}")
        return
    
    # Clear existing data first
    try:
        client.table('workflow_modes').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        print("Cleared existing workflow_modes data")
    except Exception as e:
        print(f"Warning: Could not clear existing data: {e}")
    
    migrated = 0
    for row in rows:
        try:
            # Parse steps_json from SQLite
            steps = []
            steps_json = row['steps_json'] if 'steps_json' in row.keys() else None
            if steps_json:
                try:
                    steps = json.loads(steps_json)
                except:
                    pass
            
            # Access sqlite3.Row by column name
            short_desc = row['short_description'] if 'short_description' in row.keys() else None
            
            data = {
                'mode_key': row['mode_key'],
                'name': row['name'],
                'icon': row['icon'] or '🎯',
                'short_description': short_desc,
                'description': row['description'],
                'steps': steps,  # Supabase uses 'steps' not 'steps_json'
                'sort_order': row['sort_order'] or 0,
                'is_active': bool(row['is_active']),
                'created_at': row['created_at'] or datetime.utcnow().isoformat(),
                'updated_at': row['updated_at'] or datetime.utcnow().isoformat(),
            }
            
            client.table('workflow_modes').insert(data).execute()
            migrated += 1
            print(f"  ✓ Migrated: {row['mode_key']} - {row['name']}")
        except Exception as e:
            print(f"  ✗ Failed: {row['mode_key']} - {e}")
    
    print(f"Migrated {migrated}/{len(rows)} workflow_modes entries")


def migrate_conversation_mindmaps(client, conn, dry_run=False):
    """Migrate conversation_mindmaps table."""
    print("\n=== Migrating conversation_mindmaps ===")
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversation_mindmaps")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} rows in SQLite")
    
    if dry_run:
        print("[DRY RUN] Would migrate:")
        for row in rows:
            title = row['title'] if row['title'] else 'Untitled'
            print(f"  - ID {row['id']}: {title}")
        return
    
    # Clear existing data first
    try:
        client.table('conversation_mindmaps').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        print("Cleared existing conversation_mindmaps data")
    except Exception as e:
        print(f"Warning: Could not clear existing data: {e}")
    
    migrated = 0
    for row in rows:
        try:
            # Parse mindmap_json
            mindmap_json = {}
            raw_json = row['mindmap_json']
            if raw_json:
                try:
                    mindmap_json = json.loads(raw_json)
                except:
                    mindmap_json = {'raw': raw_json}
            
            # Access optional columns safely
            title = row['title'] if 'title' in row.keys() else None
            
            data = {
                'mindmap_json': mindmap_json,
                'hierarchy_levels': row['hierarchy_levels'] or 1,
                'root_node_id': row['root_node_id'],
                'node_count': row['node_count'] or 0,
                'title': title,
                'created_at': row['created_at'] or datetime.utcnow().isoformat(),
                'updated_at': row['updated_at'] or datetime.utcnow().isoformat(),
            }
            
            # Note: conversation_id would need mapping if conversations were migrated
            
            client.table('conversation_mindmaps').insert(data).execute()
            migrated += 1
            print(f"  ✓ Migrated: mindmap {row['id']}")
        except Exception as e:
            print(f"  ✗ Failed: mindmap {row['id']} - {e}")
    
    print(f"Migrated {migrated}/{len(rows)} conversation_mindmaps entries")


def migrate_mindmap_syntheses(client, conn, dry_run=False):
    """Migrate mindmap_syntheses table."""
    print("\n=== Migrating mindmap_syntheses ===")
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mindmap_syntheses")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} rows in SQLite")
    
    if dry_run:
        print("[DRY RUN] Would migrate:")
        for row in rows[:3]:
            text_preview = (row.get('synthesis_text') or '')[:50]
            print(f"  - ID {row['id']}: {text_preview}...")
        return
    
    # Clear existing data first
    try:
        client.table('mindmap_syntheses').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        print("Cleared existing mindmap_syntheses data")
    except Exception as e:
        print(f"Warning: Could not clear existing data: {e}")
    
    migrated = 0
    cols = [desc[0] for desc in cursor.description] if cursor.description else []
    
    for row in rows:
        try:
            row_dict = dict(row)
            
            data = {
                'synthesis_text': row_dict.get('synthesis_text', ''),
                'synthesis_type': row_dict.get('synthesis_type', 'summary'),
                'input_text': row_dict.get('input_text'),
                'model_used': row_dict.get('model_used', 'gpt-4o-mini'),
                'tokens_used': row_dict.get('tokens_used'),
                'created_at': row_dict.get('created_at') or datetime.utcnow().isoformat(),
                'updated_at': row_dict.get('updated_at') or datetime.utcnow().isoformat(),
            }
            
            # Add optional fields if they exist
            if row_dict.get('confidence_score'):
                data['confidence_score'] = row_dict['confidence_score']
            if row_dict.get('tags'):
                try:
                    data['tags'] = json.loads(row_dict['tags']) if isinstance(row_dict['tags'], str) else row_dict['tags']
                except:
                    pass
            if row_dict.get('metadata'):
                try:
                    data['metadata'] = json.loads(row_dict['metadata']) if isinstance(row_dict['metadata'], str) else row_dict['metadata']
                except:
                    pass
            
            client.table('mindmap_syntheses').insert(data).execute()
            migrated += 1
            print(f"  ✓ Migrated: synthesis {row_dict.get('id')}")
        except Exception as e:
            print(f"  ✗ Failed: synthesis - {e}")
    
    print(f"Migrated {migrated}/{len(rows)} mindmap_syntheses entries")


def main():
    parser = argparse.ArgumentParser(description='Migrate missing tables from SQLite to Supabase')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without making changes')
    parser.add_argument('--table', choices=['code_locker', 'workflow_modes', 'mindmaps', 'syntheses', 'all'], 
                        default='all', help='Which table to migrate')
    args = parser.parse_args()
    
    print("=" * 60)
    print("SQLite to Supabase Migration - Missing Tables")
    print("=" * 60)
    
    if args.dry_run:
        print(">>> DRY RUN MODE - No changes will be made <<<\n")
    
    # Connect to databases
    client = get_supabase_client()
    if not client:
        print("ERROR: Could not connect to Supabase. Check SUPABASE_URL and SUPABASE_KEY")
        sys.exit(1)
    
    conn = get_sqlite_connection()
    
    try:
        if args.table in ['code_locker', 'all']:
            migrate_code_locker(client, conn, args.dry_run)
        
        if args.table in ['workflow_modes', 'all']:
            migrate_workflow_modes(client, conn, args.dry_run)
        
        if args.table in ['mindmaps', 'all']:
            migrate_conversation_mindmaps(client, conn, args.dry_run)
        
        if args.table in ['syntheses', 'all']:
            migrate_mindmap_syntheses(client, conn, args.dry_run)
        
        print("\n" + "=" * 60)
        print("Migration complete!")
        print("=" * 60)
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
