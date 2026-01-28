# src/app/domains/search/__init__.py
"""
Search Domain

Provides unified search across all entity types:
- Keyword search
- Semantic (vector) search  
- Hybrid search (RRF fusion)
- Full-text search with HTML templates
- Smart suggestions
"""

from .api import router, fulltext_router

__all__ = ["router", "fulltext_router"]
