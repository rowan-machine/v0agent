#!/usr/bin/env python3
"""Test mention detection logic."""
import sys
import os
import re
sys.path.insert(0, '/Users/rowan/v0agent')
from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()

user_name = 'Rowan'
pattern = r'^\s*(\w+\s+)?\d+\s*(minutes?|seconds?|:\d{2})'

# Get transcripts that have Rowan
docs = client.table('documents').select('content, source').ilike('content', f'%{user_name}%').ilike('source', 'Transcript%').limit(3).execute()

for doc in docs.data:
    content = doc['content']
    print(f"\n=== {doc['source'][:40]} ===")
    
    search_pos = 0
    mentions = []
    speakers = []
    
    while True:
        idx = content.lower().find(user_name.lower(), search_pos)
        if idx == -1:
            break
            
        # Get context
        before = content[max(0, idx-50):idx]
        after_name = content[idx+len(user_name):idx+len(user_name)+50]
        
        # Check if speaker line (followed by timestamp)
        is_speaker = bool(re.match(pattern, after_name, re.IGNORECASE))
        
        # Also check line-start pattern
        line_start = content.rfind('\n', 0, idx) + 1
        line_prefix = content[line_start:idx].strip()
        is_line_start = len(line_prefix) < 5
        
        context = before[-20:].replace('\n', '\\n') + '[' + user_name + ']' + after_name[:25].replace('\n', '\\n')
        
        if is_speaker:
            speakers.append(context)
        elif is_line_start:
            speakers.append(context + " (line start)")
        else:
            mentions.append(context)
        
        search_pos = idx + len(user_name)
    
    print(f"\n🔊 SPEAKER LINES ({len(speakers)}):")
    for s in speakers[:3]:
        print(f"  {s}")
    if len(speakers) > 3:
        print(f"  ... and {len(speakers)-3} more")
    
    print(f"\n👋 REAL MENTIONS ({len(mentions)}):")
    for m in mentions[:5]:
        print(f"  {m}")
    if len(mentions) > 5:
        print(f"  ... and {len(mentions)-5} more")
