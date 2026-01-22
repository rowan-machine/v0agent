#!/usr/bin/env python3
"""
Quick embedding migration script - SQLite to Supabase pgvector.
Maps SQLite integer IDs to Supabase UUIDs via content matching.
"""

import sqlite3
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


def main():
    print("=" * 60)
    print("Embedding Migration: SQLite → Supabase pgvector")
    print("=" * 60)
    
    # Get Supabase credentials
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_KEY")
        sys.exit(1)
    
    print(f"📡 Supabase URL: {url}")
    
    from supabase import create_client
    sb = create_client(url, key)
    
    # Get existing Supabase data for ID mapping
    print("\n🔗 Creating ID mappings...")
    
    meetings_result = sb.table('meetings').select('id, meeting_name').execute()
    supabase_meetings = {m['meeting_name']: m['id'] for m in meetings_result.data}
    print(f"   Supabase meetings: {len(supabase_meetings)}")
    
    docs_result = sb.table('documents').select('id, source').execute()
    supabase_docs = {d['source']: d['id'] for d in docs_result.data}
    print(f"   Supabase documents: {len(supabase_docs)}")
    
    tickets_result = sb.table('tickets').select('id, ticket_id').execute()
    supabase_tickets = {t['ticket_id']: t['id'] for t in tickets_result.data}
    print(f"   Supabase tickets: {len(supabase_tickets)}")
    
    # Connect to SQLite
    db_path = project_root / "agent.db"
    if not db_path.exists():
        print(f"❌ SQLite database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Create SQLite → Supabase mappings
    meeting_map = {}
    for row in conn.execute('SELECT id, meeting_name FROM meeting_summaries').fetchall():
        if row['meeting_name'] in supabase_meetings:
            meeting_map[row['id']] = supabase_meetings[row['meeting_name']]
    print(f"   Meeting mappings: {len(meeting_map)}")
    
    doc_map = {}
    for row in conn.execute('SELECT id, source FROM docs').fetchall():
        if row['source'] in supabase_docs:
            doc_map[row['id']] = supabase_docs[row['source']]
    print(f"   Document mappings: {len(doc_map)}")
    
    ticket_map = {}
    for row in conn.execute('SELECT id, ticket_id FROM tickets').fetchall():
        if row['ticket_id'] in supabase_tickets:
            ticket_map[row['id']] = supabase_tickets[row['ticket_id']]
    print(f"   Ticket mappings: {len(ticket_map)}")
    
    # Get embeddings from SQLite
    print("\n📊 Fetching embeddings from SQLite...")
    embeddings = conn.execute('''
        SELECT id, ref_type, ref_id, model, vector 
        FROM embeddings
    ''').fetchall()
    print(f"   Found {len(embeddings)} embeddings")
    
    if not embeddings:
        print("✅ No embeddings to migrate")
        return
    
    # Migrate embeddings
    print("\n🚀 Migrating embeddings...")
    
    stats = {
        'migrated': 0,
        'skipped_no_mapping': 0,
        'skipped_duplicate': 0,
        'errors': 0,
    }
    
    batch = []
    
    for emb in embeddings:
        ref_type = emb['ref_type']
        ref_id = emb['ref_id']
        
        # Map ref_id to Supabase UUID
        supabase_ref_id = None
        supabase_ref_type = ref_type
        
        if ref_type == 'meeting':
            supabase_ref_id = meeting_map.get(ref_id)
        elif ref_type == 'doc':
            supabase_ref_id = doc_map.get(ref_id)
            supabase_ref_type = 'document'
        elif ref_type == 'ticket':
            supabase_ref_id = ticket_map.get(ref_id)
        
        if not supabase_ref_id:
            stats['skipped_no_mapping'] += 1
            continue
        
        # Parse vector
        vector = json.loads(emb['vector'])
        
        batch.append({
            'ref_type': supabase_ref_type,
            'ref_id': supabase_ref_id,
            'model': emb['model'],
            'embedding': vector,
        })
        
        # Insert in batches of 20
        if len(batch) >= 20:
            try:
                sb.table('embeddings').insert(batch).execute()
                stats['migrated'] += len(batch)
                print(f"   ✅ Migrated {stats['migrated']} embeddings...")
            except Exception as e:
                if 'duplicate' in str(e).lower():
                    stats['skipped_duplicate'] += len(batch)
                else:
                    stats['errors'] += len(batch)
                    print(f"   ❌ Batch error: {e}")
            batch = []
    
    # Insert remaining
    if batch:
        try:
            sb.table('embeddings').insert(batch).execute()
            stats['migrated'] += len(batch)
        except Exception as e:
            if 'duplicate' in str(e).lower():
                stats['skipped_duplicate'] += len(batch)
            else:
                stats['errors'] += len(batch)
                print(f"   ❌ Final batch error: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Migration Summary")
    print("=" * 60)
    print(f"   Total embeddings: {len(embeddings)}")
    print(f"   ✅ Migrated: {stats['migrated']}")
    print(f"   ⚠️ Skipped (no mapping): {stats['skipped_no_mapping']}")
    print(f"   ⚠️ Skipped (duplicate): {stats['skipped_duplicate']}")
    print(f"   ❌ Errors: {stats['errors']}")
    print("=" * 60)
    
    conn.close()


if __name__ == "__main__":
    main()
