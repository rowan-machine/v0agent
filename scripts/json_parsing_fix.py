#!/usr/bin/env python3
"""Test that the JSON-encoded meeting parsing fix works."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.repositories.meetings import SupabaseMeetingRepository

def test_supabase_json_parsing():
    """Test that SupabaseMeetingRepository can parse JSON-encoded meeting data."""
    print("Testing Supabase JSON parsing...")
    
    repo = SupabaseMeetingRepository()
    
    # Simulate a row where the entire meeting is JSON-encoded in meeting_name
    problematic_row = {
        "id": "123",
        "meeting_name": json.dumps({
            "meeting_name": "Test Meeting",
            "meeting_date": "2024-01-15",
            "synthesized_notes": "Test notes",
            "signals": {"decisions": ["Use new framework"]},
            "raw_text": "Transcript here"
        }),
        "meeting_date": None,
        "synthesized_notes": None,
        "signals": {},
        "raw_text": None,
        "pocket_ai_summary": None,
        "pocket_mind_map": None,
        "import_source": None,
        "created_at": None,
        "updated_at": None
    }
    
    # Format the row using the fixed _format_row method
    result = repo._format_row(problematic_row)
    
    # Verify the data was correctly extracted
    assert result["meeting_name"] == "Test Meeting", f"Expected 'Test Meeting', got '{result['meeting_name']}'"
    assert result["meeting_date"] == "2024-01-15", f"Expected '2024-01-15', got '{result['meeting_date']}'"
    assert result["synthesized_notes"] == "Test notes", f"Expected 'Test notes', got '{result['synthesized_notes']}'"
    assert result["signals"]["decisions"] == ["Use new framework"], f"Expected decisions list, got {result['signals']}"
    
    print("✓ Supabase JSON parsing test passed!")


def test_normal_rows_still_work():
    """Test that normal (non-JSON-encoded) rows still work correctly."""
    print("Testing normal row parsing...")
    
    repo = SupabaseMeetingRepository()
    
    # Normal row
    normal_row = {
        "id": "456",
        "meeting_name": "Normal Meeting",
        "meeting_date": "2024-01-17",
        "synthesized_notes": "Normal notes",
        "signals": {"decisions": ["Normal decision"]},
        "raw_text": "Normal transcript",
        "pocket_ai_summary": "Normal summary",
        "pocket_mind_map": "Normal map",
        "import_source": "api",
        "created_at": "2024-01-17T10:00:00",
        "updated_at": "2024-01-17T11:00:00"
    }
    
    result = repo._format_row(normal_row)
    
    assert result["meeting_name"] == "Normal Meeting"
    assert result["meeting_date"] == "2024-01-17"
    assert result["synthesized_notes"] == "Normal notes"
    assert result["import_source"] == "api"
    
    print("✓ Normal row parsing test passed!")


if __name__ == "__main__":
    test_supabase_json_parsing()
    test_normal_rows_still_work()
    print("\n✓ All tests passed!")
