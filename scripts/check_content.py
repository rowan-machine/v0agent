#!/usr/bin/env python3
"""Check meeting content."""
import sys
sys.path.insert(0, '/Users/rowan/v0agent')
from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()
r = client.table('meetings').select('meeting_name, synthesized_notes, signals').limit(5).execute()

print("=== MEETING CONTENT CHECK ===\n")
for m in r.data:
    name = m.get('meeting_name', 'Unknown')
    notes = m.get('synthesized_notes') or ''
    signals = m.get('signals') or {}
    print(f"Meeting: {name[:40]}")
    print(f"  Notes: {len(notes)} chars")
    print(f"  Signals: {signals}")
    print()
