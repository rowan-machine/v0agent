# src/app/api/v1/dikw.py
"""
API v1 - DIKW Knowledge Pyramid endpoints.

RESTful endpoints for DIKW (Data-Information-Knowledge-Wisdom)
pyramid operations with proper pagination and HTTP semantics.

Uses service layer for data access (DDD compliant).
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class DIKWLevel(str, Enum):
    DATA = "data"
    INFORMATION = "information"
    KNOWLEDGE = "knowledge"
    WISDOM = "wisdom"


class DIKWItemResponse(BaseModel):
    """Response model for a DIKW item."""
    id: int
    level: DIKWLevel
    content: str
    summary: Optional[str] = None
    tags: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0, le=1)
    status: str = "active"
    source_meeting_id: Optional[str] = None
    parent_id: Optional[int] = None
    created_at: Optional[str] = None
    promoted_at: Optional[str] = None


class DIKWItemCreate(BaseModel):
    """Request model for creating a DIKW item."""
    level: DIKWLevel
    content: str
    summary: Optional[str] = None
    tags: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0, le=1)
    source_meeting_id: Optional[str] = None
    parent_id: Optional[int] = None


class DIKWPyramidResponse(BaseModel):
    """Response model for the full DIKW pyramid."""
    pyramid: Dict[str, List[DIKWItemResponse]]
    counts: Dict[str, int]


class DIKWListResponse(BaseModel):
    """Response model for paginated DIKW items."""
    items: List[DIKWItemResponse]
    total: int
    skip: int
    limit: int


# =============================================================================
# SERVICE LAYER ACCESS (DDD Compliant)
# =============================================================================

def _get_dikw_repository():
    """Get DIKW repository (lazy import for DDD compliance)."""
    from ...adapters.database.supabase import SupabaseDatabaseAdapter, SupabaseDIKWRepository
    db = SupabaseDatabaseAdapter()
    return SupabaseDIKWRepository(db)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=DIKWListResponse)
async def list_dikw_items(
    level: Optional[DIKWLevel] = Query(None, description="Filter by DIKW level"),
    status: str = Query("active", description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
):
    """
    List DIKW items with optional filters.
    
    Returns items ordered by most recently created first.
    """
    try:
        repo = _get_dikw_repository()
        
        items = repo.get_items(
            level=level.value if level else None,
            status=status,
            limit=limit + skip  # Fetch enough for pagination
        )
        
        # Apply pagination
        paginated = items[skip:skip + limit] if items else []
        
        return DIKWListResponse(
            items=[DIKWItemResponse(**item) for item in paginated],
            total=len(items or []),
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Failed to list DIKW items: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch DIKW items")


@router.get("/pyramid", response_model=DIKWPyramidResponse)
async def get_dikw_pyramid():
    """
    Get the full DIKW pyramid structure.
    
    Returns all active items organized by level.
    """
    try:
        repo = _get_dikw_repository()
        pyramid_raw = repo.get_pyramid()
        
        pyramid = {}
        counts = {}
        
        for level, items in pyramid_raw.items():
            pyramid[level] = [
                DIKWItemResponse(
                    id=item["id"],
                    level=DIKWLevel(level),
                    content=item.get("content", "")[:500],
                    summary=item.get("summary"),
                    tags=item.get("tags"),
                    confidence=item.get("confidence", 0.7),
                    status=item.get("status", "active"),
                    created_at=item.get("created_at"),
                )
                for item in items
            ]
            counts[level] = len(items)
        
        return DIKWPyramidResponse(pyramid=pyramid, counts=counts)
    except Exception as e:
        logger.error(f"Failed to get DIKW pyramid: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch DIKW pyramid")


@router.get("/{item_id}", response_model=DIKWItemResponse)
async def get_dikw_item(item_id: int):
    """
    Get a single DIKW item by ID.
    
    Returns 404 if item not found.
    """
    try:
        repo = _get_dikw_repository()
        item = repo.get_item(item_id)
        
        if not item:
            raise HTTPException(status_code=404, detail="DIKW item not found")
        
        return DIKWItemResponse(**item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get DIKW item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch DIKW item")


@router.post("", response_model=DIKWItemResponse, status_code=201)
async def create_dikw_item(item: DIKWItemCreate):
    """
    Create a new DIKW item.
    
    Returns the created item with generated ID.
    """
    try:
        repo = _get_dikw_repository()
        
        data = {
            "level": item.level.value,
            "content": item.content,
            "summary": item.summary,
            "tags": item.tags,
            "confidence": item.confidence,
            "status": "active",
        }
        
        if item.source_meeting_id:
            data["source_meeting_id"] = item.source_meeting_id
        if item.parent_id:
            data["parent_id"] = item.parent_id
        
        created = repo.create_item(data)
        
        if not created:
            raise HTTPException(status_code=500, detail="Failed to create DIKW item")
        
        return DIKWItemResponse(**created)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create DIKW item: {e}")
        raise HTTPException(status_code=500, detail="Failed to create DIKW item")


@router.patch("/{item_id}", response_model=DIKWItemResponse)
async def update_dikw_item(item_id: int, updates: Dict[str, Any]):
    """
    Update a DIKW item.
    
    Supports partial updates. Returns the updated item.
    """
    try:
        repo = _get_dikw_repository()
        
        # Verify item exists
        existing = repo.get_item(item_id)
        if not existing:
            raise HTTPException(status_code=404, detail="DIKW item not found")
        
        # Filter allowed update fields
        allowed_fields = {"content", "summary", "tags", "confidence", "status"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        updated = repo.update_item(item_id, filtered_updates)
        
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update DIKW item")
        
        return DIKWItemResponse(**updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update DIKW item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update DIKW item")


@router.post("/{item_id}/promote", response_model=DIKWItemResponse)
async def promote_dikw_item(item_id: int, to_level: DIKWLevel):
    """
    Promote a DIKW item to a higher level.
    
    Validates that promotion is to a higher level.
    """
    level_order = ["data", "information", "knowledge", "wisdom"]
    
    try:
        repo = _get_dikw_repository()
        
        # Get current item
        item = repo.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="DIKW item not found")
        
        current_level = item.get("level", "data")
        current_idx = level_order.index(current_level)
        target_idx = level_order.index(to_level.value)
        
        if target_idx <= current_idx:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot promote from {current_level} to {to_level.value}"
            )
        
        promoted = repo.promote_item(item_id, to_level.value)
        
        if not promoted:
            raise HTTPException(status_code=500, detail="Failed to promote DIKW item")
        
        return DIKWItemResponse(**promoted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to promote DIKW item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to promote DIKW item")


@router.delete("/{item_id}", status_code=204)
async def delete_dikw_item(item_id: int):
    """
    Delete (soft-delete) a DIKW item.
    
    Sets status to 'deleted' rather than removing the record.
    """
    try:
        repo = _get_dikw_repository()
        
        # Verify item exists
        item = repo.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="DIKW item not found")
        
        success = repo.delete_item(item_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete DIKW item")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete DIKW item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete DIKW item")
