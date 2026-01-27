# src/app/domains/career/services/suggestion_service.py
"""
Career Suggestion Service

Business logic for generating career development suggestions.
"""

import logging
from typing import Optional
from datetime import datetime

from ....repositories import get_career_repository

logger = logging.getLogger(__name__)


async def generate_career_suggestions(
    user_id: str = "default",
    context: Optional[str] = None,
) -> list[dict]:
    """
    Generate career development suggestions based on user activity.
    
    Args:
        user_id: The user to generate suggestions for
        context: Optional context to consider
        
    Returns:
        List of suggestion dictionaries
    """
    try:
        from ....llm import ask
        
        repo = get_career_repository()
        
        # Get recent standups for context
        standups = await repo.list_standups(user_id, limit=5)
        
        # Get recent skills
        skills = await repo.list_skills(user_id)
        
        # Build context
        standup_context = "\n".join([
            f"- {s.get('today', 'No update')}" 
            for s in standups
        ]) if standups else "No recent standups"
        
        skills_context = ", ".join([
            s.get('name', '') for s in skills[:10]
        ]) if skills else "No skills recorded"
        
        prompt = f"""Based on this developer's recent activity, suggest 3 career development actions:

**Recent Work:**
{standup_context}

**Skills:**
{skills_context}

{f"**Additional Context:** {context}" if context else ""}

For each suggestion provide:
1. A short title (5-7 words)
2. Why it matters (1 sentence)
3. How to do it (1-2 sentences)

Format as JSON array with keys: title, reason, action
"""
        
        response = ask(prompt, max_tokens=500)
        
        # Try to parse JSON from response
        import json
        try:
            # Find JSON array in response
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                suggestions = json.loads(response[start:end])
                return suggestions
        except json.JSONDecodeError:
            pass
        
        # Fallback: return as single suggestion
        return [{
            "title": "Review your recent work",
            "reason": "Self-reflection drives growth",
            "action": response[:200] if response else "Take time to review your standups"
        }]
        
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return []
