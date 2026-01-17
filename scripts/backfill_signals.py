#!/usr/bin/env python3
# Backfill signals_json for existing meetings

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.db import connect
from app.mcp.parser import parse_meeting_summary
from app.mcp.extract import extract_structured_signals


def backfill_signals():
    with connect() as conn:
        # Get all meetings
        meetings = conn.execute(
            "SELECT id, synthesized_notes FROM meeting_summaries"
        ).fetchall()
        
        print(f"Found {len(meetings)} meetings to process...")
        
        for meeting in meetings:
            meeting_id = meeting["id"]
            synthesized_notes = meeting["synthesized_notes"]
            
            # Parse and extract signals
            parsed_sections = parse_meeting_summary(synthesized_notes)
            signals = extract_structured_signals(parsed_sections)
            
            # Update the record
            conn.execute(
                """
                UPDATE meeting_summaries
                SET signals_json = ?
                WHERE id = ?
                """,
                (json.dumps(signals), meeting_id)
            )
            
            print(f"✓ Meeting {meeting_id}: extracted {sum(len(v) if isinstance(v, list) else 0 for v in signals.values())} signals")
        
        print(f"\n✓ Successfully backfilled signals for {len(meetings)} meetings")


if __name__ == "__main__":
    backfill_signals()
