#!/usr/bin/env python3
# Migration: Add signals_json column to meeting_summaries

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.db import connect

def migrate():
    with connect() as conn:
        # Check if column already exists
        cursor = conn.execute("PRAGMA table_info(meeting_summaries)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "signals_json" in columns:
            print("Column 'signals_json' already exists. Skipping migration.")
            return
        
        # Add the column
        conn.execute("""
            ALTER TABLE meeting_summaries
            ADD COLUMN signals_json TEXT
        """)
        print("Successfully added 'signals_json' column to meeting_summaries table.")

if __name__ == "__main__":
    migrate()
