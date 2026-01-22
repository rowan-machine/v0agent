# src/app/api/v1/__init__.py
"""
API v1 - Versioned REST API endpoints.

Phase 3.1: Modern API with proper HTTP semantics.
- Pagination with skip/limit
- Proper HTTP status codes
- Pydantic request/response models
- OpenAPI/Swagger documentation
"""

from fastapi import APIRouter

from .meetings import router as meetings_router
from .documents import router as documents_router
from .signals import router as signals_router
from .tickets import router as tickets_router

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include sub-routers
router.include_router(meetings_router, prefix="/meetings", tags=["meetings"])
router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(signals_router, prefix="/signals", tags=["signals"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
