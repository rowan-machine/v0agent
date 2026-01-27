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
from ...infrastructure.supabase_client import get_supabase_client

router = APIRouter()


def ensure_sync_tables():
    """Ensure sync-related tables exist.
    
    Note: Tables are pre-created in Supabase via migrations.
    This function is kept for backwards compatibility.
    """
    pass  # Table creation handled by Supabase migrations


def get_server_changes_since(device_id: str, since_timestamp: float) -> List[Dict[str, Any]]:
    """Get all changes on server since timestamp, excluding device's own changes."""
    supabase = get_supabase_client()
    result = supabase.table("sync_log").select("*").gt("timestamp", since_timestamp).neq("device_id", device_id).order("timestamp").execute()
    
    return result.data or []


def apply_client_change(change: SyncChange, device_id: str) -> Optional[SyncConflict]:
    """
    Apply a single client change to the server.
    
    Returns SyncConflict if conflict detected, None otherwise.
    """
    import json
    current_timestamp = time.time()
    
    supabase = get_supabase_client()
    
    # Check for conflict - is there a newer server change for same entity?
    result = supabase.table("sync_log").select("*").eq("entity_type", change.entity_type.value).eq("entity_id", change.entity_id).gt("timestamp", change.local_timestamp).order("timestamp", desc=True).limit(1).execute()
    
    if result.data:
        # Conflict detected - server has newer change
        server_change = result.data[0]
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
        supabase.table(table).insert(change.data).execute()
    elif change.action == "update" and change.data:
        # Update existing record
        supabase.table(table).update(change.data).eq("pk", change.entity_id).execute()
    elif change.action == "delete":
        supabase.table(table).delete().eq("pk", change.entity_id).execute()
    
    # Log the change
    supabase.table("sync_log").insert({
        "entity_type": change.entity_type.value,
        "entity_id": change.entity_id,
        "action": change.action,
        "device_id": device_id,
        "timestamp": current_timestamp,
        "data": json.dumps(change.data) if change.data else None
    }).execute()
    
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
    supabase = get_supabase_client()
    supabase.table("device_sync_state").upsert({
        "device_id": device_id,
        "last_sync_timestamp": current_time,
        "pending_count": len(conflicts)
    }).execute()
    
    # Update device last_seen
    from datetime import datetime, timezone
    supabase.table("device_registry").update({"last_seen": datetime.now(timezone.utc).isoformat()}).eq("device_id", device_id).execute()
    
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
    
    supabase = get_supabase_client()
    result = supabase.table("device_sync_state").select("*").eq("device_id", device_id).execute()
    
    if result.data:
        state = result.data[0]
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
    
    supabase = get_supabase_client()
    supabase.table("sync_log").insert({
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": f"conflict_resolved_{resolution}",
        "device_id": device_id,
        "timestamp": current_time,
        "data": None
    }).execute()
    
    return SyncResponse(
        success=True,
        device_id=device_id,
        server_changes=[],
        sync_timestamp=current_time,
        conflicts=[],
        applied_count=1
    )
