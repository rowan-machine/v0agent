# src/app/agents/dikw_synthesizer/__init__.py
"""
DIKW Synthesizer Agent Package

Knowledge pyramid management - promotes signals through Data → Information → Knowledge → Wisdom.

This package provides:
- DIKWSynthesizerAgent: Main agent class for DIKW operations
- Constants: DIKW_LEVELS, prompts, etc.
- Visualization: Mindmap, graph, and tag cluster builders
- Adapters: Backward-compatible functions for existing code
"""

from .constants import (
    DIKW_LEVELS,
    DIKW_LEVEL_DESCRIPTIONS,
    DIKW_NEXT_LEVEL,
    DIKW_PREV_LEVEL,
    LEVEL_PROMPTS,
    MERGE_PROMPT,
    PROMOTION_PROMPTS,
    SYNTHESIS_PROMPTS,
)
from .agent import DIKWSynthesizerAgent
from .visualization import (
    build_graph_data,
    build_mindmap_tree,
    build_tag_clusters,
    get_mindmap_data,
)
from .adapters import (
    # Singleton
    get_dikw_synthesizer,
    
    # Async adapters
    promote_signal_to_dikw_adapter,
    promote_dikw_item_adapter,
    merge_dikw_items_adapter,
    validate_dikw_item_adapter,
    generate_dikw_tags_adapter,
    ai_summarize_dikw_adapter,
    ai_promote_dikw_adapter,
    get_mindmap_data_adapter,
    find_duplicates_adapter,
    analyze_for_suggestions_adapter,
    generate_promoted_content_adapter,
    generate_wisdom_content_adapter,
    suggest_from_signals_adapter,
    
    # Sync wrapper
    generate_dikw_tags,
)

__all__ = [
    # Constants
    "DIKW_LEVELS",
    "DIKW_LEVEL_DESCRIPTIONS",
    "DIKW_NEXT_LEVEL",
    "DIKW_PREV_LEVEL",
    "LEVEL_PROMPTS",
    "MERGE_PROMPT",
    "PROMOTION_PROMPTS",
    "SYNTHESIS_PROMPTS",
    
    # Agent
    "DIKWSynthesizerAgent",
    "get_dikw_synthesizer",
    
    # Visualization
    "build_graph_data",
    "build_mindmap_tree",
    "build_tag_clusters",
    "get_mindmap_data",
    
    # Adapters (async)
    "promote_signal_to_dikw_adapter",
    "promote_dikw_item_adapter",
    "merge_dikw_items_adapter",
    "validate_dikw_item_adapter",
    "generate_dikw_tags_adapter",
    "ai_summarize_dikw_adapter",
    "ai_promote_dikw_adapter",
    "get_mindmap_data_adapter",
    "find_duplicates_adapter",
    "analyze_for_suggestions_adapter",
    "generate_promoted_content_adapter",
    "generate_wisdom_content_adapter",
    "suggest_from_signals_adapter",
    
    # Adapters (sync)
    "generate_dikw_tags",
]
