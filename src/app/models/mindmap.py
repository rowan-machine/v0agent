"""
Pydantic models for Mindmap data structures.

Provides typed data structures for mindmap nodes, hierarchies,
and synthesis results with full hierarchy support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class MindmapNode(BaseModel):
    """Single node in a mindmap with hierarchy information."""
    id: str
    title: str
    level: int = 0  # Hierarchy level (0 = root)
    depth: int = 0  # Calculated depth from root
    parent_id: Optional[str] = None
    children_ids: List[str] = Field(default_factory=list)
    content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[int] = None
    mindmap_id: Optional[int] = None


class MindmapEdge(BaseModel):
    """Connection between nodes in a mindmap."""
    source: str
    target: str
    relationship: str = "connects to"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HierarchicalMindmap(BaseModel):
    """Complete mindmap with hierarchy structure."""
    id: Optional[int] = None
    conversation_id: Optional[int] = None
    nodes: List[MindmapNode] = Field(default_factory=list)
    edges: List[MindmapEdge] = Field(default_factory=list)
    root_node_id: Optional[str] = None
    hierarchy_levels: int = 0
    node_count: int = 0
    max_depth: int = 0
    nodes_by_level: Dict[int, List[MindmapNode]] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MindmapNodesByLevel(BaseModel):
    """Nodes grouped by hierarchy level."""
    level: int
    nodes: List[MindmapNode]
    count: int


class MindmapHierarchyView(BaseModel):
    """Tree-structured view of mindmap hierarchy."""
    node: MindmapNode
    children: List['MindmapHierarchyView'] = Field(default_factory=list)


MindmapHierarchyView.model_rebuild()


class MindmapExtraction(BaseModel):
    """Extracted information from a single mindmap."""
    key_topics: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, str]] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)
    hierarchy_depth: int = 0
    node_count: int = 0


class MindmapSynthesisMetadata(BaseModel):
    """Metadata about synthesis generation."""
    total_mindmaps: int
    total_nodes: int
    source_conversation_ids: List[int]
    source_mindmap_ids: List[int]
    generated_at: datetime
    model: str = "gpt-4o-mini"


class MindmapSynthesis(BaseModel):
    """AI-generated synthesis of all mindmaps."""
    id: Optional[int] = None
    synthesis_text: str
    hierarchy_summary: Optional[Dict[str, Any]] = None
    key_topics: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)
    source_mindmap_ids: List[int] = Field(default_factory=list)
    source_conversation_ids: List[int] = Field(default_factory=list)
    metadata: Optional[MindmapSynthesisMetadata] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MindmapSynthesisChange(BaseModel):
    """Record of a change to mindmap synthesis."""
    id: Optional[int] = None
    synthesis_id: int
    previous_text: Optional[str] = None
    changes_summary: str
    triggered_by: str  # 'new_mindmap', 'updated_mindmap', 'manual', 'scheduled'
    created_at: Optional[datetime] = None


class MindmapHierarchySummary(BaseModel):
    """Summary statistics of mindmap hierarchies."""
    total_mindmaps: int
    total_nodes: int
    avg_depth: float
    levels_distribution: Dict[int, int]  # {level: count}
    conversation_count: int
    unique_topics: List[str] = Field(default_factory=list)
    total_relationships: int = 0


class MindmapRAGContext(BaseModel):
    """Mindmap context for RAG queries."""
    synthesis: MindmapSynthesis
    relevant_nodes: List[MindmapNode] = Field(default_factory=list)
    key_topics: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    source_conversation_count: int = 0


class MindmapSearchResult(BaseModel):
    """Search result containing mindmap data."""
    node_id: str
    title: str
    content: Optional[str]
    hierarchy_level: int
    depth: int
    parent_id: Optional[str]
    conversation_id: Optional[int]
    mindmap_id: Optional[int]
    relevance_score: float
    match_type: str = "hierarchy"  # 'hierarchy', 'synthesis', 'topic', 'relationship'
