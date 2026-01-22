#!/usr/bin/env python3
"""Check SQLite data and Supabase mappings for migration."""

import sqlite3
import os
import sys
from pathlib import Path
from collections import Counter

# Add project root
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


def main():
    print("=" * 60)
    print("Data Migration Status Check")
    print("=" * 60)
    
    # SQLite data
    conn = sqlite3.connect(str(project_root / 'agent.db'))
    conn.row_factory = sqlite3.Row
    
    print("\n📊 SQLite Data Counts:")
    tables = [
        ('docs', 'Documents'),
        ('meeting_summaries', 'Meetings'),
        ('tickets', 'Tickets'),
        ('embeddings', 'Embeddings'),
        ('career_profile', 'Career Profile'),
        ('career_suggestions', 'Career Suggestions'),
        ('career_memories', 'Career Memories'),
        ('skill_tracker', 'Skills'),
        ('standup_updates', 'Standups'),
        ('dikw_items', 'DIKW Items'),
    ]
    
    for table, name in tables:
        try:
            count = conn.execute(f'SELECT COUNT(*) as c FROM {table}').fetchone()['c']
            print(f"   {name}: {count}")
        except Exception as e:
            print(f"   {name}: ERROR - {e}")
    
    # Embedding breakdown
    print("\n📊 SQLite Embeddings by Type:")
    embeddings = conn.execute('SELECT ref_type, ref_id FROM embeddings').fetchall()
    by_type = Counter(e['ref_type'] for e in embeddings)
    for t, count in by_type.items():
        print(f"   {t}: {count}")
    
    # Check Supabase
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    if url and key:
        from supabase import create_client
        sb = create_client(url, key)
        
        print("\n📊 Supabase Data Counts:")
        sb_tables = [
            ('documents', 'Documents'),
            ('meetings', 'Meetings'),
            ('tickets', 'Tickets'),
            ('embeddings', 'Embeddings'),
            ('career_profiles', 'Career Profiles'),
            ('career_suggestions', 'Career Suggestions'),
            ('career_memories', 'Career Memories'),
            ('skill_tracker', 'Skills'),
            ('standup_updates', 'Standups'),
            ('dikw_items', 'DIKW Items'),
        ]
        
        for table, name in sb_tables:
            try:
                result = sb.table(table).select('id', count='exact').execute()
                print(f"   {name}: {result.count}")
            except Exception as e:
                print(f"   {name}: ERROR - {e}")
        
        # Check mappings
        print("\n🔗 Checking ID Mappings:")
        
        # Meetings
        sb_meetings = sb.table('meetings').select('id, meeting_name').execute()
        sb_meeting_names = {m['meeting_name'] for m in sb_meetings.data}
        sqlite_meeting_names = {r['meeting_name'] for r in conn.execute('SELECT meeting_name FROM meeting_summaries').fetchall()}
        matched = len(sb_meeting_names & sqlite_meeting_names)
        print(f"   Meetings matched by name: {matched}/{len(sqlite_meeting_names)}")
        
        # Documents  
        sb_docs = sb.table('documents').select('id, source').execute()
        sb_doc_sources = {d['source'] for d in sb_docs.data}
        sqlite_doc_sources = {r['source'] for r in conn.execute('SELECT source FROM docs').fetchall()}
        matched = len(sb_doc_sources & sqlite_doc_sources)
        print(f"   Documents matched by source: {matched}/{len(sqlite_doc_sources)}")
        
        # Tickets
        sb_tickets = sb.table('tickets').select('id, ticket_id').execute()
        sb_ticket_ids = {t['ticket_id'] for t in sb_tickets.data}
        sqlite_ticket_ids = {r['ticket_id'] for r in conn.execute('SELECT ticket_id FROM tickets').fetchall()}
        matched = len(sb_ticket_ids & sqlite_ticket_ids)
        print(f"   Tickets matched by ticket_id: {matched}/{len(sqlite_ticket_ids)}")
    
    conn.close()


if __name__ == "__main__":
    main()
