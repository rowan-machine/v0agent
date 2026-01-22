# src/app/api/mobile/models.py
"""
Pydantic models for mobile sync API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DeviceType(str, Enum):
    LAPTOP = "laptop"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    TABLET = "tablet"


class SyncEntityType(str, Enum):
    MEETING = "meeting"
    DOCUMENT = "document"
    SIGNAL = "signal"
    TICKET = "ticket"


class ConflictResolution(str, Enum):
    SERVER_WINS = "server_wins"
    CLIENT_WINS = "client_wins"
    MANUAL = "manual"


# -------------------------
# Device Models
# -------------------------

class DeviceRegister(BaseModel):
    """Request model for device registration."""
    device_id: str = Field(..., min_length=1, max_length=255)
    device_name: str = Field(..., min_length=1, max_length=255)
    device_type: DeviceType
    app_version: Optional[str] = None


class DeviceResponse(BaseModel):
    """Response model for device info."""
    device_id: str
    device_name: str
    device_type: str
    last_seen: Optional[str] = None
    registered_at: Optional[str] = None
    app_version: Optional[str] = None


class DeviceListResponse(BaseModel):
    """Response model for list of devices."""
    devices: List[DeviceResponse]
    count: int


# -------------------------
# Sync Models
# -------------------------

class SyncChange(BaseModel):
    """A single entity change for sync."""
    entity_type: SyncEntityType
    entity_id: int
    action: str = Field(..., pattern=r"^(create|update|delete)$")
    data: Optional[Dict[str, Any]] = None
    local_timestamp: float  # Unix timestamp


class SyncRequest(BaseModel):
    """Request model for sync operation."""
    device_id: str
    changes: List[SyncChange] = []
    last_sync_timestamp: Optional[float] = None  # Unix timestamp


class SyncConflict(BaseModel):
    """Model for a sync conflict."""
    entity_type: str
    entity_id: int
    server_data: Dict[str, Any]
    client_data: Dict[str, Any]
    server_timestamp: float
    client_timestamp: float
    resolution: Optional[ConflictResolution] = None


class SyncResponse(BaseModel):
    """Response model for sync operation."""
    success: bool = True
    device_id: str
    server_changes: List[Dict[str, Any]] = []
    sync_timestamp: float  # Unix timestamp for next sync
    conflicts: List[SyncConflict] = []
    applied_count: int = 0
    error: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Response model for sync status."""
    device_id: str
    online: bool = True
    pending_changes: int = 0
    last_sync: Optional[str] = None
    sync_enabled: bool = True
