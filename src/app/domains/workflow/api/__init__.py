# src/app/domains/workflow/api/__init__.py
"""
Workflow Domain API Routes

Combines all workflow-related routers into a single domain router.
"""

from fastapi import APIRouter

from .modes import router as modes_router
from .progress import router as progress_router
from .timer import router as timer_router
from .jobs import router as jobs_router
from .tracing import router as tracing_router

router = APIRouter(tags=["workflow"])

# Include sub-routers
router.include_router(modes_router)
router.include_router(progress_router)
router.include_router(timer_router)
router.include_router(jobs_router)
router.include_router(tracing_router)

__all__ = ["router"]
