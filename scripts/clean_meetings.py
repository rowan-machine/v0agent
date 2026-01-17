#!/usr/bin/env python3
# Backfill: Clean existing meeting summaries

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.db import connect
from app.mcp.cleaner import clean_meeting_text
from app.mcp.parser import parse_meeting_summary
from app.mcp.extract import extract_structured_signals


def clean_existing_meetings():
    with connect() as conn:
        # Get all meetings
        meetings = conn.execute(
            "SELECT id, synthesized_notes FROM meeting_summaries"
        ).fetchall()
        
        print(f"Found {len(meetings)} meetings to clean...")
        
        for meeting in meetings:
            meeting_id = meeting["id"]
            original_notes = meeting["synthesized_notes"]
            
            # Clean the text
            cleaned_notes = clean_meeting_text(original_notes)
            
            # Re-parse and extract signals from cleaned text
            parsed_sections = parse_meeting_summary(cleaned_notes)
            signals = extract_structured_signals(parsed_sections)
            
            # Update the record
            conn.execute(
                """
                UPDATE meeting_summaries
                SET synthesized_notes = ?, signals_json = ?
                WHERE id = ?
                """,
                (cleaned_notes, json.dumps(signals), meeting_id)
            )
            
            # Show what changed
            if original_notes != cleaned_notes:
                removed_chars = len(original_notes) - len(cleaned_notes)
                print(f"✓ Meeting {meeting_id}: cleaned ({removed_chars} chars removed)")
            else:
                print(f"  Meeting {meeting_id}: no changes needed")
        
        print(f"\n✓ Successfully cleaned {len(meetings)} meetings")


if __name__ == "__main__":
    clean_existing_meetings()
