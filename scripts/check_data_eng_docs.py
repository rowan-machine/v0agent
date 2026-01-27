#!/usr/bin/env python3
"""Check document-meeting relationships for Data Eng Backlog meetings."""
import sys
sys.path.insert(0, 'src')
from app.infrastructure.supabase_client import get_supabase_client

def main():
    client = get_supabase_client()

    # 1. Find ALL meetings with 'Data Eng Backlog' in name
    print('=' * 60)
    print('MEETINGS with "Data Eng Backlog" in name:')
    print('=' * 60)
    meetings = client.table('meetings').select('id, name, meeting_date').ilike('name', '%Data Eng Backlog%').order('meeting_date', desc=True).execute()
    for m in meetings.data:
        print(f"  ID: {m['id']}")
        print(f"  Name: {m['name']}")
        print(f"  Date: {m['meeting_date']}")
        print()

    # 2. Find ALL documents with 'Data Eng Backlog' in source
    print('=' * 60)
    print('DOCUMENTS with "Data Eng Backlog" in source:')
    print('=' * 60)
    docs = client.table('documents').select('id, source, document_date, meeting_id').ilike('source', '%Data Eng Backlog%').order('document_date', desc=True).execute()
    for d in docs.data:
        print(f"  Doc ID: {d['id']}")
        print(f"  Source: {d['source']}")
        print(f"  Doc Date: {d['document_date']}")
        print(f"  Meeting ID: {d['meeting_id']}")
        print()

    # 3. Build meeting lookup for comparison
    meeting_dates = {m['id']: m['meeting_date'] for m in meetings.data}
    meeting_names = {m['id']: m['name'] for m in meetings.data}

    # 4. Find mismatches
    print('=' * 60)
    print('MISMATCHES (document_date != meeting_date):')
    print('=' * 60)
    mismatches = []
    for d in docs.data:
        meeting_id = d['meeting_id']
        if meeting_id and meeting_id in meeting_dates:
            meeting_date = meeting_dates[meeting_id]
            doc_date = d['document_date']
            if doc_date and meeting_date and doc_date != meeting_date:
                mismatches.append({
                    'doc_id': d['id'],
                    'doc_source': d['source'],
                    'doc_date': doc_date,
                    'meeting_id': meeting_id,
                    'meeting_name': meeting_names.get(meeting_id),
                    'meeting_date': meeting_date
                })
                print(f"  MISMATCH FOUND:")
                print(f"    Doc ID: {d['id']}")
                print(f"    Doc Source: {d['source']}")
                print(f"    Doc Date: {doc_date}")
                print(f"    Meeting ID: {meeting_id}")
                print(f"    Meeting Date: {meeting_date}")
                print()

    if not mismatches:
        print('  No mismatches found.')
    
    print()
    print(f'Total meetings found: {len(meetings.data)}')
    print(f'Total documents found: {len(docs.data)}')
    print(f'Total mismatches: {len(mismatches)}')

if __name__ == '__main__':
    main()
