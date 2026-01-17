# src/app/memory/vector_store.py
import json
from .embed import vec_to_json, vec_from_json
from ..db import connect

def upsert_embedding(ref_type: str, ref_id: int, model: str, vector: list[float]) -> None:
    if not vector:
        return
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO embeddings (ref_type, ref_id, model, vector, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(ref_type, ref_id, model)
            DO UPDATE SET vector=excluded.vector, updated_at=datetime('now')
            """,
            (ref_type, ref_id, model, vec_to_json(vector)),
        )

def fetch_all_embeddings(ref_type: str, model: str):
    with connect() as conn:
        rows = conn.execute(
            "SELECT ref_id, vector FROM embeddings WHERE ref_type=? AND model=?",
            (ref_type, model),
        ).fetchall()
    return [(r["ref_id"], vec_from_json(r["vector"])) for r in rows]

def cosine(a: list[float], b: list[float]) -> float:
    # pure python cosine
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x*y for x, y in zip(a, b))
    na = sum(x*x for x in a) ** 0.5
    nb = sum(y*y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
