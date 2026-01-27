# src/app/domains/documents/api/__init__.py
"""
Documents Domain API Routes

Aggregates all document sub-routers into a single router for main.py.
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .search import router as search_router

# Create the aggregated documents router
router = APIRouter(prefix="/documents", tags=["documents"])

# Include all sub-routers
router.include_router(crud_router, tags=["documents-crud"])
router.include_router(search_router)

__all__ = ["router"]
