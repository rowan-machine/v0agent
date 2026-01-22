#!/usr/bin/env python3
"""
Migrate embeddings from SQLite to Supabase with proper ID mapping.
"""

import sqlite3
import os
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


def main():
    print("=" * 60)
    print("Embedding Migration: SQLite → Supabase")
    print("=" * 60)
    
    # Connect to SQLite
    conn = sqlite3.connect(str(project_root / 'agent.db'))
    conn.row_factory = sqlite3.Row
    
    # Connect to Supabase
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_KEY")
        sys.exit(1)
    
    from supabase import create_client
    sb = create_client(url, key)
    
    # Build ID mappings
    print("\n📋 Building ID mappings...")
    
    # Meeting mappings (SQLite meeting_summaries.id -> Supabase meetings.id)
    sqlite_meetings = {row['id']: row['meeting_name'] 
                       for row in conn.execute('SELECT id, meeting_name FROM meeting_summaries').fetchall()}
    sb_meetings_data = sb.table('meetings').select('id, meeting_name').execute().data
    sb_meetings = {row['meeting_name']: row['id'] for row in sb_meetings_data}
    meeting_map = {sqlite_id: sb_meetings.get(name) for sqlite_id, name in sqlite_meetings.items()}
    print(f"   Meetings: {sum(1 for v in meeting_map.values() if v)} mapped")
    
    # Doc mappings (SQLite docs.id -> Supabase documents.id)
    sqlite_docs = {row['id']: row['source'] 
                   for row in conn.execute('SELECT id, source FROM docs').fetchall()}
    sb_docs_data = sb.table('documents').select('id, source').execute().data
    sb_docs = {row['source']: row['id'] for row in sb_docs_data}
    doc_map = {sqlite_id: sb_docs.get(source) for sqlite_id, source in sqlite_docs.items()}
    print(f"   Documents: {sum(1 for v in doc_map.values() if v)} mapped")
    
    # Ticket mappings (SQLite tickets.id -> Supabase tickets.id)
    sqlite_tickets = {row['id']: row['ticket_id'] 
                      for row in conn.execute('SELECT id, ticket_id FROM tickets').fetchall()}
    sb_tickets_data = sb.table('tickets').select('id, ticket_id').execute().data
    sb_tickets = {row['ticket_id']: row['id'] for row in sb_tickets_data}
    ticket_map = {sqlite_id: sb_tickets.get(tid) for sqlite_id, tid in sqlite_tickets.items()}
    print(f"   Tickets: {sum(1 for v in ticket_map.values() if v)} mapped")
    
    # Get existing embeddings to avoid duplicates
    existing_embeddings = sb.table('embeddings').select('ref_type, ref_id').execute().data
    existing_set = {(e['ref_type'], e['ref_id']) for e in existing_embeddings}
    print(f"\n📊 Existing embeddings in Supabase: {len(existing_set)}")
    
    # Get SQLite embeddings
    embeddings = conn.execute('SELECT id, ref_type, ref_id, model, vector FROM embeddings').fetchall()
    print(f"📊 Embeddings in SQLite: {len(embeddings)}")
    
    # Migrate embeddings
    print("\n🚀 Migrating embeddings...")
    migrated = 0
    skipped = 0
    errors = 0
    
    for emb in embeddings:
        ref_type = emb['ref_type']
        sqlite_ref_id = emb['ref_id']
        
        # Map the ref_type and get the Supabase UUID
        if ref_type == 'meeting':
            supabase_ref_type = 'meeting'
            supabase_ref_id = meeting_map.get(sqlite_ref_id)
        elif ref_type == 'doc':
            supabase_ref_type = 'document'
            supabase_ref_id = doc_map.get(sqlite_ref_id)
        elif ref_type == 'ticket':
            supabase_ref_type = 'ticket'
            supabase_ref_id = ticket_map.get(sqlite_ref_id)
        else:
            print(f"   ⚠️ Unknown ref_type: {ref_type}")
            errors += 1
            continue
        
        if not supabase_ref_id:
            print(f"   ⚠️ No mapping for {ref_type} {sqlite_ref_id}")
            errors += 1
            continue
        
        # Check if already exists
        if (supabase_ref_type, supabase_ref_id) in existing_set:
            skipped += 1
            continue
        
        # Parse the vector
        try:
            vector = json.loads(emb['vector'])
        except:
            print(f"   ⚠️ Failed to parse vector for {ref_type} {sqlite_ref_id}")
            errors += 1
            continue
        
        # Insert into Supabase
        try:
            result = sb.table('embeddings').insert({
                'ref_type': supabase_ref_type,
                'ref_id': supabase_ref_id,
                'model': emb['model'],
                'embedding': vector,
            }).execute()
            
            if result.data:
                migrated += 1
                existing_set.add((supabase_ref_type, supabase_ref_id))
        except Exception as e:
            print(f"   ❌ Insert failed for {ref_type} {sqlite_ref_id}: {e}")
            errors += 1
    
    print(f"\n✅ Migration complete!")
    print(f"   Migrated: {migrated}")
    print(f"   Skipped (already exists): {skipped}")
    print(f"   Errors: {errors}")
    
    # Final count
    final_count = sb.table('embeddings').select('id', count='exact').execute()
    print(f"\n📊 Total embeddings in Supabase: {final_count.count}")


if __name__ == '__main__':
    main()
