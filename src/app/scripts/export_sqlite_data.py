#!/usr/bin/env python3
"""Export SQLite data to JSON for Supabase migration."""
import sqlite3
import json
from pathlib import Path

db_path = Path(__file__).parent.parent.parent.parent / "agent.db"
output_dir = Path(__file__).parent / "migration_data"
output_dir.mkdir(exist_ok=True)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Export skills
skills = conn.execute('SELECT * FROM skill_tracker').fetchall()
skills_data = []
for s in skills:
    d = dict(s)
    evidence = d.get('evidence', '[]')
    try:
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
    except:
        evidence = []
    skills_data.append({
        "skill_name": d.get('skill_name'),
        "category": d.get('category', 'general'),
        "proficiency_level": d.get('proficiency_level', 0) or 0,
        "evidence": evidence,
        "projects_count": d.get('projects_count', 0) or 0,
        "tickets_count": d.get('tickets_count', 0) or 0,
    })

with open(output_dir / "skills.json", "w") as f:
    json.dump(skills_data, f, indent=2)
print(f"Exported {len(skills_data)} skills to {output_dir / 'skills.json'}")

# Export career suggestions
suggestions = conn.execute('SELECT * FROM career_suggestions').fetchall()
suggestions_data = []
for s in suggestions:
    d = dict(s)
    suggestions_data.append({
        "suggestion_type": d.get('suggestion_type', 'learning'),
        "title": d.get('title'),
        "description": d.get('description'),
        "rationale": d.get('rationale'),
        "difficulty": d.get('difficulty'),
        "time_estimate": d.get('time_estimate'),
        "related_goal": d.get('related_goal'),
        "status": d.get('status', 'active'),
        "source": d.get('source', 'ai'),
    })

with open(output_dir / "career_suggestions.json", "w") as f:
    json.dump(suggestions_data, f, indent=2)
print(f"Exported {len(suggestions_data)} career suggestions")

# Export career memories
memories = conn.execute('SELECT * FROM career_memories').fetchall()
memories_data = []
for m in memories:
    d = dict(m)
    skills = d.get('skills', '')
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(',') if s.strip()]
    memories_data.append({
        "memory_type": d.get('memory_type', 'learning'),
        "title": d.get('title'),
        "description": d.get('description'),
        "skills": skills,
        "source_type": d.get('source_type'),
        "is_pinned": bool(d.get('is_pinned')),
        "is_ai_work": bool(d.get('is_ai_work')),
    })

with open(output_dir / "career_memories.json", "w") as f:
    json.dump(memories_data, f, indent=2)
print(f"Exported {len(memories_data)} career memories")

# Export meetings
meetings = conn.execute('SELECT * FROM meeting_summaries').fetchall()
meetings_data = []
for m in meetings:
    d = dict(m)
    signals = d.get('signals', '{}')
    try:
        if isinstance(signals, str):
            signals = json.loads(signals)
    except:
        signals = {}
    meetings_data.append({
        "meeting_name": d.get('meeting_name'),
        "synthesized_notes": d.get('synthesized_notes'),
        "meeting_date": d.get('meeting_date'),
        "raw_text": d.get('raw_text'),
        "signals": signals,
    })

with open(output_dir / "meetings.json", "w") as f:
    json.dump(meetings_data, f, indent=2, default=str)
print(f"Exported {len(meetings_data)} meetings")

# Export documents
docs = conn.execute('SELECT * FROM docs').fetchall()
docs_data = []
for d_row in docs:
    d = dict(d_row)
    docs_data.append({
        "source": d.get('source'),
        "content": d.get('content'),
        "document_date": d.get('document_date'),
    })

with open(output_dir / "documents.json", "w") as f:
    json.dump(docs_data, f, indent=2, default=str)
print(f"Exported {len(docs_data)} documents")

# Export tickets
tickets = conn.execute('SELECT * FROM tickets').fetchall()
tickets_data = []
for t in tickets:
    d = dict(t)
    tags = d.get('tags', '')
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    task_decomp = d.get('task_decomposition')
    try:
        if isinstance(task_decomp, str):
            task_decomp = json.loads(task_decomp)
    except:
        task_decomp = None
    tickets_data.append({
        "ticket_id": d.get('ticket_id'),
        "title": d.get('title'),
        "description": d.get('description'),
        "status": d.get('status', 'backlog'),
        "priority": d.get('priority'),
        "sprint_points": d.get('sprint_points', 0) or 0,
        "in_sprint": bool(d.get('in_sprint', True)),
        "ai_summary": d.get('ai_summary'),
        "implementation_plan": d.get('implementation_plan'),
        "task_decomposition": task_decomp,
        "tags": tags,
    })

with open(output_dir / "tickets.json", "w") as f:
    json.dump(tickets_data, f, indent=2, default=str)
print(f"Exported {len(tickets_data)} tickets")

# Export standups
standups = conn.execute('SELECT * FROM standup_updates').fetchall()
standups_data = []
for s in standups:
    d = dict(s)
    key_themes = d.get('key_themes')
    try:
        if isinstance(key_themes, str):
            key_themes = json.loads(key_themes)
    except:
        key_themes = None
    standups_data.append({
        "content": d.get('content'),
        "sentiment": d.get('sentiment'),
        "key_themes": key_themes,
        "feedback": d.get('feedback'),
    })

with open(output_dir / "standup_updates.json", "w") as f:
    json.dump(standups_data, f, indent=2)
print(f"Exported {len(standups_data)} standup updates")

# Export career chat history
chats = conn.execute('SELECT * FROM career_chat_updates').fetchall()
chats_data = []
for c in chats:
    d = dict(c)
    chats_data.append({
        "message": d.get('message'),
        "response": d.get('response'),
        "summary": d.get('summary'),
    })

with open(output_dir / "career_chat_updates.json", "w") as f:
    json.dump(chats_data, f, indent=2)
print(f"Exported {len(chats_data)} career chat updates")

conn.close()
print("\nAll exports complete!")
