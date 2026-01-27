#!/usr/bin/env python3
"""List all meetings sorted by date with their IDs."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()

# Get all meetings sorted by date
meetings_resp = client.table('meetings').select('id, meeting_name, meeting_date').order('meeting_date').execute()

print("=== ALL MEETINGS ===\n")
for m in meetings_resp.data:
    date = str(m.get('meeting_date', ''))[:10] or 'no-date'
    name = m.get('meeting_name', 'Untitled')
    mid = m['id'][:8]
    
    # Get docs for this meeting
    docs_resp = client.table('documents').select('id, source, document_date').eq('meeting_id', m['id']).execute()
    doc_count = len(docs_resp.data)
    
    print(f"📅 {date} | {mid} | {name[:45]:<45} | 📄 {doc_count} docs")
    for d in docs_resp.data:
        doc_date = str(d.get('document_date', ''))[:10]
        print(f"    └── {doc_date} | {d['source'][:50]}")
