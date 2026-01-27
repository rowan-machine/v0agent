#!/usr/bin/env python3
"""
Check for documents that have a date mismatch with their linked meeting.
"""
import sys
sys.path.insert(0, 'src')
from app.infrastructure.supabase_client import get_supabase_client
import json

def main():
    client = get_supabase_client()
    
    # Get all meetings
    meetings = client.table('meetings').select('id, meeting_name, meeting_date').execute()
    meeting_map = {}
    for m in meetings.data:
        name = m['meeting_name']
        if name.startswith('{'):
            try:
                parsed = json.loads(name)
                name = parsed.get('meeting_name', name)
            except:
                pass
        meeting_map[m['id']] = {
            'name': name,
            'date': m['meeting_date'][:10] if m['meeting_date'] else None
        }
    
    # Get all documents
    documents = client.table('documents').select('id, meeting_id, source, document_date').execute()
    
    mismatches = []
    for doc in documents.data:
        if not doc['meeting_id']:
            continue
        
        doc_date = doc['document_date'][:10] if doc['document_date'] else None
        meeting = meeting_map.get(doc['meeting_id'])
        
        if not meeting:
            continue
        
        meeting_date = meeting['date']
        
        if doc_date and meeting_date and doc_date != meeting_date:
            mismatches.append({
                'doc_id': doc['id'],
                'doc_source': doc['source'],
                'doc_date': doc_date,
                'meeting_id': doc['meeting_id'],
                'meeting_name': meeting['name'],
                'meeting_date': meeting_date,
            })
    
    if mismatches:
        print(f"Found {len(mismatches)} date mismatches:")
        for m in mismatches:
            print(f"\n  Doc: {m['doc_source'][:50]}")
            print(f"    Doc date: {m['doc_date']} vs Meeting date: {m['meeting_date']}")
            print(f"    Meeting: {m['meeting_name'][:40]}")
            print(f"    Doc ID: {m['doc_id'][:8]}... Meeting ID: {m['meeting_id'][:8]}...")
    else:
        print("✅ No date mismatches found - all documents match their meeting dates!")
    
    # Also check for meetings with multiple documents
    print("\n\n=== MEETINGS WITH MULTIPLE DOCUMENTS ===")
    meeting_docs = {}
    for doc in documents.data:
        if doc['meeting_id']:
            if doc['meeting_id'] not in meeting_docs:
                meeting_docs[doc['meeting_id']] = []
            meeting_docs[doc['meeting_id']].append(doc)
    
    for meeting_id, docs in meeting_docs.items():
        if len(docs) > 1:
            meeting = meeting_map.get(meeting_id, {})
            print(f"\n{meeting.get('name', 'Unknown')[:50]} ({meeting.get('date', 'N/A')}):")
            print(f"  Meeting ID: {meeting_id[:8]}...")
            for d in docs:
                doc_date = d['document_date'][:10] if d['document_date'] else 'N/A'
                print(f"  - {d['source'][:50]} (date: {doc_date})")

if __name__ == '__main__':
    main()
