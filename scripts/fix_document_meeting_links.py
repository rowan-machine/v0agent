#!/usr/bin/env python3
"""
Fix Document-Meeting Links

This script:
1. Analyzes all meetings and documents
2. Reassigns documents to the correct meeting based on matching:
   - Meeting name (extracted from document source)
   - Document date matching meeting date
3. Reports what was fixed

Run with: python scripts/fix_document_meeting_links.py
"""

import sys
import re
sys.path.insert(0, "src")

import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_meeting_name_from_source(source: str) -> str:
    """Extract meeting name from document source field."""
    # Patterns like "Transcript: Meeting Name" or "Pocket Summary (Type): Meeting Name"
    patterns = [
        r"^Transcript:\s*(.+)$",
        r"^Pocket Summary \([^)]+\):\s*(.+)$",
        r"^Summary:\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, source.strip())
        if match:
            return match.group(1).strip()
    return source.strip()


def get_clean_meeting_name(name: str) -> str:
    """Extract meeting name, handling JSON-encoded values."""
    if isinstance(name, str) and name.startswith("{"):
        try:
            parsed = json.loads(name)
            return parsed.get("meeting_name", name)
        except:
            pass
    return name


def main():
    from app.infrastructure.supabase_client import get_supabase_client
    
    client = get_supabase_client()
    if not client:
        logger.error("Could not connect to Supabase")
        return
    
    # Get all meetings
    meetings_result = client.table("meetings").select("id, meeting_name, meeting_date, created_at").execute()
    meetings = meetings_result.data or []
    
    # Get all documents
    docs_result = client.table("documents").select("id, meeting_id, source, document_date, created_at").execute()
    docs = docs_result.data or []
    
    logger.info(f"Found {len(meetings)} meetings and {len(docs)} documents")
    
    # Build meeting lookup by (name, date)
    meeting_by_name_date = {}
    meeting_by_id = {}
    
    for m in meetings:
        mid = m.get("id")
        name = get_clean_meeting_name(m.get("meeting_name", ""))
        date = m.get("meeting_date", "")[:10] if m.get("meeting_date") else ""
        
        meeting_by_id[mid] = {"name": name, "date": date}
        
        key = (name.lower().strip(), date)
        if key not in meeting_by_name_date:
            meeting_by_name_date[key] = []
        meeting_by_name_date[key].append(mid)
    
    # Analyze and fix documents
    fixes_needed = []
    already_correct = 0
    no_match = []
    
    for doc in docs:
        doc_id = doc.get("id")
        current_meeting_id = doc.get("meeting_id")
        source = doc.get("source", "")
        doc_date = doc.get("document_date", "")[:10] if doc.get("document_date") else ""
        
        # Extract meeting name from source
        doc_meeting_name = extract_meeting_name_from_source(source)
        
        # Find the correct meeting by name + date
        key = (doc_meeting_name.lower().strip(), doc_date)
        matching_meetings = meeting_by_name_date.get(key, [])
        
        if not matching_meetings:
            # Try without date
            for (name, date), mids in meeting_by_name_date.items():
                if name == doc_meeting_name.lower().strip():
                    matching_meetings = mids
                    break
        
        if matching_meetings:
            # Pick the correct meeting (should only be one with matching date)
            correct_meeting_id = matching_meetings[0]
            
            if current_meeting_id == correct_meeting_id:
                already_correct += 1
            else:
                current_meeting_info = meeting_by_id.get(current_meeting_id, {})
                correct_meeting_info = meeting_by_id.get(correct_meeting_id, {})
                
                fixes_needed.append({
                    "doc_id": doc_id,
                    "source": source[:60],
                    "doc_date": doc_date,
                    "current_meeting_id": current_meeting_id,
                    "current_meeting_name": current_meeting_info.get("name", "?"),
                    "current_meeting_date": current_meeting_info.get("date", "?"),
                    "correct_meeting_id": correct_meeting_id,
                    "correct_meeting_name": correct_meeting_info.get("name", "?"),
                    "correct_meeting_date": correct_meeting_info.get("date", "?"),
                })
        else:
            no_match.append({
                "doc_id": doc_id,
                "source": source[:60],
                "doc_date": doc_date,
                "doc_meeting_name": doc_meeting_name,
            })
    
    # Report
    print("\n" + "="*80)
    print("DOCUMENT-MEETING LINK ANALYSIS")
    print("="*80)
    
    print(f"\n✅ Already correct: {already_correct}")
    print(f"⚠️  Need fixing: {len(fixes_needed)}")
    print(f"❓ No match found: {len(no_match)}")
    
    if fixes_needed:
        print("\n--- FIXES NEEDED ---")
        for fix in fixes_needed:
            print(f"\nDocument: {fix['source']}")
            print(f"  Doc date: {fix['doc_date']}")
            print(f"  CURRENT: {fix['current_meeting_name'][:40]} ({fix['current_meeting_date']})")
            print(f"  CORRECT: {fix['correct_meeting_name'][:40]} ({fix['correct_meeting_date']})")
    
    if no_match:
        print("\n--- NO MATCH FOUND ---")
        for nm in no_match[:5]:
            print(f"  {nm['source']} (date: {nm['doc_date']}, extracted: {nm['doc_meeting_name'][:30]})")
    
    # Apply fixes
    if fixes_needed:
        print("\n" + "="*80)
        print("APPLYING FIXES...")
        print("="*80)
        
        for fix in fixes_needed:
            try:
                client.table("documents").update({
                    "meeting_id": fix["correct_meeting_id"]
                }).eq("id", fix["doc_id"]).execute()
                
                print(f"✅ Fixed: {fix['source'][:50]} -> {fix['correct_meeting_name'][:30]}")
            except Exception as e:
                print(f"❌ Failed: {fix['source'][:50]} - {e}")
        
        print(f"\nDone! Fixed {len(fixes_needed)} document links.")
    else:
        print("\n✅ All documents are correctly linked!")


if __name__ == "__main__":
    main()
