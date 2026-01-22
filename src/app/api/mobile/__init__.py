# src/app/api/mobile/__init__.py
"""
API Mobile - Endpoints for mobile app sync and device management.

Phase 3.2: Offline-first mobile sync architecture.
- Device registration and discovery
- Bidirectional sync with conflict resolution
- Sync status and queue management
"""

from fastapi import APIRouter

from .sync import router as sync_router
from .device import router as device_router

router = APIRouter(prefix="/api/mobile", tags=["mobile"])

# Include sub-routers
router.include_router(sync_router, tags=["sync"])
router.include_router(device_router, prefix="/device", tags=["device"])
