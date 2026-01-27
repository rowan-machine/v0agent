#!/usr/bin/env python3
"""
Migrate local uploads to Supabase Storage.

This script:
1. Reads all attachments from local SQLite database
2. Uploads each file to Supabase Storage
3. Updates the database with Supabase URLs
"""

import os
import sys

# Set database path before importing
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
os.environ['DATABASE_PATH'] = os.path.join(project_dir, 'agent.db')

# Add src to path
sys.path.insert(0, os.path.join(project_dir, 'src'))

from app.db import connect
from app.infrastructure.supabase_client import get_supabase_client


def migrate_uploads():
    """Migrate local uploads to Supabase Storage."""
    client = get_supabase_client()
    if not client:
        print("❌ Supabase client not available")
        return
    
    storage = client.storage.from_('meeting-uploads')
    base_dir = project_dir
    
    # Get all attachments that need migration
    with connect() as conn:
        attachments = conn.execute("""
            SELECT id, ref_type, ref_id, filename, file_path, mime_type, file_size
            FROM attachments
            WHERE file_path LIKE 'uploads/%'
              AND (supabase_url IS NULL OR supabase_url = '')
        """).fetchall()
    
    print(f"\n=== MIGRATING {len(attachments)} ATTACHMENTS ===\n")
    
    migrated = 0
    failed = 0
    skipped = 0
    
    for att in attachments:
        att_id = att['id']
        ref_id = att['ref_id']
        filename = att['filename']
        local_path = att['file_path']
        mime_type = att['mime_type'] or 'image/png'
        
        full_path = os.path.join(base_dir, local_path)
        
        print(f"  {filename}")
        print(f"    Local: {local_path}")
        
        if not os.path.exists(full_path):
            print(f"    ⚠️ File not found, skipping")
            skipped += 1
            continue
        
        # Check file size
        file_size = os.path.getsize(full_path)
        if file_size == 0:
            print(f"    ⚠️ Empty file, skipping")
            skipped += 1
            continue
        
        try:
            # Read file
            with open(full_path, 'rb') as f:
                content = f.read()
            
            # Generate storage path
            ext = os.path.splitext(filename)[1] or os.path.splitext(local_path)[1] or '.png'
            unique_name = os.path.basename(local_path)
            storage_path = f"meetings/{ref_id}/{unique_name}"
            
            # Upload to Supabase
            result = storage.upload(
                path=storage_path,
                file=content,
                file_options={'content-type': mime_type}
            )
            
            # Get public URL
            public_url = storage.get_public_url(storage_path)
            
            # Update database
            with connect() as conn:
                conn.execute("""
                    UPDATE attachments
                    SET supabase_url = ?, supabase_path = ?
                    WHERE id = ?
                """, (public_url, storage_path, att_id))
            
            print(f"    ✅ Migrated to: {storage_path}")
            migrated += 1
            
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            failed += 1
    
    print(f"\n=== MIGRATION COMPLETE ===")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Failed:   {failed}")
    
    # Also sync to Supabase attachments table
    if migrated > 0:
        print(f"\n=== SYNCING TO SUPABASE ATTACHMENTS TABLE ===")
        sync_attachments_to_supabase(client)


def sync_attachments_to_supabase(client):
    """Sync attachments table to Supabase."""
    with connect() as conn:
        attachments = conn.execute("""
            SELECT id, ref_type, ref_id, filename, file_path, mime_type, file_size, 
                   supabase_url, supabase_path, ai_description, tags, created_at
            FROM attachments
            WHERE supabase_url IS NOT NULL
        """).fetchall()
    
    for att in attachments:
        try:
            data = {
                'local_id': att['id'],
                'ref_type': att['ref_type'],
                'ref_id': str(att['ref_id']),
                'filename': att['filename'],
                'file_path': att['file_path'] or '',
                'mime_type': att['mime_type'],
                'file_size': att['file_size'],
                'supabase_url': att['supabase_url'],
                'supabase_path': att['supabase_path'],
                'ai_description': att['ai_description'],
                'tags': att['tags'],
            }
            
            # Upsert to Supabase
            client.table('attachments').upsert(data, on_conflict='local_id').execute()
            print(f"  ✅ Synced {att['filename']}")
        except Exception as e:
            print(f"  ❌ Failed to sync {att['filename']}: {e}")


if __name__ == "__main__":
    migrate_uploads()
