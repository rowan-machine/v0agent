# src/app/api/mobile/device.py
"""
Device management endpoints for mobile sync.

Handles device registration, discovery, and status.
"""

from fastapi import APIRouter, HTTPException

from .models import (
    DeviceRegister, DeviceResponse, DeviceListResponse
)
from ...db import connect

router = APIRouter()


def ensure_device_table():
    """Ensure device_registry table exists."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_registry (
                device_id TEXT PRIMARY KEY,
                device_name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                app_version TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


@router.post("/register", response_model=DeviceResponse)
async def register_device(device: DeviceRegister):
    """
    Register a device for multi-device sync.
    
    Creates or updates device entry in registry.
    """
    ensure_device_table()
    
    with connect() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO device_registry 
            (device_id, device_name, device_type, app_version, last_seen, registered_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 
                    COALESCE((SELECT registered_at FROM device_registry WHERE device_id = ?), CURRENT_TIMESTAMP))
        """, (device.device_id, device.device_name, device.device_type.value,
              device.app_version, device.device_id))
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM device_registry WHERE device_id = ?",
            (device.device_id,)
        ).fetchone()
    
    d = dict(row)
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
    
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM device_registry ORDER BY last_seen DESC"
        ).fetchall()
    
    devices = [
        DeviceResponse(
            device_id=dict(row)["device_id"],
            device_name=dict(row)["device_name"],
            device_type=dict(row)["device_type"],
            last_seen=dict(row).get("last_seen"),
            registered_at=dict(row).get("registered_at"),
            app_version=dict(row).get("app_version")
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
    
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM device_registry WHERE device_id = ?",
            (device_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    
    d = dict(row)
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
    
    with connect() as conn:
        existing = conn.execute(
            "SELECT device_id FROM device_registry WHERE device_id = ?",
            (device_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Device not found")
        
        conn.execute("DELETE FROM device_registry WHERE device_id = ?", (device_id,))
        conn.commit()


@router.post("/{device_id}/heartbeat", response_model=DeviceResponse)
async def device_heartbeat(device_id: str):
    """
    Update device last_seen timestamp (heartbeat).
    
    Returns 404 if device not registered.
    """
    ensure_device_table()
    
    with connect() as conn:
        result = conn.execute("""
            UPDATE device_registry SET last_seen = CURRENT_TIMESTAMP
            WHERE device_id = ?
        """, (device_id,))
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Device not registered")
        
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM device_registry WHERE device_id = ?",
            (device_id,)
        ).fetchone()
    
    d = dict(row)
    return DeviceResponse(
        device_id=d["device_id"],
        device_name=d["device_name"],
        device_type=d["device_type"],
        last_seen=d.get("last_seen"),
        registered_at=d.get("registered_at"),
        app_version=d.get("app_version")
    )
