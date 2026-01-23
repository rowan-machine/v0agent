# src/app/api/v1/__init__.py
"""
API v1 - Versioned REST API endpoints.

Phase 3.1: Modern API with proper HTTP semantics.
- Pagination with skip/limit
- Proper HTTP status codes
- Pydantic request/response models
- OpenAPI/Swagger documentation

Phase 7+: Signal feedback loop and AI memory integration
Phase F1: File import pipeline for Pocket transcripts
Phase F3: Notification system for proactive alerts
"""

from fastapi import APIRouter

from .meetings import router as meetings_router
from .documents import router as documents_router
from .signals import router as signals_router
from .tickets import router as tickets_router
from .feedback import router as feedback_router
from .ai_memory import router as ai_memory_router
from .imports import router as imports_router
from .notifications import router as notifications_router

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include sub-routers
router.include_router(meetings_router, prefix="/meetings", tags=["meetings"])
router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(signals_router, prefix="/signals", tags=["signals"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
router.include_router(feedback_router, prefix="/signals", tags=["feedback"])
router.include_router(ai_memory_router, prefix="/ai", tags=["ai-memory"])
router.include_router(imports_router, prefix="/imports", tags=["imports"])
router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
