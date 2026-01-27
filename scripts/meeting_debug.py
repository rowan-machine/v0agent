#!/usr/bin/env python3
"""Debug script to check how meetings are being stored and retrieved."""

import json
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set environment for testing
os.environ["ENVIRONMENT"] = "test"
os.environ["SUPABASE_URL"] = "http://localhost:54321"  # Local Supabase
os.environ["SUPABASE_ANON_KEY"] = "test"

# Import after path setup
from app.services import meetings_supabase
from app.repositories.meetings import get_meeting_repository
from app.mcp.tools import load_meeting_bundle

def test_meeting_roundtrip():
    """Test loading and retrieving a meeting."""
    
    # Create a test meeting
    test_data = {
        "meeting_name": "Test Meeting",
        "meeting_date": "2024-01-15",
        "summary_text": """
        Synthesized Signals (Authoritative)
        Key decisions made today.
        
        Decisions:
        - Use new framework for Q1
        
        Action Items:
        - John to review PR
        
        Blockers:
        - Storage limits
        
        Risks:
        - Timeline slippage
        
        Ideas:
        - Performance optimization
        """,
        "transcript_text": "This is the meeting transcript.",
        "pocket_ai_summary": "Quick summary from Pocket AI.",
        "pocket_mind_map": "Pocket mind map content."
    }
    
    print("=" * 80)
    print("STEP 1: Loading meeting via load_meeting_bundle")
    print("=" * 80)
    print(f"Input data: {json.dumps(test_data, indent=2)}")
    
    result = load_meeting_bundle(test_data)
    print(f"\nResult: {json.dumps(result, indent=2)}")
    
    if result.get("status") == "skipped":
        print("\nMeeting already exists - fetching it instead")
        meeting_id = result.get("existing_meeting_id")
    else:
        print("\nMeeting created successfully")
        # Get the meeting ID from somewhere - we need to query for it
        repo = get_meeting_repository("supabase")
        meetings = repo.get_all()
        if meetings:
            meeting = meetings[-1]  # Get the last one
            meeting_id = meeting.get("id")
        else:
            print("ERROR: No meetings found after creation")
            return
    
    print("\n" + "=" * 80)
    print("STEP 2: Retrieving the meeting")
    print("=" * 80)
    
    repo = get_meeting_repository("supabase")
    meeting = repo.get_by_id(meeting_id)
    
    if not meeting:
        print(f"ERROR: Meeting {meeting_id} not found")
        return
    
    print(f"Retrieved meeting: {json.dumps(meeting, indent=2, default=str)}")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    
    meeting_name = meeting.get("meeting_name")
    print(f"Meeting name type: {type(meeting_name)}")
    print(f"Meeting name value: {meeting_name}")
    
    if isinstance(meeting_name, str) and meeting_name.startswith('{'):
        print("⚠️  WARNING: Meeting name is a JSON string!")
        try:
            parsed = json.loads(meeting_name)
            print(f"Parsed content: {json.dumps(parsed, indent=2)}")
        except:
            print("Could not parse as JSON")
    else:
        print("✓ Meeting name is correctly formatted")

if __name__ == "__main__":
    test_meeting_roundtrip()
