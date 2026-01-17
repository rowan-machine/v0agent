# tests/test_retrieve_determinism.py

from app.db import connect
from app.memory.retrieve import retrieve


def seed_docs():
    with connect() as conn:
        conn.execute(
            "INSERT INTO docs (source, content) VALUES (?, ?)",
            ("Doc 1", "Blocked by X."),
        )
        conn.execute(
            "INSERT INTO docs (source, content) VALUES (?, ?)",
            ("Doc 2", "Blocked by Y."),
        )


def test_deterministic_order(temp_db):
    seed_docs()

    r1 = retrieve(terms=["blocked"], source_type="docs", limit=10)
    r2 = retrieve(terms=["blocked"], source_type="docs", limit=10)

    assert [d["id"] for d in r1["documents"]] == [
        d["id"] for d in r2["documents"]
    ]
