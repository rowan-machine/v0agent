#!/usr/bin/env python
"""Populate empty Supabase meeting fields from linked documents."""
import sys
sys.path.insert(0, '/Users/rowan/v0agent')

from src.app.infrastructure.supabase_client import get_supabase_client


def populate_meeting_fields():
    """Populate raw_text and synthesized_notes from linked documents."""
    client = get_supabase_client()
    
    # Get all meetings
    meetings = client.table('meetings').select('id, meeting_name, raw_text, synthesized_notes').execute()
    
    updated_count = 0
    
    for meeting in meetings.data:
        meeting_id = meeting['id']
        meeting_name = meeting['meeting_name']
        
        # Skip if already has raw_text
        if meeting.get('raw_text'):
            continue
        
        # Get linked documents
        docs = client.table('documents').select('source, content').eq('meeting_id', meeting_id).execute()
        
        if not docs.data:
            continue
        
        # Combine content from all linked documents
        raw_parts = []
        for doc in docs.data:
            if doc.get('content'):
                source = doc.get('source', 'Document')
                raw_parts.append(f"=== {source} ===\n{doc['content']}")
        
        if not raw_parts:
            continue
        
        raw_text = "\n\n".join(raw_parts)
        
        # Update meeting with raw_text
        try:
            client.table('meetings').update({
                'raw_text': raw_text
            }).eq('id', meeting_id).execute()
            
            print(f"✅ Updated: {meeting_name[:50]} ({len(raw_text)} chars from {len(docs.data)} docs)")
            updated_count += 1
        except Exception as e:
            print(f"❌ Failed: {meeting_name[:50]} - {e}")
    
    print(f"\n🎉 Updated {updated_count} meetings with raw_text from documents")
    return updated_count


if __name__ == "__main__":
    populate_meeting_fields()
