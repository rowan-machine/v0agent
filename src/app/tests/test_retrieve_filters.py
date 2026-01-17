# tests/test_retrieve_filters.py

from app.db import connect
from app.memory.retrieve import retrieve


def seed_all():
    with connect() as conn:
        # Old doc
        conn.execute(
            "INSERT INTO docs (source, content, document_date) VALUES (?, ?, ?)",
            ("Old Doc", "Blocked by legacy process.", "2025-12-01"),
        )
        # New doc
        conn.execute(
            "INSERT INTO docs (source, content, document_date) VALUES (?, ?, ?)",
            ("New Doc", "Blocked by new dependency.", "2026-01-15"),
        )
        # Meeting
        conn.execute(
            """
            INSERT INTO meeting_summaries
            (meeting_name, synthesized_notes, meeting_date)
            VALUES (?, ?, ?)
            """,
            ("Retro", "Blocked by unclear ownership.", "2026-01-14"),
        )


def test_date_filter_and_both_sources(temp_db):
    seed_all()

    results = retrieve(
        terms=["blocked"],
        source_type="both",
        start_date="2026-01-01",
        end_date=None,
        limit=10,
    )

    docs = results["documents"]
    meetings = results["meetings"]

    # Old doc excluded
    assert len(docs) == 1
    assert docs[0]["source"] == "New Doc"

    # Meeting included
    assert len(meetings) == 1
    assert meetings[0]["meeting_name"] == "Retro"
