# src/app/memory/embed.py
import json
import os
from openai import OpenAI

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

_client = None
def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client

def embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return []
    resp = client().embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding

def vec_to_json(vec: list[float]) -> str:
    return json.dumps(vec)

def vec_from_json(s: str) -> list[float]:
    return json.loads(s)
