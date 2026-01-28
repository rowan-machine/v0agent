# src/app/domains/knowledge_graph/__init__.py
"""
Knowledge Graph Domain

Manages entity links between meetings, documents, tickets, DIKW items, and signals.
"""

from .api import router

__all__ = ["router"]
