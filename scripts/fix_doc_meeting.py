#!/usr/bin/env python3
"""
Fix document-meeting relationships.
Finds documents where the document_date doesn't match the meeting_date
and helps you reassign them.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()

# Fetch all meetings with their dates
meetings_resp = client.table('meetings').select('id, meeting_name, meeting_date').execute()
meetings_by_id = {m['id']: m for m in meetings_resp.data}
meetings_by_date_name = {}
for m in meetings_resp.data:
    date = str(m.get('meeting_date', ''))[:10]
    name = m.get('meeting_name', '')
    key = f"{date}|{name}"
    meetings_by_date_name[key] = m

# Fetch all documents
docs_resp = client.table('documents').select('id, source, document_date, meeting_id').execute()

print("=== DOCUMENT-MEETING MISMATCHES ===\n")
mismatches = []

for doc in docs_resp.data:
    doc_date = str(doc.get('document_date', ''))[:10]
    doc_source = doc.get('source', '')
    meeting_id = doc.get('meeting_id')
    
    if not meeting_id:
        continue
    
    meeting = meetings_by_id.get(meeting_id)
    if not meeting:
        print(f"❌ Doc {doc['id'][:8]} has invalid meeting_id")
        continue
        
    meeting_date = str(meeting.get('meeting_date', ''))[:10]
    meeting_name = meeting.get('meeting_name', '')
    
    # Check if document date matches meeting date
    if doc_date and meeting_date and doc_date != meeting_date:
        mismatches.append({
            'doc_id': doc['id'],
            'doc_date': doc_date,
            'doc_source': doc_source,
            'meeting_id': meeting_id,
            'meeting_date': meeting_date,
            'meeting_name': meeting_name
        })
        print(f"⚠️  MISMATCH: Doc dated {doc_date} linked to meeting dated {meeting_date}")
        print(f"   Doc: {doc_source[:60]}")
        print(f"   Meeting: {meeting_name}")
        
        # Suggest correct meeting
        for m in meetings_resp.data:
            m_date = str(m.get('meeting_date', ''))[:10]
            if m_date == doc_date:
                print(f"   💡 Suggested meeting: {m['meeting_name']} ({m['id'][:8]})")
        print()

if not mismatches:
    print("✅ All document dates match their meeting dates!")
else:
    print(f"\n=== Found {len(mismatches)} mismatches ===\n")
    
    # Interactive fixing
    print("Would you like to fix these? Enter doc_id meeting_id to fix, or 'q' to quit:")
    print("Example: abc12345 xyz67890")
    
    while True:
        user_input = input("> ").strip()
        if user_input.lower() == 'q':
            break
        parts = user_input.split()
        if len(parts) != 2:
            print("Enter: doc_id_prefix meeting_id_prefix")
            continue
        doc_prefix, meeting_prefix = parts
        
        # Find matching doc and meeting
        doc = next((d for d in docs_resp.data if d['id'].startswith(doc_prefix)), None)
        meeting = next((m for m in meetings_resp.data if m['id'].startswith(meeting_prefix)), None)
        
        if not doc:
            print(f"No doc found starting with {doc_prefix}")
            continue
        if not meeting:
            print(f"No meeting found starting with {meeting_prefix}")
            continue
        
        print(f"Update doc '{doc['source'][:40]}...' to meeting '{meeting['meeting_name']}'? (y/n)")
        confirm = input().strip().lower()
        if confirm == 'y':
            client.table('documents').update({'meeting_id': meeting['id']}).eq('id', doc['id']).execute()
            print("✅ Updated!")
        else:
            print("Skipped.")
