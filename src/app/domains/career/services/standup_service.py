# src/app/domains/career/services/standup_service.py
"""
Standup Analysis Service

Business logic for analyzing standup updates using AI.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def analyze_standup(
    yesterday: str,
    today: str,
    blockers: str,
) -> Optional[str]:
    """
    Analyze a standup update using AI.
    
    Returns:
        AI-generated analysis of the standup, or None if analysis fails.
    """
    try:
        from ....llm import ask
        
        prompt = f"""Analyze this standup update and provide brief coaching feedback:

**Yesterday:**
{yesterday or 'No updates'}

**Today:**
{today or 'No plans'}

**Blockers:**
{blockers or 'None'}

Provide 2-3 sentences of constructive feedback focusing on:
- Progress acknowledgment
- Blocker resolution suggestions if any
- One actionable tip for the day
"""
        
        analysis = ask(prompt, max_tokens=200)
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to analyze standup: {e}")
        return None
