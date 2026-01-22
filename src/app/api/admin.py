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
        applied_count=status["applied"],
        pending_count=status["pending"],
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
    
    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        database=db_status,
        migrations_pending=migration_status["pending"],
        version="2.0.0-phase4"  # Update as we progress
    )
