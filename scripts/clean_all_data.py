#!/usr/bin/env python
"""Clean up all meetings, documents, and action items for a fresh start."""
import sys
sys.path.insert(0, '/Users/rowan/v0agent')

from src.app.infrastructure.supabase_client import get_supabase_client
import sqlite3


def clean_supabase():
    """Delete all meetings and documents from Supabase."""
    client = get_supabase_client()
    
    # Get counts first
    meetings_count = client.table('meetings').select('id', count='exact').execute()
    docs_count = client.table('documents').select('id', count='exact').execute()
    
    print(f"Found {meetings_count.count} meetings and {docs_count.count} documents in Supabase")
    
    confirm = input("Delete ALL meetings and documents from Supabase? (type 'yes' to confirm): ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return False
    
    # Delete documents first (foreign key to meetings)
    print("Deleting documents...")
    client.table('documents').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    
    # Delete meetings
    print("Deleting meetings...")
    client.table('meetings').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    
    # Verify
    after_meetings = client.table('meetings').select('id', count='exact').execute()
    after_docs = client.table('documents').select('id', count='exact').execute()
    
    print(f"✅ Supabase cleanup complete: {after_meetings.count} meetings, {after_docs.count} documents remaining")
    return True


def clean_sqlite():
    """Delete all meetings and action items from SQLite."""
    conn = sqlite3.connect('/Users/rowan/v0agent/agent.db')
    cursor = conn.cursor()
    
    # Check counts
    meetings = cursor.execute("SELECT COUNT(*) FROM meeting_summaries").fetchone()[0]
    
    print(f"Found {meetings} meetings in SQLite")
    
    confirm = input("Delete ALL meetings from SQLite? (type 'yes' to confirm): ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return False
    
    # Delete meetings
    cursor.execute("DELETE FROM meeting_summaries")
    conn.commit()
    
    # Check after
    after = cursor.execute("SELECT COUNT(*) FROM meeting_summaries").fetchone()[0]
    print(f"✅ SQLite cleanup complete: {after} meetings remaining")
    
    conn.close()
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("CLEANUP SCRIPT - Fresh Start")
    print("=" * 50)
    print()
    
    print("Step 1: Clean Supabase (primary database)")
    clean_supabase()
    
    print()
    print("Step 2: Clean SQLite (legacy database)")
    clean_sqlite()
    
    print()
    print("🎉 Done! You can now load fresh meeting bundles.")
