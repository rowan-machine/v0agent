# src/app/adapters/embedding/__init__.py
"""
Embedding adapters package.

Contains concrete implementations of EmbeddingPort for different providers:
- OpenAI: Cloud-based embeddings using OpenAI API
- Local: Local embeddings using sentence-transformers
"""

from .openai import OpenAIEmbeddingAdapter
from .local import LocalEmbeddingAdapter

__all__ = [
    "OpenAIEmbeddingAdapter",
    "LocalEmbeddingAdapter",
]
