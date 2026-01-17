# src/app/memory/semantic.py
import os
from .embed import embed_text, EMBED_MODEL
from .vector_store import fetch_all_embeddings, cosine
from ..db import connect

USE_EMBEDDINGS = os.getenv("USE_EMBEDDINGS", "1") == "1"

def semantic_search(question: str, ref_type: str, k: int = 8):
    if not USE_EMBEDDINGS:
        return []
    qvec = embed_text(question)
    if not qvec:
        return []

    candidates = fetch_all_embeddings(ref_type, EMBED_MODEL)
    scored = [(ref_id, cosine(qvec, vec)) for ref_id, vec in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [ref_id for ref_id, score in scored[:k] if score > 0]

    if not top:
        return []

    with connect() as conn:
        if ref_type == "doc":
            rows = conn.execute(
                f"SELECT id, source, content, document_date, created_at FROM docs WHERE id IN ({','.join(['?']*len(top))})",
                top,
            ).fetchall()
            return [dict(r) for r in rows]
        else:
            rows = conn.execute(
                f"SELECT id, meeting_name, synthesized_notes, meeting_date, created_at FROM meeting_summaries WHERE id IN ({','.join(['?']*len(top))})",
                top,
            ).fetchall()
            return [dict(r) for r in rows]
