#!/usr/bin/env python3
"""Fix meetings where meeting_name contains JSON instead of plain text."""
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()

# Get all meetings
meetings_resp = client.table('meetings').select('id, meeting_name').execute()

print("=== FIXING MEETING NAMES WITH JSON ===\n")
fixed = 0

for m in meetings_resp.data:
    name = m.get('meeting_name', '')
    if not name:
        continue
        
    # Check if name starts with '{' (JSON)
    if name.strip().startswith('{'):
        try:
            data = json.loads(name)
            actual_name = data.get('meeting_name', 'Unknown Meeting')
            print(f"🔧 Fixing: {m['id'][:8]}... '{name[:50]}' -> '{actual_name}'")
            
            # Update the meeting
            client.table('meetings').update({'meeting_name': actual_name}).eq('id', m['id']).execute()
            fixed += 1
        except json.JSONDecodeError:
            print(f"❌ Could not parse JSON for {m['id'][:8]}: {name[:50]}")

print(f"\n✅ Fixed {fixed} meetings")
