#!/usr/bin/env python3
"""Check 1/26 meetings and documents."""
import sys
sys.path.insert(0, '/Users/rowan/v0agent')
from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()

# Check all 1/26 meetings
print("=== 1/26 MEETINGS ===")
meetings = client.table('meetings').select('id, meeting_name').gte('meeting_date', '2026-01-26').lt('meeting_date', '2026-01-27').execute()

for m in meetings.data:
    print(f"\n{m['meeting_name'][:45]}")
    print(f"  ID: {m['id']}")
    
    # Get linked docs
    docs = client.table('documents').select('source').eq('meeting_id', m['id']).execute()
    if docs.data:
        for d in docs.data:
            print(f"  📄 {d['source'][:50]}")
    else:
        print(f"  ❌ No documents")

# Check all 1/26 documents
print("\n\n=== ALL 1/26 DOCUMENTS ===")
docs = client.table('documents').select('id, source, meeting_id').gte('document_date', '2026-01-26').lt('document_date', '2026-01-27').execute()
for d in docs.data:
    linked = "LINKED" if d.get('meeting_id') else "NOT LINKED"
    print(f"  {d['source'][:45]} [{linked}]")
