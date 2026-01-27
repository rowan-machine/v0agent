#!/usr/bin/env python3
"""Check specific meeting relationships."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.infrastructure.supabase_client import get_supabase_client
import os
# Disable app startup
os.environ["SKIP_STARTUP"] = "1"

def main():
    client = get_supabase_client()
    
    print("=== DATA ENG BACKLOG GROOMING ===")
    r = client.table('meetings').select('id, meeting_name, meeting_date').eq('meeting_name', 'Data Eng Backlog Grooming').order('meeting_date').execute()
    for m in r.data:
        date = str(m.get('meeting_date', ''))[:10]
        docs = client.table('documents').select('source, document_date').eq('meeting_id', m['id']).execute()
        print(f"\n📅 {date} ({m['id'][:8]})")
        if docs.data:
            for d in docs.data:
                doc_date = str(d.get('document_date', ''))[:10]
                print(f"   📄 {doc_date} | {d['source'][:50]}")
        else:
            print("   (no documents)")
    
    print("\n=== QUOTE-LINQ ===")
    r = client.table('meetings').select('id, meeting_name, meeting_date').ilike('meeting_name', '%Quote-LinQ%').order('meeting_date').execute()
    for m in r.data:
        date = str(m.get('meeting_date', ''))[:10]
        docs = client.table('documents').select('source, document_date').eq('meeting_id', m['id']).execute()
        print(f"\n📅 {date} ({m['id'][:8]})")
        if docs.data:
            for d in docs.data:
                doc_date = str(d.get('document_date', ''))[:10]
                print(f"   📄 {doc_date} | {d['source'][:50]}")
        else:
            print("   (no documents)")

if __name__ == "__main__":
    main()
