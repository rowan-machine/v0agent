# src/app/agents/dikw_synthesizer/adapters.py
"""
DIKW Synthesizer Adapter Functions

Backward-compatible adapter functions for main.py and other consumers.
These wrap the DIKWSynthesizerAgent class methods.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..base import AgentConfig
from .agent import DIKWSynthesizerAgent
from .constants import DIKW_LEVELS
from .visualization import get_mindmap_data

logger = logging.getLogger(__name__)

# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_dikw_synthesizer_instance: Optional[DIKWSynthesizerAgent] = None


def get_dikw_synthesizer(
    llm_client=None,
    db_connection=None,
) -> DIKWSynthesizerAgent:
    """
    Get the global DIKW Synthesizer agent instance (lazy singleton).
    
    Args:
        llm_client: Optional LLM client for AI calls
        db_connection: Optional database connection
    
    Returns:
        DIKWSynthesizerAgent instance
    """
    global _dikw_synthesizer_instance
    
    if _dikw_synthesizer_instance is None:
        config = AgentConfig(
            name="dikw_synthesizer",
            description="Knowledge pyramid management - promotes signals through Data → Information → Knowledge → Wisdom",
            system_prompt="",  # Will use template
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=2000,
            tools=[],
            capabilities=[
                "promote_signal",
                "promote",
                "merge",
                "validate",
                "summarize",
                "refine",
                "generate_tags",
                "ai_review",
                "mindmap",
            ],
        )
        
        _dikw_synthesizer_instance = DIKWSynthesizerAgent(
            config=config,
            llm_client=llm_client,
            db_connection=db_connection,
        )
    
    return _dikw_synthesizer_instance


# =============================================================================
# ADAPTER FUNCTIONS - Backward compatibility with main.py
# =============================================================================

async def promote_signal_to_dikw_adapter(
    signal_text: str,
    signal_type: str = "",
    meeting_id: Optional[int] = None,
    target_level: str = "data",
) -> Dict[str, Any]:
    """
    Adapter function for promoting a signal to DIKW.
    Maintains backward compatibility with main.py routes.
    """
    agent = get_dikw_synthesizer()
    return await agent.run(
        action='promote_signal',
        data={
            'signal_text': signal_text,
            'signal_type': signal_type,
            'meeting_id': meeting_id,
            'level': target_level,
        }
    )


async def promote_dikw_item_adapter(
    content: str,
    from_level: str,
    to_level: Optional[str] = None,
    promoted_content: Optional[str] = None,
    summary: Optional[str] = None,
    tags: str = "",
) -> Dict[str, Any]:
    """
    Adapter function for promoting a DIKW item.
    Maintains backward compatibility with main.py routes.
    """
    agent = get_dikw_synthesizer()
    return await agent.run(
        action='promote',
        data={
            'content': content,
            'from_level': from_level,
            'to_level': to_level,
            'promoted_content': promoted_content,
            'summary': summary,
            'tags': tags,
        }
    )


async def merge_dikw_items_adapter(items: List[Dict]) -> Dict[str, Any]:
    """
    Adapter function for merging DIKW items.
    Maintains backward compatibility with main.py routes.
    """
    agent = get_dikw_synthesizer()
    return await agent.run(action='merge', data={'items': items})


async def validate_dikw_item_adapter(
    action: str = "validate",
    confidence: float = 0.5,
    validation_count: int = 0,
) -> Dict[str, Any]:
    """
    Adapter function for validating DIKW items.
    Maintains backward compatibility with main.py routes.
    """
    agent = get_dikw_synthesizer()
    return await agent.run(
        action='validate',
        data={
            'action': action,
            'confidence': confidence,
            'validation_count': validation_count,
        }
    )


async def generate_dikw_tags_adapter(
    content: str,
    level: str = "data",
    existing_tags: str = "",
) -> str:
    """
    Adapter function for generating DIKW tags.
    Maintains backward compatibility with main.py routes.
    """
    agent = get_dikw_synthesizer()
    result = await agent.run(
        action='generate_tags',
        data={
            'content': content,
            'level': level,
            'existing_tags': existing_tags,
        }
    )
    return result.get('tags', '')


async def ai_summarize_dikw_adapter(content: str, level: str = "data") -> str:
    """
    Adapter function for AI summarization.
    Maintains backward compatibility with main.py routes.
    """
    agent = get_dikw_synthesizer()
    result = await agent.run(
        action='summarize',
        data={'content': content, 'level': level}
    )
    return result.get('summary', '')


async def ai_promote_dikw_adapter(
    content: str,
    from_level: str,
    to_level: str,
) -> Dict[str, Any]:
    """
    Adapter function for AI-assisted promotion.
    Maintains backward compatibility with main.py routes.
    """
    agent = get_dikw_synthesizer()
    return await agent.run(
        action='promote',
        data={
            'content': content,
            'from_level': from_level,
            'to_level': to_level,
        }
    )


def get_mindmap_data_adapter(items: List[Dict]) -> Dict[str, Any]:
    """
    Adapter function for getting mindmap visualization data.
    Maintains backward compatibility with main.py routes.
    """
    return get_mindmap_data(items)


async def find_duplicates_adapter(items: List[Dict], level: str) -> List[List[int]]:
    """
    Adapter function for finding duplicate DIKW items.
    Returns groups of IDs that are duplicates/similar.
    
    Migration Note (P1.8): Centralizes duplicate detection logic.
    """
    if len(items) < 2:
        return []
    
    items_text = "\n".join([
        f"[ID:{i.get('id')}] {(i.get('content') or '')[:150]}"
        for i in items[:30]
    ])
    
    prompt = f"""Analyze these {level}-level DIKW items and identify duplicates or highly similar items that should be merged.

Items:
{items_text}

Return a JSON array of groups to merge. Each group is an array of IDs that are duplicates/similar:
Example: [[1, 5], [3, 8, 12]]

Only group items that are clearly about the same thing. Return empty array [] if no duplicates.
Return ONLY the JSON array:"""

    agent = get_dikw_synthesizer()
    try:
        response = await agent._call_llm_text(prompt)
        groups = json.loads(response.strip().strip('```json').strip('```'))
        return [g for g in groups if len(g) >= 2]
    except Exception as e:
        logger.error(f"Error finding duplicates in {level}: {e}")
        return []


async def analyze_for_suggestions_adapter(items: List[Dict]) -> Dict[str, Any]:
    """
    Adapter function for smart DIKW suggestions analysis.
    Returns promotion candidates, confidence updates, wisdom candidates, and new suggestions.
    
    Migration Note (P1.8): Centralizes smart suggestions logic.
    """
    if not items:
        return {'promote': [], 'confidence': [], 'wisdom_candidates': [], 'suggest': []}
    
    items_summary = "\n".join([
        f"[{i.get('level')}] (id:{i.get('id')}, confidence:{i.get('confidence', 70)}%) {i.get('content', '')[:200]}"
        for i in items[:25]
    ])
    
    prompt = f"""Analyze these DIKW pyramid items thoroughly:

Current items:
{items_summary}

Provide a comprehensive analysis with JSON containing:

1. "promote": Items ready for promotion (consider: maturity, validation, actionability)
   [{{"id": <id>, "from_level": "data", "to_level": "information", "reason": "specific reason"}}]

2. "confidence": Items needing confidence adjustments based on:
   - Specificity (vague = lower, precise = higher)
   - Verifiability (opinion = 40-60%, verified fact = 80-95%)
   - Actionability (theoretical = lower, practical = higher)
   - Time sensitivity (dated info = lower confidence)
   [{{"id": <id>, "old_confidence": 70, "new_confidence": 85, "reason": "why this adjustment"}}]

3. "wisdom_candidates": Knowledge items that could become wisdom (timeless principles, strategic insights)
   [{{"id": <id>, "potential_wisdom": "the distilled principle", "readiness_score": 1-10, "reason": "why this could be wisdom"}}]

4. "suggest": New items to fill gaps in the pyramid
   [{{"level": "knowledge", "content": "...", "summary": "..."}}]

Be specific about confidence levels:
- 30-50%: Uncertain, needs validation
- 50-70%: Reasonable but not confirmed
- 70-85%: Well-supported
- 85-95%: Highly confident, verified

JSON only:"""

    agent = get_dikw_synthesizer()
    try:
        response = await agent._call_llm_text(prompt)
        result = json.loads(response.strip().strip('```json').strip('```'))
        return {
            'promote': result.get('promote', [])[:4],
            'confidence': result.get('confidence', [])[:6],
            'wisdom_candidates': result.get('wisdom_candidates', [])[:3],
            'suggest': result.get('suggest', [])[:3],
        }
    except Exception as e:
        logger.error(f"Error in smart suggestions analysis: {e}")
        return {'promote': [], 'confidence': [], 'wisdom_candidates': [], 'suggest': []}


async def generate_promoted_content_adapter(
    content: str, 
    to_level: str
) -> Dict[str, str]:
    """
    Adapter function for generating promoted content for a specific level.
    Returns dict with 'promoted_content' and 'summary'.
    
    Migration Note (P1.8): Centralizes promotion content generation.
    """
    promotion_prompts = {
        'information': f"""Transform this raw data into structured, contextualized information.
Explain what it means, why it matters, and what context is needed to understand it.

Data: {content}

Provide clear, informative content:""",
        'knowledge': f"""Extract actionable knowledge from this information.
What patterns emerge? What can be applied? What decisions does this inform?

Information: {content}

Provide actionable knowledge:""",
        'wisdom': f"""Distill strategic wisdom from this knowledge.
What timeless principle or strategic insight emerges that will remain true across contexts?

Knowledge: {content}

Provide wisdom-level insight:"""
    }
    
    agent = get_dikw_synthesizer()
    try:
        promoted_content = await agent._call_llm_text(
            promotion_prompts.get(to_level, promotion_prompts['information'])
        )
        summary = await agent._call_llm_text(
            f"Summarize this {to_level}-level insight in one clear sentence:\n\n{promoted_content}"
        )
        return {'promoted_content': promoted_content, 'summary': summary}
    except Exception as e:
        logger.error(f"Error generating promoted content: {e}")
        return {'promoted_content': content, 'summary': ''}


async def generate_wisdom_content_adapter(
    knowledge_content: str, 
    potential_wisdom_direction: str = ""
) -> str:
    """
    Adapter function for generating wisdom content from knowledge.
    
    Migration Note (P1.8): Centralizes wisdom generation logic.
    """
    prompt = f"""Transform this knowledge into timeless wisdom - a principle that transcends specific contexts.

Knowledge: {knowledge_content}
Potential wisdom direction: {potential_wisdom_direction}

Create a concise, memorable wisdom statement:"""

    agent = get_dikw_synthesizer()
    try:
        return await agent._call_llm_text(prompt)
    except Exception as e:
        logger.error(f"Error generating wisdom content: {e}")
        return ""


async def suggest_from_signals_adapter(signal_context: str) -> List[Dict]:
    """
    Adapter function for suggesting DIKW items from meeting signals.
    
    Migration Note (P1.8): Centralizes signal-to-DIKW suggestion logic.
    """
    if not signal_context:
        return []
    
    prompt = f"""Based on these recent signals from meetings, suggest 2-3 DIKW items to add:

{signal_context}

Return a JSON array of objects with: level (data/information/knowledge/wisdom), content, summary
Example: [{{"level": "data", "content": "Team velocity decreased 20% this sprint", "summary": "Velocity tracking observation"}}]

JSON array only:"""

    agent = get_dikw_synthesizer()
    try:
        response = await agent._call_llm_text(prompt)
        suggestions = json.loads(response.strip().strip('```json').strip('```'))
        return suggestions[:3]
    except Exception as e:
        logger.error(f"Error generating suggestions from signals: {e}")
        return []


# Synchronous wrapper for backward compatibility
def generate_dikw_tags(content: str, level: str, existing_tags: str = "") -> str:
    """
    Synchronous wrapper for tag generation.
    Used by main.py for direct calls.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, use create_task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_dikw_tags_adapter(content, level, existing_tags)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                generate_dikw_tags_adapter(content, level, existing_tags)
            )
    except Exception as e:
        logger.error(f"Failed to generate tags synchronously: {e}")
        # Fallback to simple extraction
        return ""


__all__ = [
    # Singleton
    "get_dikw_synthesizer",
    
    # Async adapters
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
    
    # Sync wrapper
    "generate_dikw_tags",
]
