#!/usr/bin/env python3
"""
One-off fix: Reassign Rx Backlog Grooming documents to correct meetings based on date.

Problem: 3 transcripts from 1/6, 1/13, 1/20 are all linked to the same meeting
Solution: 
1. Find meetings without documents and assign them correct dates
2. Reassign documents to meetings with matching dates
"""
import sys
sys.path.insert(0, 'src')
from app.infrastructure.supabase_client import get_supabase_client
import json

def main():
    client = get_supabase_client()
    
    # Get all Rx Backlog Grooming meetings
    all_meetings = client.table('meetings').select('id, meeting_name, meeting_date, created_at').execute()
    
    rx_meetings = []
    for m in all_meetings.data:
        name = m['meeting_name']
        if name.startswith('{'):
            try:
                parsed = json.loads(name)
                name = parsed.get('meeting_name', name)
            except:
                pass
        if name == 'Rx Backlog Grooming':
            rx_meetings.append({**m, 'clean_name': name})
    
    print(f"Found {len(rx_meetings)} Rx Backlog Grooming meetings")
    
    # Get documents for all meetings
    meetings_with_docs = []
    meetings_without_docs = []
    
    for m in rx_meetings:
        docs = client.table('documents').select('id, source, document_date').eq('meeting_id', m['id']).execute()
        m['docs'] = docs.data
        if docs.data:
            meetings_with_docs.append(m)
        else:
            meetings_without_docs.append(m)
    
    print(f"\nMeetings with docs: {len(meetings_with_docs)}")
    print(f"Meetings without docs: {len(meetings_without_docs)}")
    
    # Get the meeting with all 3 documents
    if meetings_with_docs:
        source_meeting = meetings_with_docs[0]
        docs = source_meeting['docs']
        
        print(f"\nSource meeting {source_meeting['id']} has {len(docs)} documents:")
        for d in docs:
            print(f"  - Doc {d['id']}: date={d['document_date'][:10] if d['document_date'] else 'N/A'}")
        
        # We need to assign each document to a meeting with matching date
        # First, update the empty meetings to have the correct dates
        doc_dates = [d['document_date'][:10] if d['document_date'] else None for d in docs]
        
        # Create a mapping: doc_date -> meeting_id
        date_to_meeting = {}
        
        # The source meeting already has date 2026-01-06
        source_date = source_meeting['meeting_date'][:10] if source_meeting['meeting_date'] else None
        if source_date:
            date_to_meeting[source_date] = source_meeting['id']
        
        # Assign remaining dates to empty meetings
        remaining_dates = [d for d in doc_dates if d and d not in date_to_meeting]
        print(f"\nDates needing meetings: {remaining_dates}")
        
        for i, date in enumerate(remaining_dates):
            if i < len(meetings_without_docs):
                meeting = meetings_without_docs[i]
                print(f"  Assigning date {date} to meeting {meeting['id']}")
                # Update the meeting's date
                client.table('meetings').update({'meeting_date': f'{date}T00:00:00+00:00'}).eq('id', meeting['id']).execute()
                date_to_meeting[date] = meeting['id']
        
        # Now reassign documents to the correct meetings
        print("\nReassigning documents:")
        for d in docs:
            doc_date = d['document_date'][:10] if d['document_date'] else None
            if doc_date and doc_date in date_to_meeting:
                target_meeting = date_to_meeting[doc_date]
                current_meeting = source_meeting['id']
                if target_meeting != current_meeting:
                    print(f"  Moving doc {d['id']} ({doc_date}) from {current_meeting[:8]}... to {target_meeting[:8]}...")
                    client.table('documents').update({'meeting_id': target_meeting}).eq('id', d['id']).execute()
                else:
                    print(f"  Doc {d['id']} ({doc_date}) already correct")
    
    print("\n✅ Done!")

if __name__ == '__main__':
    main()
