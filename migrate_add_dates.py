#!/usr/bin/env python3
"""
Migration script to add meeting_date and document_date columns.
"""
import sqlite3

DB_PATH = "agent.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Add meeting_date column to meeting_summaries
    try:
        cursor.execute("ALTER TABLE meeting_summaries ADD COLUMN meeting_date TEXT")
        print("✓ Added meeting_date column to meeting_summaries")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ meeting_date column already exists")
        else:
            raise
    
    # Add document_date column to docs
    try:
        cursor.execute("ALTER TABLE docs ADD COLUMN document_date TEXT")
        print("✓ Added document_date column to docs")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ document_date column already exists")
        else:
            raise
    
    conn.commit()
    conn.close()
    print("\n✓ Migration complete!")

if __name__ == "__main__":
    migrate()
