# tests/test_retrieve_meetings.py

from app.db import connect
from app.memory.retrieve import retrieve


def seed_meetings():
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meeting_summaries
            (meeting_name, synthesized_notes, meeting_date)
            VALUES (?, ?, ?)
            """,
            (
                "Sprint Planning",
                "We are blocked by waiting on the PBM schema.",
                "2026-01-12",
            ),
        )


def test_retrieve_meetings_only(temp_db):
    seed_meetings()

    results = retrieve(
        terms=["blocked"],
        source_type="meetings",
        limit=10,
    )

    assert results["documents"] == []
    assert len(results["meetings"]) == 1
    assert results["meetings"][0]["meeting_name"] == "Sprint Planning"
