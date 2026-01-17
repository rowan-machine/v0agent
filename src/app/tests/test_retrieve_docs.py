# tests/test_retrieve_docs.py

from app.db import connect
from app.memory.retrieve import retrieve


def seed_docs():
    with connect() as conn:
        conn.execute(
            "INSERT INTO docs (source, content, document_date) VALUES (?, ?, ?)",
            ("Doc A", "This sprint is blocked by schema approval.", "2026-01-10"),
        )
        conn.execute(
            "INSERT INTO docs (source, content, document_date) VALUES (?, ?, ?)",
            ("Doc B", "Everything is on track.", "2026-01-11"),
        )


def test_retrieve_documents_basic(temp_db):
    seed_docs()

    results = retrieve(
        terms=["blocked"],
        source_type="docs",
        limit=10,
    )

    docs = results["documents"]
    meetings = results["meetings"]

    assert len(docs) == 1
    assert docs[0]["source"] == "Doc A"
    assert meetings == []
