#!/usr/bin/env python
import os
import sys

# Set up path
sys.path.insert(0, '/Users/rowan/v0agent')

# Load env
from pathlib import Path
env_file = Path('/Users/rowan/v0agent/.env')
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

from src.app.services import meetings_supabase

# Get all meetings
meetings = meetings_supabase.get_all_meetings(limit=1)
if meetings:
    m = meetings[0]
    print("meeting_name type:", type(m.get('meeting_name')))
    mn = m.get('meeting_name')
    if isinstance(mn, str):
        if mn.startswith('{'):
            print("⚠️  WARNING: meeting_name IS A JSON STRING!")
        print("meeting_name (first 150 chars):", repr(mn[:150]))
    else:
        print("meeting_name:", mn)
else:
    print("No meetings found")
