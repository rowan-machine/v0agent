#!/usr/bin/env python3
"""
Fix meeting dates based on their document dates.

Problem: Many meetings all have date 2026-01-26 (today) but their documents have the actual meeting dates.
Solution: Update meeting dates to match the earliest document date for that meeting.
"""
import sys
sys.path.insert(0, 'src')
from app.infrastructure.supabase_client import get_supabase_client
import json
from collections import defaultdict

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
            'date': m['meeting_date'],
            'raw': m
        }
    
    # Get all documents
    documents = client.table('documents').select('id, meeting_id, source, document_date').execute()
    
    # Group documents by meeting
    meeting_docs = defaultdict(list)
    for doc in documents.data:
        if doc['meeting_id'] and doc['document_date']:
            meeting_docs[doc['meeting_id']].append(doc)
    
    # Strategy: For each meeting with multiple documents having different dates,
    # we need to either:
    # 1. Update the meeting date to match its documents (if all docs have same date)
    # 2. Create new meetings for docs with different dates (if docs have different dates)
    
    updates_needed = []
    splits_needed = []
    
    for meeting_id, docs in meeting_docs.items():
        meeting = meeting_map.get(meeting_id)
        if not meeting:
            continue
        
        # Get unique document dates
        doc_dates = set(d['document_date'][:10] for d in docs if d['document_date'])
        meeting_date = meeting['date'][:10] if meeting['date'] else None
        
        if len(doc_dates) == 1:
            # All docs have the same date - just update meeting date
            doc_date = list(doc_dates)[0]
            if doc_date != meeting_date:
                updates_needed.append({
                    'meeting_id': meeting_id,
                    'meeting_name': meeting['name'],
                    'old_date': meeting_date,
                    'new_date': doc_date,
                    'docs': docs
                })
        elif len(doc_dates) > 1:
            # Multiple dates - need to split
            splits_needed.append({
                'meeting_id': meeting_id,
                'meeting_name': meeting['name'],
                'meeting_date': meeting_date,
                'doc_dates': doc_dates,
                'docs': docs
            })
    
    # Apply updates (simple date changes)
    print(f"\n=== UPDATING {len(updates_needed)} MEETING DATES ===")
    for update in updates_needed:
        print(f"\n  {update['meeting_name'][:50]}")
        print(f"    {update['old_date']} → {update['new_date']}")
        
        # Update the meeting date
        client.table('meetings').update({
            'meeting_date': f"{update['new_date']}T00:00:00+00:00"
        }).eq('id', update['meeting_id']).execute()
        print(f"    ✅ Updated!")
    
    # Handle splits - need to find or create meetings for mismatched docs
    print(f"\n\n=== HANDLING {len(splits_needed)} MEETINGS WITH MULTIPLE DOC DATES ===")
    for split in splits_needed:
        print(f"\n  {split['meeting_name'][:50]} (meeting date: {split['meeting_date']})")
        print(f"    Doc dates: {split['doc_dates']}")
        
        # Find the primary date (most documents OR same as meeting date)
        date_counts = defaultdict(list)
        for doc in split['docs']:
            doc_date = doc['document_date'][:10]
            date_counts[doc_date].append(doc)
        
        # The meeting keeps its current date if it matches any docs, otherwise use most common
        if split['meeting_date'] in date_counts:
            primary_date = split['meeting_date']
        else:
            # Use the date with most documents
            primary_date = max(date_counts.keys(), key=lambda d: len(date_counts[d]))
        
        print(f"    Primary date for this meeting: {primary_date}")
        
        # Update meeting to primary date if different
        if primary_date != split['meeting_date']:
            client.table('meetings').update({
                'meeting_date': f"{primary_date}T00:00:00+00:00"
            }).eq('id', split['meeting_id']).execute()
            print(f"    ✅ Updated meeting date to {primary_date}")
        
        # For documents with different dates, find or create target meetings
        for doc_date, docs in date_counts.items():
            if doc_date == primary_date:
                print(f"    Docs for {doc_date}: staying with this meeting ({len(docs)} docs)")
                continue
            
            # Need to find a meeting with this name and date
            existing = client.table('meetings').select('id, meeting_name, meeting_date').ilike('meeting_name', f'%{split["meeting_name"]}%').execute()
            
            target_meeting_id = None
            for m in existing.data:
                m_name = m['meeting_name']
                if m_name.startswith('{'):
                    try:
                        parsed = json.loads(m_name)
                        m_name = parsed.get('meeting_name', m_name)
                    except:
                        pass
                m_date = m['meeting_date'][:10] if m['meeting_date'] else None
                if m_name == split['meeting_name'] and m_date == doc_date:
                    target_meeting_id = m['id']
                    break
            
            if target_meeting_id:
                print(f"    Docs for {doc_date}: moving to existing meeting {target_meeting_id[:8]}... ({len(docs)} docs)")
            else:
                # Create new meeting
                new_meeting = client.table('meetings').insert({
                    'meeting_name': split['meeting_name'],
                    'meeting_date': f"{doc_date}T00:00:00+00:00",
                    'synthesized_notes': '',
                }).execute()
                target_meeting_id = new_meeting.data[0]['id']
                print(f"    Docs for {doc_date}: created new meeting {target_meeting_id[:8]}... ({len(docs)} docs)")
            
            # Move docs to target meeting
            for doc in docs:
                client.table('documents').update({
                    'meeting_id': target_meeting_id
                }).eq('id', doc['id']).execute()
            print(f"      ✅ Moved {len(docs)} documents")
    
    print("\n\n✅ Done!")

if __name__ == '__main__':
    main()
