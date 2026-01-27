# src/app/domains/search/__init__.py
"""
Search Domain

Provides unified search across all entity types:
- Keyword search
- Semantic (vector) search  
- Hybrid search (RRF fusion)
- Mindmap search
- Smart suggestions
"""

from .api import router

__all__ = ["router"]
