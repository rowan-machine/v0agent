#!/usr/bin/env python3
"""
Generate SQL for embedding migration.
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
    # Connect to SQLite
    conn = sqlite3.connect(str(project_root / 'agent.db'))
    conn.row_factory = sqlite3.Row
    
    # Connect to Supabase for mapping
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    from supabase import create_client
    sb = create_client(url, key)
    
    # Build ID mappings
    sqlite_meetings = {row['id']: row['meeting_name'] 
                       for row in conn.execute('SELECT id, meeting_name FROM meeting_summaries').fetchall()}
    sb_meetings = {row['meeting_name']: row['id'] 
                   for row in sb.table('meetings').select('id, meeting_name').execute().data}
    meeting_map = {sqlite_id: sb_meetings.get(name) for sqlite_id, name in sqlite_meetings.items()}
    
    sqlite_docs = {row['id']: row['source'] 
                   for row in conn.execute('SELECT id, source FROM docs').fetchall()}
    sb_docs = {row['source']: row['id'] 
               for row in sb.table('documents').select('id, source').execute().data}
    doc_map = {sqlite_id: sb_docs.get(source) for sqlite_id, source in sqlite_docs.items()}
    
    sqlite_tickets = {row['id']: row['ticket_id'] 
                      for row in conn.execute('SELECT id, ticket_id FROM tickets').fetchall()}
    sb_tickets = {row['ticket_id']: row['id'] 
                  for row in sb.table('tickets').select('id, ticket_id').execute().data}
    ticket_map = {sqlite_id: sb_tickets.get(tid) for sqlite_id, tid in sqlite_tickets.items()}
    
    # Get existing embeddings
    existing_embeddings = sb.table('embeddings').select('ref_type, ref_id').execute().data
    existing_set = {(e['ref_type'], e['ref_id']) for e in existing_embeddings}
    
    # Get SQLite embeddings
    embeddings = conn.execute('SELECT id, ref_type, ref_id, model, vector FROM embeddings').fetchall()
    
    # Output SQL inserts
    print("-- Embedding migration SQL")
    print("-- Run this with mcp_supabase_execute_sql")
    print()
    
    for emb in embeddings:
        ref_type = emb['ref_type']
        sqlite_ref_id = emb['ref_id']
        
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
            continue
        
        if not supabase_ref_id:
            print(f"-- SKIP: No mapping for {ref_type} {sqlite_ref_id}")
            continue
        
        if (supabase_ref_type, supabase_ref_id) in existing_set:
            print(f"-- SKIP: Already exists {supabase_ref_type} {supabase_ref_id}")
            continue
        
        # Parse vector
        try:
            vector = json.loads(emb['vector'])
            vector_str = '[' + ','.join(str(v) for v in vector) + ']'
        except:
            print(f"-- ERROR: Failed to parse vector for {ref_type} {sqlite_ref_id}")
            continue
        
        print(f"-- {ref_type} {sqlite_ref_id} -> {supabase_ref_type} {supabase_ref_id}")
        print(f"INSERT INTO embeddings (ref_type, ref_id, model, embedding)")
        print(f"VALUES ('{supabase_ref_type}', '{supabase_ref_id}', '{emb['model']}', '{vector_str}'::vector);")
        print()


if __name__ == '__main__':
    main()
