#!/usr/bin/env python3
"""Check document-meeting relationships."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()

# Data Eng Backlog meetings
meeting_ids = {
    '1/8': '1ae18dad-9f42-4d83-a742-01650468a20c',
    '1/22': '5bcf5731-fa6b-4505-b0c4-b28f9322181a', 
    '1/26': '35a7fde1-ae23-44ba-ae7e-a92fd3ad35cc'
}

print("=== DATA ENG BACKLOG GROOMING MEETINGS ===\n")
for date, mid in meeting_ids.items():
    docs = client.table('documents').select('id, source, document_date').eq('meeting_id', mid).execute()
    print(f"{date} meeting ({mid[:8]}...):")
    if docs.data:
        for d in docs.data:
            doc_date = str(d.get('document_date', ''))[:10]
            print(f"  📄 {doc_date} | {d['source'][:50]}")
    else:
        print("  (no documents attached)")
    print()

# Quote-LinQ meetings
print("\n=== QUOTE-LINQ SPRINT PLANNING MEETINGS ===\n")
quote_meetings = client.table('meetings').select('id, meeting_name, meeting_date').ilike('meeting_name', '%Quote-LinQ%Sprint%').execute()
for m in sorted(quote_meetings.data, key=lambda x: x.get('meeting_date', '') or ''):
    mid = m['id']
    date = str(m.get('meeting_date', ''))[:10]
    docs = client.table('documents').select('id, source, document_date').eq('meeting_id', mid).execute()
    print(f"{date} meeting ({mid[:8]}...):")
    if docs.data:
        for d in docs.data:
            doc_date = str(d.get('document_date', ''))[:10]
            print(f"  📄 {doc_date} | {d['source'][:50]}")
    else:
        print("  (no documents attached)")
    print()

# ALL DOCUMENTS with their meeting info
print("\n=== ALL DOCUMENTS WITH MEETINGS ===\n")
all_docs = client.table('documents').select('id, source, document_date, meeting_id').order('document_date').execute()
for d in all_docs.data:
    doc_date = str(d.get('document_date', ''))[:10] or 'no-date'
    meeting_id = d.get('meeting_id')
    
    if meeting_id:
        # Fetch meeting name
        meeting = client.table('meetings').select('meeting_name, meeting_date').eq('id', meeting_id).single().execute()
        if meeting.data:
            m_name = meeting.data.get('meeting_name', '?')[:40]
            m_date = str(meeting.data.get('meeting_date', ''))[:10]
            print(f"📄 {doc_date} | {d['source'][:45]:<45} → 🗓️ {m_date} {m_name}")
        else:
            print(f"📄 {doc_date} | {d['source'][:45]:<45} → ❌ Invalid meeting_id")
    else:
        print(f"📄 {doc_date} | {d['source'][:45]:<45} → 🔗 NOT LINKED")
