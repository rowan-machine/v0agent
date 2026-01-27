#!/usr/bin/env python3
"""Migration script to fix meetings that have JSON-encoded data in meeting_name."""

import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.db import connect
from app.repositories import get_meeting_repository

def fix_sqlite_meetings():
    """Fix SQLite meetings with JSON-encoded data."""
    logger.info("Fixing SQLite meetings...")
    
    with connect() as conn:
        # Find meetings where meeting_name looks like JSON
        rows = conn.execute("""
            SELECT id, meeting_name, synthesized_notes FROM meeting_summaries
            WHERE meeting_name LIKE '{%'
        """).fetchall()
        
        if not rows:
            logger.info("No SQLite meetings to fix")
            return
        
        for row in rows:
            meeting_id = row["id"]
            meeting_name = row["meeting_name"]
            
            logger.info(f"Found problematic SQLite meeting: {meeting_id}")
            
            try:
                parsed = json.loads(meeting_name)
                if isinstance(parsed, dict):
                    logger.info(f"  Extracted data: {json.dumps(parsed, indent=2)[:200]}...")
                    
                    # Update the meeting with extracted data
                    real_meeting_name = parsed.get("meeting_name", "Untitled Meeting")
                    real_synthesized_notes = parsed.get("synthesized_notes", "")
                    real_meeting_date = parsed.get("meeting_date")
                    real_signals = parsed.get("signals", {})
                    real_raw_text = parsed.get("raw_text", "")
                    
                    conn.execute("""
                        UPDATE meeting_summaries
                        SET meeting_name = ?, synthesized_notes = ?, meeting_date = ?, 
                            signals_json = ?, raw_text = ?
                        WHERE id = ?
                    """, (
                        real_meeting_name,
                        real_synthesized_notes,
                        real_meeting_date,
                        json.dumps(real_signals) if real_signals else None,
                        real_raw_text,
                        meeting_id
                    ))
                    logger.info(f"  ✓ Fixed SQLite meeting {meeting_id}")
            except json.JSONDecodeError:
                logger.warning(f"  Could not parse meeting {meeting_id}")
        
        conn.commit()


def fix_supabase_meetings():
    """Fix Supabase meetings with JSON-encoded data."""
    logger.info("Fixing Supabase meetings...")
    
    repo = get_meeting_repository("supabase")
    if not repo or not repo.client:
        logger.warning("Supabase not available")
        return
    
    try:
        # Get all meetings
        meetings = repo.get_all()
        
        fixed_count = 0
        for meeting in meetings:
            meeting_name = meeting.get("meeting_name")
            
            if isinstance(meeting_name, str) and meeting_name.startswith('{'):
                logger.info(f"Found problematic Supabase meeting: {meeting.get('id')}")
                
                try:
                    parsed = json.loads(meeting_name)
                    if isinstance(parsed, dict):
                        logger.info(f"  Extracted data: {json.dumps(parsed, indent=2)[:200]}...")
                        
                        # Update the meeting
                        real_meeting_name = parsed.get("meeting_name", "Untitled Meeting")
                        real_synthesized_notes = parsed.get("synthesized_notes", "")
                        real_meeting_date = parsed.get("meeting_date")
                        real_signals = parsed.get("signals", {})
                        real_raw_text = parsed.get("raw_text", "")
                        
                        update_data = {
                            "meeting_name": real_meeting_name,
                            "synthesized_notes": real_synthesized_notes,
                            "meeting_date": real_meeting_date,
                            "signals": real_signals,
                            "raw_text": real_raw_text,
                        }
                        
                        repo.update(meeting.get("id"), update_data)
                        logger.info(f"  ✓ Fixed Supabase meeting {meeting.get('id')}")
                        fixed_count += 1
                except json.JSONDecodeError:
                    logger.warning(f"  Could not parse meeting {meeting.get('id')}")
        
        logger.info(f"Fixed {fixed_count} Supabase meetings")
    except Exception as e:
        logger.error(f"Error fixing Supabase meetings: {e}")


if __name__ == "__main__":
    logger.info("Starting meeting data migration...")
    fix_sqlite_meetings()
    fix_supabase_meetings()
    logger.info("Migration complete!")
