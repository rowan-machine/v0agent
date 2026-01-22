# src/app/api/admin.py
"""
Admin API endpoints for system management.

Phase 4.1: Database migration management.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/admin", tags=["admin"])


class MigrationInfo(BaseModel):
    """Schema for a single migration."""
    version: str
    description: str
    applied: bool
    applied_at: str | None = None


class MigrationStatusResponse(BaseModel):
    """Schema for migration status response."""
    total_migrations: int
    applied_count: int
    pending_count: int
    migrations: List[MigrationInfo]


@router.get("/migrations", response_model=MigrationStatusResponse)
def get_migrations():
    """
    Get database migration status.
    
    Returns list of all migrations with their applied status.
    Useful for debugging and monitoring infrastructure state.
    """
    from ..db_migrations import get_migration_status
    
    status = get_migration_status()
    
    # Transform to response format
    migrations = []
    for m in status["migrations"]:
        migrations.append(MigrationInfo(
            version=m["version"],
            description=m["description"],
            applied=m["applied"],
            applied_at=m.get("applied_at")
        ))
    
    return MigrationStatusResponse(
        total_migrations=status["total"],
        applied_count=status["applied_count"],
        pending_count=len(status["pending"]),
        migrations=migrations
    )


class RunMigrationsResponse(BaseModel):
    """Schema for run migrations response."""
    applied: int
    skipped: int
    details: List[str]


@router.post("/migrations/run", response_model=RunMigrationsResponse)
def run_migrations():
    """
    Run pending database migrations.
    
    Executes all unapplied migrations in order.
    Safe to call multiple times - already applied migrations are skipped.
    """
    from ..db_migrations import run_all_migrations
    
    result = run_all_migrations()
    
    return RunMigrationsResponse(
        applied=result["applied"],
        skipped=result["skipped"],
        details=result.get("details", [])
    )


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    database: str
    migrations_pending: int
    version: str
    infrastructure: dict | None = None


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    System health check endpoint.
    
    Returns overall system status including database and migration state.
    """
    from ..db_migrations import get_migration_status
    from ..db import connect
    
    # Check database
    db_status = "ok"
    try:
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Check migrations
    migration_status = get_migration_status()
    
    # Check infrastructure components
    infra_status = {}
    try:
        from ..infrastructure import get_task_queue, get_cache, get_rate_limiter
        
        queue = get_task_queue()
        infra_status["task_queue"] = "redis" if queue.is_redis_available else "fallback"
        
        cache = get_cache()
        infra_status["cache"] = "redis" if cache.is_redis_available else "memory"
        
        limiter = get_rate_limiter()
        infra_status["rate_limiter"] = "redis" if limiter.is_redis_available else "memory"
        
        from ..infrastructure import get_supabase_client
        supabase = get_supabase_client()
        infra_status["supabase"] = "connected" if supabase else "not_configured"
    except Exception as e:
        infra_status["error"] = str(e)
    
    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        database=db_status,
        migrations_pending=len(migration_status["pending"]),
        version="2.0.0-phase4",
        infrastructure=infra_status
    )


class InfrastructureStatusResponse(BaseModel):
    """Schema for infrastructure status response."""
    task_queue: dict
    cache: dict
    rate_limiter: dict
    mdns: dict
    supabase: dict


@router.get("/infrastructure", response_model=InfrastructureStatusResponse)
def get_infrastructure_status():
    """
    Get detailed infrastructure component status.
    
    Returns status of all Phase 4 infrastructure components:
    - Task queue (RQ/Redis)
    - Cache (Redis/Memory)
    - Rate limiter
    - mDNS discovery
    - Supabase connection
    """
    from ..infrastructure import (
        get_task_queue,
        get_cache,
        get_rate_limiter,
        get_mdns_discovery,
        get_supabase_client,
    )
    
    # Task queue
    queue = get_task_queue()
    task_queue_status = {
        "mode": "redis" if queue.is_redis_available else "fallback",
        "pending_jobs": len(queue.get_pending_jobs()),
    }
    
    # Cache
    cache = get_cache()
    cache_status = cache.get_stats()
    
    # Rate limiter
    limiter = get_rate_limiter()
    rate_limiter_status = {
        "mode": "redis" if limiter.is_redis_available else "memory",
    }
    
    # mDNS
    mdns = get_mdns_discovery()
    mdns_status = {
        "running": mdns.is_running,
        "devices_discovered": mdns.device_count,
    }
    
    # Supabase
    supabase = get_supabase_client()
    supabase_status = {
        "connected": supabase is not None,
    }
    
    return InfrastructureStatusResponse(
        task_queue=task_queue_status,
        cache=cache_status,
        rate_limiter=rate_limiter_status,
        mdns=mdns_status,
        supabase=supabase_status,
    )


class SyncRequest(BaseModel):
    """Request for data sync."""
    tables: List[str] | None = None  # None = all tables
    direction: str = "sqlite_to_supabase"  # or "supabase_to_sqlite"


class SyncResponse(BaseModel):
    """Response from data sync."""
    status: str
    synced: dict
    errors: List[str]


@router.post("/sync", response_model=SyncResponse)
async def sync_data(request: SyncRequest):
    """
    Sync data between SQLite and Supabase.
    
    By default syncs all tables from SQLite to Supabase.
    Can specify specific tables or reverse direction.
    """
    from ..infrastructure import get_supabase_sync
    from ..db import connect
    
    sync = get_supabase_sync()
    
    if not sync.is_available:
        return SyncResponse(
            status="error",
            synced={},
            errors=["Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY."]
        )
    
    tables = request.tables or ["meetings", "documents", "tickets", "dikw_items"]
    synced = {}
    errors = []
    
    try:
        with connect() as conn:
            for table in tables:
                try:
                    if table == "meetings":
                        rows = conn.execute("SELECT * FROM meeting_summaries").fetchall()
                        count = 0
                        for row in rows:
                            result = await sync.sync_meeting(dict(row))
                            if result:
                                count += 1
                        synced["meetings"] = count
                        
                    elif table == "documents":
                        rows = conn.execute("SELECT * FROM docs").fetchall()
                        count = 0
                        for row in rows:
                            result = await sync.sync_document(dict(row))
                            if result:
                                count += 1
                        synced["documents"] = count
                        
                    elif table == "tickets":
                        rows = conn.execute("SELECT * FROM tickets").fetchall()
                        count = 0
                        for row in rows:
                            result = await sync.sync_ticket(dict(row))
                            if result:
                                count += 1
                        synced["tickets"] = count
                        
                    elif table == "dikw_items":
                        rows = conn.execute("SELECT * FROM dikw_items").fetchall()
                        count = 0
                        for row in rows:
                            result = await sync.sync_dikw_item(dict(row))
                            if result:
                                count += 1
                        synced["dikw_items"] = count
                        
                except Exception as e:
                    errors.append(f"{table}: {str(e)}")
                    
    except Exception as e:
        errors.append(f"Database error: {str(e)}")
    
    return SyncResponse(
        status="completed" if not errors else "partial",
        synced=synced,
        errors=errors
    )
