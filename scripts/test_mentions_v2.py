#!/usr/bin/env python3
"""Test mention detection with the updated logic."""
import sys
import os
import re
sys.path.insert(0, '/Users/rowan/v0agent')
from src.app.infrastructure.supabase_client import get_supabase_client

client = get_supabase_client()

user_name = 'Rowan'

# Get documents with Rowan
docs = client.table('documents').select('id, source, content').ilike('content', f'%{user_name}%').limit(5).execute()

# Patterns for speaker detection
timestamp_pattern = r'^\s*(\w+\s+)?\d+\s*(minutes?|seconds?|:\d{2})'
colon_pattern = r'^(\**)?[:\s*]'
lastname_colon_pattern = r'^\s*\w+\s*(:\**|\*+:)'
line_prefix_pattern = r'^\s*(\w{1,3}|\s|\**)*$'

for doc in docs.data:
    content = doc['content']
    print(f"\n=== {doc['source'][:40]} ===")
    
    mentions = []
    speakers = []
    search_pos = 0
    
    while True:
        idx = content.lower().find(user_name.lower(), search_pos)
        if idx == -1:
            break
            
        after_name = content[idx + len(user_name):idx + len(user_name) + 50]
        line_start = content.rfind('\n', 0, idx) + 1
        line_prefix = content[line_start:idx].strip()
        
        reasons = []
        is_speaker = False
        
        if re.match(timestamp_pattern, after_name, re.IGNORECASE):
            is_speaker = True
            reasons.append("timestamp")
        
        if re.match(colon_pattern, after_name):
            is_speaker = True  
            reasons.append("colon")
        
        if re.match(lastname_colon_pattern, after_name, re.IGNORECASE):
            is_speaker = True
            reasons.append("lastname:colon")
        
        if len(line_prefix) < 5 and re.match(line_prefix_pattern, line_prefix):
            is_speaker = True
            reasons.append("line-start")
        
        context = f"...{content[max(0,idx-20):idx]}[{user_name}]{after_name[:25]}..."
        
        if is_speaker:
            speakers.append((context, reasons))
        else:
            mentions.append(context)
        
        search_pos = idx + len(user_name)
    
    print(f"\n🔊 SPEAKER ({len(speakers)}):")
    for s, r in speakers[:3]:
        print(f"  [{', '.join(r)}] {s}")
    
    print(f"\n👋 MENTION ({len(mentions)}):")
    for m in mentions[:5]:
        print(f"  {m}")
