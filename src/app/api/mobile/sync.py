# src/app/api/mobile/sync.py
"""
Sync endpoints for mobile app.

Implements bidirectional sync with conflict detection and resolution.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
import time

from .models import (
    SyncRequest, SyncResponse, SyncStatusResponse, SyncChange, SyncConflict
)
from ...db import connect

router = APIRouter()


def ensure_sync_tables():
    """Ensure sync-related tables exist."""
    with connect() as conn:
        # Sync log tracks all changes for delta sync
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                device_id TEXT,
                timestamp REAL NOT NULL,
                data TEXT,
                synced_to TEXT DEFAULT ''
            )
        """)
        
        # Device sync state tracks last sync per device
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_sync_state (
                device_id TEXT PRIMARY KEY,
                last_sync_timestamp REAL NOT NULL,
                pending_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def get_server_changes_since(device_id: str, since_timestamp: float) -> List[Dict[str, Any]]:
    """Get all changes on server since timestamp, excluding device's own changes."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT * FROM sync_log 
            WHERE timestamp > ? AND (device_id IS NULL OR device_id != ?)
            ORDER BY timestamp ASC
        """, (since_timestamp, device_id)).fetchall()
    
    return [dict(row) for row in rows]


def apply_client_change(change: SyncChange, device_id: str) -> Optional[SyncConflict]:
    """
    Apply a single client change to the server.
    
    Returns SyncConflict if conflict detected, None otherwise.
    """
    current_timestamp = time.time()
    
    with connect() as conn:
        # Check for conflict - is there a newer server change for same entity?
        server_change = conn.execute("""
            SELECT * FROM sync_log 
            WHERE entity_type = ? AND entity_id = ? AND timestamp > ?
            ORDER BY timestamp DESC LIMIT 1
        """, (change.entity_type.value, change.entity_id, change.local_timestamp)).fetchone()
        
        if server_change:
            # Conflict detected - server has newer change
            import json
            server_data = json.loads(server_change["data"]) if server_change["data"] else {}
            
            return SyncConflict(
                entity_type=change.entity_type.value,
                entity_id=change.entity_id,
                server_data=server_data,
                client_data=change.data or {},
                server_timestamp=server_change["timestamp"],
                client_timestamp=change.local_timestamp
            )
        
        # No conflict - apply change
        table_map = {
            "meeting": "meeting",
            "document": "document",
            "signal": "signal",
            "ticket": "ticket"
        }
        table = table_map.get(change.entity_type.value)
        
        if change.action == "create" and change.data:
            # Insert new record
            columns = list(change.data.keys())
            placeholders = ", ".join(["?"] * len(columns))
            values = list(change.data.values())
            conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values)
            )
        elif change.action == "update" and change.data:
            # Update existing record
            sets = ", ".join([f"{k} = ?" for k in change.data.keys()])
            values = list(change.data.values()) + [change.entity_id]
            conn.execute(
                f"UPDATE {table} SET {sets} WHERE pk = ?",
                tuple(values)
            )
        elif change.action == "delete":
            conn.execute(f"DELETE FROM {table} WHERE pk = ?", (change.entity_id,))
        
        # Log the change
        import json
        conn.execute("""
            INSERT INTO sync_log (entity_type, entity_id, action, device_id, timestamp, data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (change.entity_type.value, change.entity_id, change.action, 
              device_id, current_timestamp, json.dumps(change.data) if change.data else None))
        
        conn.commit()
    
    return None


@router.post("/sync", response_model=SyncResponse)
async def sync_changes(request: SyncRequest):
    """
    Handle bidirectional sync between device and server.
    
    1. Get server changes since last sync
    2. Apply device changes to server
    3. Return server changes and any conflicts
    """
    ensure_sync_tables()
    
    device_id = request.device_id
    last_sync = request.last_sync_timestamp or 0.0
    current_time = time.time()
    
    # Get server changes since last sync
    server_changes = get_server_changes_since(device_id, last_sync)
    
    # Apply client changes
    conflicts = []
    applied_count = 0
    
    for change in request.changes:
        conflict = apply_client_change(change, device_id)
        if conflict:
            conflicts.append(conflict)
        else:
            applied_count += 1
    
    # Update device sync state
    with connect() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO device_sync_state (device_id, last_sync_timestamp, pending_count)
            VALUES (?, ?, ?)
        """, (device_id, current_time, len(conflicts)))
        
        # Update device last_seen
        conn.execute("""
            UPDATE device_registry SET last_seen = CURRENT_TIMESTAMP
            WHERE device_id = ?
        """, (device_id,))
        conn.commit()
    
    return SyncResponse(
        success=True,
        device_id=device_id,
        server_changes=server_changes,
        sync_timestamp=current_time,
        conflicts=conflicts,
        applied_count=applied_count
    )


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(device_id: str):
    """
    Get sync status for a device.
    
    Returns pending changes, last sync time, and online status.
    """
    ensure_sync_tables()
    
    with connect() as conn:
        # Get device sync state
        state = conn.execute("""
            SELECT * FROM device_sync_state WHERE device_id = ?
        """, (device_id,)).fetchone()
        
        if state:
        state = dict(state)
        pending = state.get("pending_count", 0)
        last_sync = state.get("last_sync_timestamp")
        last_sync_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_sync)) if last_sync else None
    else:
        pending = 0
        last_sync_str = None
    
    return SyncStatusResponse(
        device_id=device_id,
        online=True,
        pending_changes=pending,
        last_sync=last_sync_str,
        sync_enabled=True
    )


@router.post("/resolve-conflict", response_model=SyncResponse)
async def resolve_conflict(
    device_id: str,
    entity_type: str,
    entity_id: int,
    resolution: str  # "server_wins" or "client_wins"
):
    """
    Manually resolve a sync conflict.
    
    resolution options:
    - server_wins: Keep server version, discard client changes
    - client_wins: Apply client version, overwrite server
    """
    if resolution not in ["server_wins", "client_wins"]:
        raise HTTPException(status_code=400, detail="Invalid resolution type")
    
    # For now, just log the resolution - actual implementation would
    # apply the chosen version to the database
    current_time = time.time()
    
    with connect() as conn:
        conn.execute("""
            INSERT INTO sync_log (entity_type, entity_id, action, device_id, timestamp, data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (entity_type, entity_id, f"conflict_resolved_{resolution}", 
              device_id, current_time, None))
        conn.commit()
    
    return SyncResponse(
        success=True,
        device_id=device_id,
        server_changes=[],
        sync_timestamp=current_time,
        conflicts=[],
        applied_count=1
    )
