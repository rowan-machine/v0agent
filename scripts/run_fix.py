#!/usr/bin/env python3
"""Simple script to fix document-meeting mismatches."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from collections import defaultdict

def main():
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    
    print("Fetching data from Supabase...")
    meetings = supabase.table("meetings").select("id, meeting_name, meeting_date").execute().data
    documents = supabase.table("documents").select("id, source, document_date, meeting_id").execute().data
    
    print(f"  Meetings: {len(meetings)}")
    print(f"  Documents: {len(documents)}")
    
    meeting_map = {m["id"]: m for m in meetings}
    meetings_by_name = defaultdict(list)
    for m in meetings:
        name = m.get("meeting_name", "").strip()
        meetings_by_name[name].append(m)
    
    print("\n" + "=" * 80)
    print("DOCUMENT-MEETING DATE MISMATCHES")
    print("=" * 80)
    
    mismatches = []
    for doc in documents:
        if not doc.get("meeting_id"):
            continue
        meeting = meeting_map.get(doc["meeting_id"])
        if not meeting:
            continue
        m_date = (meeting.get("meeting_date") or "")[:10]
        d_date = (doc.get("document_date") or "")[:10]
        if m_date and d_date and m_date != d_date:
            mismatches.append({
                "doc_id": doc["id"],
                "doc_source": doc.get("source", "unknown"),
                "doc_date": d_date,
                "current_meeting_id": doc["meeting_id"],
                "meeting_name": meeting.get("meeting_name", "Unknown"),
                "meeting_date": m_date,
            })
    
    if not mismatches:
        print("No mismatches found!")
        return
    
    by_meeting = defaultdict(list)
    for m in mismatches:
        key = (m["meeting_name"], m["meeting_date"])
        by_meeting[key].append(m)
    
    print(f"\nFound {len(mismatches)} mismatched documents across {len(by_meeting)} meetings:\n")
    
    for (name, date), items in sorted(by_meeting.items()):
        print(f"Meeting: '{name}' ({date})")
        for item in items:
            print(f"  Doc {item['doc_id'][:8]}... ({item['doc_source']}) dated {item['doc_date']}")
        print()
    
    print("\n" + "=" * 80)
    print("FIXING MISMATCHES")
    print("=" * 80)
    
    fixed = 0
    orphaned = []
    
    for mismatch in mismatches:
        doc_date = mismatch["doc_date"]
        meeting_name = mismatch["meeting_name"]
        correct_meeting = None
        for m in meetings_by_name.get(meeting_name, []):
            m_date = (m.get("meeting_date") or "")[:10]
            if m_date == doc_date:
                correct_meeting = m
                break
        
        if correct_meeting:
            print(f"Updating doc {mismatch['doc_id'][:8]}... ({mismatch['doc_source']}, {doc_date})")
            print(f"  FROM: Meeting '{meeting_name}' ({mismatch['meeting_date']})")
            print(f"  TO:   Meeting '{meeting_name}' ({doc_date})")
            supabase.table("documents").update({"meeting_id": correct_meeting["id"]}).eq("id", mismatch["doc_id"]).execute()
            fixed += 1
        else:
            orphaned.append(mismatch)
            print(f"NO MATCH: Doc {mismatch['doc_id'][:8]}... ({doc_date}) - no meeting '{meeting_name}' on that date")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Fixed: {fixed} document links")
    print(f"Orphaned (no matching meeting): {len(orphaned)}")
    
    if orphaned:
        print("\nOrphaned documents need manual review:")
        for o in orphaned:
            print(f"  - Doc {o['doc_id'][:8]}... dated {o['doc_date']} (currently linked to '{o['meeting_name']}' on {o['meeting_date']})")

if __name__ == "__main__":
    main()
