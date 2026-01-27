#!/usr/bin/env python3
"""Investigate document-meeting relationships"""
import os
import json
from pathlib import Path

# Load .env manually
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

from supabase import create_client
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

print("=" * 80)
print("MEETING DATA")
print("=" * 80)

meetings = sb.table("meetings").select("*").execute().data
print(f"Total meetings: {len(meetings)}\n")

# Parse meeting_name - some might be JSON strings
def get_meeting_name(m):
    name = m.get("meeting_name", "Untitled")
    if isinstance(name, str) and name.startswith("{"):
        try:
            parsed = json.loads(name)
            return parsed.get("meeting_name", name)
        except:
            pass
    return name

# Group by meeting name
from collections import defaultdict
by_name = defaultdict(list)
for m in meetings:
    name = get_meeting_name(m)
    by_name[name].append(m)

for name, mtgs in sorted(by_name.items()):
    print(f"\n{name}:")
    for m in sorted(mtgs, key=lambda x: x.get("meeting_date", "")):
        date = (m.get("meeting_date") or "")[:10]
        src_doc = m.get("source_document_id")
        print(f"  - {date} (id: {m['id'][:8]}..., source_doc: {src_doc})")

print("\n" + "=" * 80)
print("DOCUMENT DATA")
print("=" * 80)

docs = sb.table("documents").select("*").execute().data
print(f"Total documents: {len(docs)}\n")

for d in sorted(docs, key=lambda x: x.get("document_date", "")):
    date = (d.get("document_date") or "")[:10]
    src = d.get("source", "?")
    meeting_id = d.get("meeting_id")
    print(f"  - {date} | source: {src[:50]} | meeting_id: {meeting_id[:8] if meeting_id else 'None'}...")

# Now check the actual meeting each doc is linked to
print("\n" + "=" * 80)
print("DOCUMENT-MEETING RELATIONSHIPS")
print("=" * 80)

meeting_map = {m["id"]: m for m in meetings}

mismatches = []
for d in sorted(docs, key=lambda x: (x.get("document_date") or "")):
    d_date = (d.get("document_date") or "")[:10]
    m_id = d.get("meeting_id")
    if m_id:
        m = meeting_map.get(m_id, {})
        m_name = get_meeting_name(m)
        m_date = (m.get("meeting_date") or "")[:10]
        match = "✓" if d_date == m_date else "✗ MISMATCH"
        print(f"Doc {d_date} -> Meeting '{m_name}' {m_date} {match}")
        if d_date != m_date:
            mismatches.append({
                "doc_id": d["id"],
                "doc_date": d_date,
                "doc_source": d.get("source", "")[:50],
                "meeting_id": m_id,
                "meeting_name": m_name,
                "meeting_date": m_date
            })

print(f"\n\nFound {len(mismatches)} mismatches")
