# src/app/domains/dashboard/__init__.py
"""
Dashboard Domain

Provides dashboard-specific functionality including:
- Quick Ask AI queries
- Smart coaching highlights
- Highlight drill-down context
"""

from .api import router

__all__ = ["router"]
