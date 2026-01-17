#!/usr/bin/env python3
# Debug parser output

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.db import connect
from app.mcp.parser import parse_meeting_summary
from app.mcp.extract import extract_structured_signals


def debug_parser():
    with connect() as conn:
        # Get one meeting
        meeting = conn.execute(
            "SELECT id, meeting_name, synthesized_notes FROM meeting_summaries WHERE id = 5"
        ).fetchone()
        
        if not meeting:
            print("No meeting found")
            return
        
        print(f"=== Meeting {meeting['id']}: {meeting['meeting_name']} ===\n")
        
        # Parse
        parsed_sections = parse_meeting_summary(meeting['synthesized_notes'])
        
        print("Parsed sections:")
        for key in parsed_sections:
            print(f"  - {key}: {len(parsed_sections[key])} chars")
        
        print("\n")
        
        # Extract signals
        signals = extract_structured_signals(parsed_sections)
        
        print("Extracted signals:")
        print(json.dumps(signals, indent=2))


if __name__ == "__main__":
    debug_parser()
