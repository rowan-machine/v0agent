# src/app/domains/knowledge_graph/api/__init__.py
"""
Knowledge Graph API

Aggregates all knowledge graph sub-routers.
"""

from fastapi import APIRouter

from .links import router as links_router
from .suggestions import router as suggestions_router
from .stats import router as stats_router

# Create the aggregated knowledge graph router
router = APIRouter(prefix="/graph", tags=["knowledge_graph"])

# Include all sub-routers
router.include_router(links_router)
router.include_router(suggestions_router)
router.include_router(stats_router)

__all__ = ["router"]
