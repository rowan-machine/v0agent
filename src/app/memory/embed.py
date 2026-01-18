# src/app/memory/embed.py
import json
import os
from openai import OpenAI

# Load env vars
from dotenv import load_dotenv
load_dotenv()

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

_client = None
def client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Check your .env file.")
        _client = OpenAI(api_key=api_key)
    return _client

def embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        resp = client().embeddings.create(model=EMBED_MODEL, input=text)
        return resp.data[0].embedding
    except Exception as e:
        print(f"Warning: Embedding failed: {e}")
        # Return empty vector as fallback
        return []

def vec_to_json(vec: list[float]) -> str:
    return json.dumps(vec)

def vec_from_json(s: str) -> list[float]:
    return json.loads(s)
