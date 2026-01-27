# src/app/repositories/dikw_repository.py
"""
DIKW Repository - Ports and Adapters

Port: DIKWRepository (abstract interface)
Adapters: SupabaseDIKWRepository

Covers DIKW-related tables:
- dikw_items (33 calls across API)
- dikw_evolution (history tracking)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

DIKW_LEVELS = ["data", "information", "knowledge", "wisdom"]
DIKW_NEXT_LEVEL = {
    "data": "information",
    "information": "knowledge",
    "knowledge": "wisdom"
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DIKWItem:
    """DIKW item domain entity."""
    id: Optional[int] = None
    level: str = "data"
    content: str = ""
    summary: Optional[str] = None
    tags: Optional[str] = None
    meeting_id: Optional[str] = None
    source_type: str = "manual"
    original_signal_type: Optional[str] = None
    confidence: int = 50
    validation_count: int = 0
    status: str = "active"
    parent_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Optional joined fields
    meeting_name: Optional[str] = None
    meeting_date: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DIKWItem":
        """Create from dictionary."""
        return cls(
            id=data.get("id"),
            level=data.get("level", "data"),
            content=data.get("content", ""),
            summary=data.get("summary"),
            tags=data.get("tags"),
            meeting_id=data.get("meeting_id"),
            source_type=data.get("source_type", "manual"),
            original_signal_type=data.get("original_signal_type"),
            confidence=data.get("confidence", 50),
            validation_count=data.get("validation_count", 0),
            status=data.get("status", "active"),
            parent_id=data.get("parent_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            meeting_name=data.get("meeting_name"),
            meeting_date=data.get("meeting_date"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage (excludes joined fields)."""
        return {
            "level": self.level,
            "content": self.content,
            "summary": self.summary,
            "tags": self.tags,
            "meeting_id": self.meeting_id,
            "source_type": self.source_type,
            "original_signal_type": self.original_signal_type,
            "confidence": self.confidence,
            "validation_count": self.validation_count,
            "status": self.status,
            "parent_id": self.parent_id,
        }


@dataclass
class DIKWEvolution:
    """DIKW evolution/history domain entity."""
    id: Optional[int] = None
    item_id: int = 0
    action: str = ""
    previous_level: Optional[str] = None
    new_level: Optional[str] = None
    previous_content: Optional[str] = None
    new_content: Optional[str] = None
    actor: str = "system"
    reason: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DIKWEvolution":
        return cls(
            id=data.get("id"),
            item_id=data.get("item_id", 0),
            action=data.get("action", ""),
            previous_level=data.get("previous_level"),
            new_level=data.get("new_level"),
            previous_content=data.get("previous_content"),
            new_content=data.get("new_content"),
            actor=data.get("actor", "system"),
            reason=data.get("reason"),
            created_at=data.get("created_at"),
        )


@dataclass 
class DIKWPyramid:
    """DIKW pyramid view with counts per level."""
    data: List[DIKWItem] = field(default_factory=list)
    information: List[DIKWItem] = field(default_factory=list)
    knowledge: List[DIKWItem] = field(default_factory=list)
    wisdom: List[DIKWItem] = field(default_factory=list)

    @property
    def counts(self) -> Dict[str, int]:
        """Get count per level."""
        return {
            "data": len(self.data),
            "information": len(self.information),
            "knowledge": len(self.knowledge),
            "wisdom": len(self.wisdom),
        }

    def to_dict(self) -> Dict[str, List[Dict]]:
        """Convert to dictionary format."""
        return {
            "data": [i.__dict__ for i in self.data],
            "information": [i.__dict__ for i in self.information],
            "knowledge": [i.__dict__ for i in self.knowledge],
            "wisdom": [i.__dict__ for i in self.wisdom],
        }


# =============================================================================
# PORT (Abstract Interface)
# =============================================================================

class DIKWRepository(ABC):
    """
    DIKW Repository Port - defines the interface for DIKW data access.
    """

    # Item CRUD operations
    @abstractmethod
    def get_items(
        self,
        level: Optional[str] = None,
        status: str = "active",
        limit: int = 100
    ) -> List[DIKWItem]:
        """Get DIKW items with optional filtering."""
        pass

    @abstractmethod
    def get_pyramid(self, status: str = "active") -> DIKWPyramid:
        """Get all items grouped by level as a pyramid view."""
        pass

    @abstractmethod
    def get_by_id(self, item_id: int) -> Optional[DIKWItem]:
        """Get a single item by ID."""
        pass

    @abstractmethod
    def get_by_ids(self, item_ids: List[int]) -> List[DIKWItem]:
        """Get multiple items by IDs."""
        pass

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Optional[DIKWItem]:
        """Create a new DIKW item."""
        pass

    @abstractmethod
    def update(self, item_id: int, data: Dict[str, Any]) -> Optional[DIKWItem]:
        """Update an existing item."""
        pass

    @abstractmethod
    def delete(self, item_id: int, soft: bool = True) -> bool:
        """Delete an item (soft delete by default)."""
        pass

    # Promotion operations
    @abstractmethod
    def promote(self, item_id: int, reason: Optional[str] = None) -> Optional[DIKWItem]:
        """Promote item to next level."""
        pass

    @abstractmethod
    def validate(self, item_id: int) -> bool:
        """Increment validation count and potentially auto-promote."""
        pass

    # Merge/synthesis operations
    @abstractmethod
    def merge(
        self,
        item_ids: List[int],
        merged_content: str,
        merged_summary: str,
        target_level: str
    ) -> Optional[DIKWItem]:
        """Merge multiple items into one."""
        pass

    # Tag operations
    @abstractmethod
    def get_items_without_tags(self) -> List[DIKWItem]:
        """Get items that need tag generation."""
        pass

    @abstractmethod
    def update_tags(self, item_id: int, tags: str) -> bool:
        """Update tags for an item."""
        pass

    # Evolution/history operations
    @abstractmethod
    def get_history(self, item_id: int) -> List[DIKWEvolution]:
        """Get evolution history for an item."""
        pass

    @abstractmethod
    def record_evolution(self, data: Dict[str, Any]) -> Optional[DIKWEvolution]:
        """Record an evolution event."""
        pass

    # Search operations
    @abstractmethod
    def search(
        self,
        query: str,
        level: Optional[str] = None,
        limit: int = 20
    ) -> List[DIKWItem]:
        """Search items by content."""
        pass


# =============================================================================
# SUPABASE ADAPTER
# =============================================================================

class SupabaseDIKWRepository(DIKWRepository):
    """Supabase adapter for DIKW repository."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from ..infrastructure.supabase_client import get_supabase_client
            self._client = get_supabase_client()
        return self._client

    def _normalize_signal_type(self, signal_type: str) -> str:
        """Normalize signal type to standard format."""
        if not signal_type:
            return signal_type
        mapping = {
            "action_items": "action_item",
            "action-items": "action_item",
            "actions": "action_item",
            "decisions": "decision",
            "blockers": "blocker",
            "risks": "risk",
            "ideas": "idea",
            "insights": "insight",
        }
        return mapping.get(signal_type.lower(), signal_type)

    def _enrich_with_meeting(self, items: List[Dict]) -> List[DIKWItem]:
        """Enrich items with meeting name and date."""
        if not items or not self.client:
            return [DIKWItem.from_dict(i) for i in items]

        # Get unique meeting IDs
        meeting_ids = list(set(
            i["meeting_id"] for i in items 
            if i.get("meeting_id")
        ))
        
        meetings_map = {}
        if meeting_ids:
            try:
                result = self.client.table("meetings").select(
                    "id, meeting_name, meeting_date"
                ).in_("id", meeting_ids).execute()
                meetings_map = {m["id"]: m for m in (result.data or [])}
            except Exception as e:
                logger.warning(f"Failed to get meeting data: {e}")

        # Enrich items
        enriched = []
        for item in items:
            item_dict = dict(item)
            if item.get("meeting_id") and item["meeting_id"] in meetings_map:
                meeting = meetings_map[item["meeting_id"]]
                item_dict["meeting_name"] = meeting.get("meeting_name")
                item_dict["meeting_date"] = meeting.get("meeting_date")
            if item_dict.get("original_signal_type"):
                item_dict["original_signal_type"] = self._normalize_signal_type(
                    item_dict["original_signal_type"]
                )
            enriched.append(DIKWItem.from_dict(item_dict))
        
        return enriched

    # -------------------------------------------------------------------------
    # Item CRUD operations
    # -------------------------------------------------------------------------

    def get_items(
        self,
        level: Optional[str] = None,
        status: str = "active",
        limit: int = 100
    ) -> List[DIKWItem]:
        """Get DIKW items with optional filtering."""
        if not self.client:
            logger.warning("Supabase not available")
            return []

        try:
            query = self.client.table("dikw_items").select("*").eq("status", status)
            if level:
                query = query.eq("level", level)
            query = query.order("created_at", desc=True).limit(limit)
            result = query.execute()
            return self._enrich_with_meeting(result.data or [])
        except Exception as e:
            logger.error(f"Failed to get DIKW items: {e}")
            return []

    def get_pyramid(self, status: str = "active") -> DIKWPyramid:
        """Get all items grouped by level."""
        items = self.get_items(status=status)
        pyramid = DIKWPyramid()
        
        for item in items:
            if item.level == "data":
                pyramid.data.append(item)
            elif item.level == "information":
                pyramid.information.append(item)
            elif item.level == "knowledge":
                pyramid.knowledge.append(item)
            elif item.level == "wisdom":
                pyramid.wisdom.append(item)
        
        return pyramid

    def get_by_id(self, item_id: int) -> Optional[DIKWItem]:
        """Get a single item by ID."""
        if not self.client:
            return None

        try:
            result = self.client.table("dikw_items").select("*").eq(
                "id", item_id
            ).execute()
            if result.data:
                items = self._enrich_with_meeting(result.data)
                return items[0] if items else None
            return None
        except Exception as e:
            logger.error(f"Failed to get DIKW item {item_id}: {e}")
            return None

    def get_by_ids(self, item_ids: List[int]) -> List[DIKWItem]:
        """Get multiple items by IDs."""
        if not self.client or not item_ids:
            return []

        try:
            result = self.client.table("dikw_items").select("*").in_(
                "id", item_ids
            ).execute()
            return self._enrich_with_meeting(result.data or [])
        except Exception as e:
            logger.error(f"Failed to get DIKW items by IDs: {e}")
            return []

    def create(self, data: Dict[str, Any]) -> Optional[DIKWItem]:
        """Create a new DIKW item."""
        if not self.client:
            return None

        try:
            # Set defaults
            insert_data = {
                "level": data.get("level", "data"),
                "content": data.get("content", ""),
                "summary": data.get("summary") or data.get("content", "")[:200],
                "tags": data.get("tags"),
                "meeting_id": data.get("meeting_id"),
                "source_type": data.get("source_type", "manual"),
                "original_signal_type": data.get("original_signal_type"),
                "validation_count": data.get("validation_count", 1),
                "confidence": data.get("confidence", 70),
                "status": "active",
            }
            
            result = self.client.table("dikw_items").insert(insert_data).execute()
            if result.data:
                return DIKWItem.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to create DIKW item: {e}")
            return None

    def update(self, item_id: int, data: Dict[str, Any]) -> Optional[DIKWItem]:
        """Update an existing item."""
        if not self.client:
            return None

        try:
            data["updated_at"] = datetime.now().isoformat()
            result = self.client.table("dikw_items").update(data).eq(
                "id", item_id
            ).execute()
            if result.data:
                return DIKWItem.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to update DIKW item {item_id}: {e}")
            return None

    def delete(self, item_id: int, soft: bool = True) -> bool:
        """Delete an item (soft delete by default)."""
        if not self.client:
            return False

        try:
            if soft:
                self.client.table("dikw_items").update(
                    {"status": "archived"}
                ).eq("id", item_id).execute()
            else:
                self.client.table("dikw_items").delete().eq("id", item_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete DIKW item {item_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Promotion operations
    # -------------------------------------------------------------------------

    def promote(self, item_id: int, reason: Optional[str] = None) -> Optional[DIKWItem]:
        """Promote item to next level."""
        if not self.client:
            return None

        try:
            # Get current item
            item = self.get_by_id(item_id)
            if not item:
                return None

            # Check if can promote
            next_level = DIKW_NEXT_LEVEL.get(item.level)
            if not next_level:
                logger.warning(f"Cannot promote item at level {item.level}")
                return item

            # Update level
            updated = self.update(item_id, {"level": next_level})
            
            # Record evolution
            if updated:
                self.record_evolution({
                    "item_id": item_id,
                    "action": "promoted",
                    "previous_level": item.level,
                    "new_level": next_level,
                    "reason": reason,
                })
            
            return updated
        except Exception as e:
            logger.error(f"Failed to promote DIKW item {item_id}: {e}")
            return None

    def validate(self, item_id: int) -> bool:
        """Increment validation count and potentially auto-promote."""
        if not self.client:
            return False

        try:
            # Get current counts
            result = self.client.table("dikw_items").select(
                "validation_count, confidence, level"
            ).eq("id", item_id).execute()
            
            if not result.data:
                return False

            current = result.data[0]
            new_count = (current.get("validation_count") or 0) + 1
            new_confidence = min(100, (current.get("confidence") or 50) + 10)
            
            # Update
            self.client.table("dikw_items").update({
                "validation_count": new_count,
                "confidence": new_confidence,
            }).eq("id", item_id).execute()

            # Check for auto-promotion (3+ validations at 80+ confidence)
            if new_count >= 3 and new_confidence >= 80:
                current_level = current.get("level", "data")
                if current_level in DIKW_NEXT_LEVEL:
                    self.promote(item_id, reason="Auto-promoted due to high validation")

            return True
        except Exception as e:
            logger.error(f"Failed to validate DIKW item {item_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Merge/synthesis operations
    # -------------------------------------------------------------------------

    def merge(
        self,
        item_ids: List[int],
        merged_content: str,
        merged_summary: str,
        target_level: str
    ) -> Optional[DIKWItem]:
        """Merge multiple items into one."""
        if not self.client or not item_ids:
            return None

        try:
            # Get source items
            source_items = self.get_by_ids(item_ids)
            if not source_items:
                return None

            # Create merged item
            merged = self.create({
                "level": target_level,
                "content": merged_content,
                "summary": merged_summary,
                "source_type": "merged",
                "confidence": 75,
                "validation_count": 1,
            })

            if merged:
                # Archive source items
                for item_id in item_ids:
                    self.client.table("dikw_items").update({
                        "status": "merged",
                        "parent_id": merged.id,
                    }).eq("id", item_id).execute()
                
                # Record evolution
                self.record_evolution({
                    "item_id": merged.id,
                    "action": "merged",
                    "new_level": target_level,
                    "reason": f"Merged from items: {item_ids}",
                })

            return merged
        except Exception as e:
            logger.error(f"Failed to merge DIKW items: {e}")
            return None

    # -------------------------------------------------------------------------
    # Tag operations
    # -------------------------------------------------------------------------

    def get_items_without_tags(self) -> List[DIKWItem]:
        """Get items that need tag generation."""
        if not self.client:
            return []

        try:
            # Get items with null tags
            result1 = self.client.table("dikw_items").select(
                "id, content, level, original_signal_type"
            ).is_("tags", "null").execute()
            
            # Get items with empty tags
            result2 = self.client.table("dikw_items").select(
                "id, content, level, original_signal_type"
            ).eq("tags", "").execute()

            items = (result1.data or []) + (result2.data or [])
            return [DIKWItem.from_dict(i) for i in items]
        except Exception as e:
            logger.error(f"Failed to get items without tags: {e}")
            return []

    def update_tags(self, item_id: int, tags: str) -> bool:
        """Update tags for an item."""
        if not self.client:
            return False

        try:
            self.client.table("dikw_items").update(
                {"tags": tags}
            ).eq("id", item_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update tags for item {item_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Evolution/history operations
    # -------------------------------------------------------------------------

    def get_history(self, item_id: int) -> List[DIKWEvolution]:
        """Get evolution history for an item."""
        if not self.client:
            return []

        try:
            result = self.client.table("dikw_evolution").select("*").eq(
                "item_id", item_id
            ).order("created_at", desc=True).execute()
            return [DIKWEvolution.from_dict(e) for e in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get history for item {item_id}: {e}")
            return []

    def record_evolution(self, data: Dict[str, Any]) -> Optional[DIKWEvolution]:
        """Record an evolution event."""
        if not self.client:
            return None

        try:
            result = self.client.table("dikw_evolution").insert(data).execute()
            if result.data:
                return DIKWEvolution.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to record evolution: {e}")
            return None

    # -------------------------------------------------------------------------
    # Search operations
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        level: Optional[str] = None,
        limit: int = 20
    ) -> List[DIKWItem]:
        """Search items by content (basic text search)."""
        if not self.client:
            return []

        try:
            db_query = self.client.table("dikw_items").select("*").eq(
                "status", "active"
            ).ilike("content", f"%{query}%")
            
            if level:
                db_query = db_query.eq("level", level)
            
            db_query = db_query.limit(limit)
            result = db_query.execute()
            return self._enrich_with_meeting(result.data or [])
        except Exception as e:
            logger.error(f"Failed to search DIKW items: {e}")
            return []


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_dikw_repository() -> DIKWRepository:
    """Get the DIKW repository (Supabase adapter)."""
    return SupabaseDIKWRepository()
