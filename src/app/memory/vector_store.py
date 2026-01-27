# src/app/memory/vector_store.py
import json
import logging
from datetime import datetime, timezone
from .embed import vec_to_json, vec_from_json
from ..infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def upsert_embedding(ref_type: str, ref_id: int, model: str, vector: list[float]) -> None:
    if not vector:
        return
    supabase = get_supabase_client()
    if not supabase:
        logger.warning("Supabase client not available for upsert_embedding")
        return
    
    try:
        # Supabase upsert with onConflict
        supabase.table("embeddings").upsert(
            {
                "ref_type": ref_type,
                "ref_id": ref_id,
                "model": model,
                "vector": vec_to_json(vector),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="ref_type,ref_id,model"
        ).execute()
    except Exception as e:
        logger.error(f"Failed to upsert embedding: {e}")


def fetch_all_embeddings(ref_type: str, model: str):
    supabase = get_supabase_client()
    if not supabase:
        logger.warning("Supabase client not available for fetch_all_embeddings")
        return []
    
    try:
        result = supabase.table("embeddings").select("ref_id, vector").eq("ref_type", ref_type).eq("model", model).execute()
        if result.data:
            return [(r["ref_id"], vec_from_json(r["vector"])) for r in result.data]
    except Exception as e:
        logger.error(f"Failed to fetch embeddings: {e}")
    
    return []

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
