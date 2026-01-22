#!/usr/bin/env python3
"""Check SQLite data counts for migration."""
import sqlite3
import json
from pathlib import Path

# Connect to SQLite
db_path = Path(__file__).parent.parent.parent.parent / "agent.db"
print(f"Database: {db_path}")
print(f"Exists: {db_path.exists()}")

if not db_path.exists():
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

tables = [
    'meeting_summaries',
    'docs', 
    'tickets',
    'dikw_items',
    'embeddings',
    'career_profile',
    'career_suggestions',
    'career_memories',
    'skill_tracker',
    'standup_updates',
    'career_chat_updates',
]

print("\nRow counts:")
for table in tables:
    try:
        row = conn.execute(f'SELECT COUNT(*) as c FROM {table}').fetchone()
        print(f"  {table}: {row[0]}")
    except Exception as e:
        print(f"  {table}: ERROR - {e}")

# Export sample data as JSON for migration
print("\nExporting data for migration...")

# Meetings
meetings = conn.execute("""
    SELECT id, meeting_name, synthesized_notes, meeting_date, raw_text, 
           signals, source_document_id, created_at
    FROM meeting_summaries
""").fetchall()
print(f"\nMeetings ({len(meetings)}):")
for m in meetings[:3]:
    print(f"  - {dict(m)['meeting_name']}")

# Skills
skills = conn.execute("""
    SELECT skill_name, category, proficiency_level, evidence, updated_at
    FROM skill_tracker
    ORDER BY proficiency_level DESC
    LIMIT 10
""").fetchall()
print(f"\nTop Skills ({len(skills)}):")
for s in skills:
    print(f"  - {dict(s)['skill_name']}: {dict(s)['proficiency_level']}%")

conn.close()
print("\nDone!")
