# src/app/domains/knowledge_graph/api/models.py
"""
Knowledge Graph API Models

Pydantic models for knowledge graph requests and responses.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class EntityRef(BaseModel):
    """Reference to an entity in the knowledge graph."""
    entity_type: str = Field(..., pattern="^(meeting|document|ticket|dikw|signal)$")
    entity_id: int


class LinkCreate(BaseModel):
    """Request to create a link between two entities."""
    source_type: str = Field(..., pattern="^(meeting|document|ticket|dikw|signal)$")
    source_id: int
    target_type: str = Field(..., pattern="^(meeting|document|ticket|dikw|signal)$")
    target_id: int
    link_type: str = Field(
        "related",
        pattern="^(semantic_similar|related|derived_from|referenced|same_topic|blocks|depends_on)$"
    )
    similarity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    is_bidirectional: bool = True
    metadata: Optional[dict] = None
    created_by: str = Field("user", pattern="^(system|user|ai)$")


class LinkResponse(BaseModel):
    """Response for a single link."""
    id: int
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    link_type: str
    similarity_score: Optional[float] = None
    confidence: float
    is_bidirectional: bool
    metadata: Optional[dict] = None
    created_by: str
    created_at: str


class LinkedEntity(BaseModel):
    """An entity linked to the query entity."""
    entity_type: str
    entity_id: int
    title: str
    snippet: str
    link_type: str
    link_direction: str  # "outgoing" | "incoming" | "both"
    similarity_score: Optional[float] = None
    confidence: float


class GraphQueryResponse(BaseModel):
    """Response for graph queries."""
    entity: EntityRef
    entity_title: str
    links: List[LinkedEntity]
    total_links: int


class GraphStatsResponse(BaseModel):
    """Graph statistics response."""
    total_links: int
    links_by_type: dict
    entities_with_links: dict
    avg_links_per_entity: float
