# scripts/backfill_embeddings.py

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.db import connect
from app.memory.embed import embed_text, EMBED_MODEL
from app.memory.vector_store import upsert_embedding

def backfill_docs():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, source, content FROM docs"
        ).fetchall()

    for row in rows:
        text = f"{row['source']}\n{row['content']}"
        vec = embed_text(text)
        upsert_embedding("doc", row["id"], EMBED_MODEL, vec)
        print(f"Embedded doc {row['id']}")

def backfill_meetings():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, meeting_name, synthesized_notes FROM meeting_summaries"
        ).fetchall()

    for row in rows:
        text = f"{row['meeting_name']}\n{row['synthesized_notes']}"
        vec = embed_text(text)
        upsert_embedding("meeting", row["id"], EMBED_MODEL, vec)
        print(f"Embedded meeting {row['id']}")

if __name__ == "__main__":
    backfill_docs()
    backfill_meetings()
    print("Backfill complete.")
