# src/app/domains/search/api/__init__.py
"""
Search Domain API Routes

Aggregates search sub-routers.
"""

from fastapi import APIRouter

from .keyword import router as keyword_router
from .semantic import router as semantic_router
from .unified import router as unified_router
from .fulltext import router as fulltext_router

# Create the aggregated search router
router = APIRouter(prefix="/search", tags=["search"])

# Include all sub-routers
router.include_router(keyword_router)
router.include_router(semantic_router)
router.include_router(unified_router)

# Fulltext router for legacy /search endpoint (HTML template)
# This is mounted separately in routers.py without prefix
fulltext_router = fulltext_router

__all__ = ["router", "fulltext_router"]
