# src/app/api/mobile/device.py
"""
Device management endpoints for mobile sync.

Handles device registration, discovery, and status.
"""

from fastapi import APIRouter, HTTPException

from .models import (
    DeviceRegister, DeviceResponse, DeviceListResponse
)
from ...infrastructure.supabase_client import get_supabase_client

router = APIRouter()


def ensure_device_table():
    """Ensure device_registry table exists.
    
    Note: Tables are pre-created in Supabase via migrations.
    This function is kept for backwards compatibility.
    """
    pass  # Table creation handled by Supabase migrations


@router.post("/register", response_model=DeviceResponse)
async def register_device(device: DeviceRegister):
    """
    Register a device for multi-device sync.
    
    Creates or updates device entry in registry.
    """
    ensure_device_table()
    
    supabase = get_supabase_client()
    
    # Check if device exists to preserve registered_at
    existing = supabase.table("device_registry").select("registered_at").eq("device_id", device.device_id).execute()
    registered_at = existing.data[0]["registered_at"] if existing.data else None
    
    # Upsert device
    data = {
        "device_id": device.device_id,
        "device_name": device.device_name,
        "device_type": device.device_type.value,
        "app_version": device.app_version,
    }
    if registered_at:
        data["registered_at"] = registered_at
    
    supabase.table("device_registry").upsert(data).execute()
    
    # Fetch the updated record
    result = supabase.table("device_registry").select("*").eq("device_id", device.device_id).execute()
    d = result.data[0]
    
    return DeviceResponse(
        device_id=d["device_id"],
        device_name=d["device_name"],
        device_type=d["device_type"],
        last_seen=d.get("last_seen"),
        registered_at=d.get("registered_at"),
        app_version=d.get("app_version")
    )


@router.get("/list", response_model=DeviceListResponse)
async def list_devices():
    """
    List all registered devices.
    """
    ensure_device_table()
    
    supabase = get_supabase_client()
    result = supabase.table("device_registry").select("*").order("last_seen", desc=True).execute()
    rows = result.data or []
    
    devices = [
        DeviceResponse(
            device_id=row["device_id"],
            device_name=row["device_name"],
            device_type=row["device_type"],
            last_seen=row.get("last_seen"),
            registered_at=row.get("registered_at"),
            app_version=row.get("app_version")
        )
        for row in rows
    ]
    
    return DeviceListResponse(devices=devices, count=len(devices))


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str):
    """
    Get device info by ID.
    
    Returns 404 if device not found.
    """
    ensure_device_table()
    
    supabase = get_supabase_client()
    result = supabase.table("device_registry").select("*").eq("device_id", device_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Device not found")
    
    d = result.data[0]
    return DeviceResponse(
        device_id=d["device_id"],
        device_name=d["device_name"],
        device_type=d["device_type"],
        last_seen=d.get("last_seen"),
        registered_at=d.get("registered_at"),
        app_version=d.get("app_version")
    )


@router.delete("/{device_id}", status_code=204)
async def unregister_device(device_id: str):
    """
    Unregister a device.
    
    Returns 204 on success, 404 if device not found.
    """
    ensure_device_table()
    
    supabase = get_supabase_client()
    
    # Check if device exists
    existing = supabase.table("device_registry").select("device_id").eq("device_id", device_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Device not found")
    
    supabase.table("device_registry").delete().eq("device_id", device_id).execute()


@router.post("/{device_id}/heartbeat", response_model=DeviceResponse)
async def device_heartbeat(device_id: str):
    """
    Update device last_seen timestamp (heartbeat).
    
    Returns 404 if device not registered.
    """
    ensure_device_table()
    
    supabase = get_supabase_client()
    
    # Check if device exists
    existing = supabase.table("device_registry").select("device_id").eq("device_id", device_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Device not registered")
    
    # Update last_seen
    from datetime import datetime, timezone
    supabase.table("device_registry").update({"last_seen": datetime.now(timezone.utc).isoformat()}).eq("device_id", device_id).execute()
    
    # Fetch updated record
    result = supabase.table("device_registry").select("*").eq("device_id", device_id).execute()
    d = result.data[0]
    
    return DeviceResponse(
        device_id=d["device_id"],
        device_name=d["device_name"],
        device_type=d["device_type"],
        last_seen=d.get("last_seen"),
        registered_at=d.get("registered_at"),
        app_version=d.get("app_version")
    )
