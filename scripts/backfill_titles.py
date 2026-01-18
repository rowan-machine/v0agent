#!/usr/bin/env python3
"""Backfill conversation titles for existing conversations."""

import sys
sys.path.insert(0, "/Users/rowan/v0agent")

from src.app.db import connect
from src.app.llm import ask


def generate_title_for_conversation(first_message):
    prompt = f"""Generate a very short title (3-6 words max) for a conversation that starts with:

"{first_message[:300]}"

Return ONLY the title, no quotes."""
    try:
        return ask(prompt, "gpt-4.1-mini")[:100]
    except Exception as e:
        print(f"LLM error: {e}")
        words = first_message.split()[:4]
        return " ".join(words)[:40]


def main():
    with connect() as conn:
        # Get conversations without titles that have messages
        rows = conn.execute("""
            SELECT c.id, 
                   (SELECT content FROM messages WHERE conversation_id = c.id AND role = 'user' ORDER BY created_at ASC LIMIT 1) as first_msg
            FROM conversations c
            WHERE (c.title IS NULL OR c.title = '')
        """).fetchall()
        
        count = 0
        for row in rows:
            if row['first_msg']:
                title = generate_title_for_conversation(row['first_msg'])
                conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, row['id']))
                print(f"Updated {row['id']}: {title}")
                count += 1
        
        print(f"\nUpdated {count} conversations with titles")


if __name__ == "__main__":
    main()
