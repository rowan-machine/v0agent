# src/app/domains/dikw/services/synthesis_service.py
"""
DIKW Synthesis Service

Business logic for AI-powered knowledge synthesis.
"""

import logging

logger = logging.getLogger(__name__)


async def synthesize_knowledge(items: list[dict]) -> dict:
    """
    Synthesize multiple DIKW items into a unified insight.
    
    Args:
        items: List of DIKW items to synthesize
        
    Returns:
        Dictionary with synthesized content and summary
    """
    if not items:
        return {"content": "", "summary": ""}
    
    try:
        from ....llm import ask
        
        combined = "\n".join([
            f"- [{item.get('level', 'data')}] {item.get('content', '')}"
            for item in items
        ])
        
        prompt = f"""Synthesize these knowledge items into a unified insight:

{combined}

Provide:
1. A synthesized statement (2-3 sentences)
2. Key patterns or connections observed
3. Actionable implications

Format as:
SYNTHESIS: [main synthesis]
PATTERNS: [patterns observed]
IMPLICATIONS: [actionable items]
"""
        
        result = await ask(prompt, max_tokens=400)
        
        # Parse the result
        synthesis = ""
        patterns = ""
        implications = ""
        
        for line in result.split("\n"):
            if line.startswith("SYNTHESIS:"):
                synthesis = line.replace("SYNTHESIS:", "").strip()
            elif line.startswith("PATTERNS:"):
                patterns = line.replace("PATTERNS:", "").strip()
            elif line.startswith("IMPLICATIONS:"):
                implications = line.replace("IMPLICATIONS:", "").strip()
        
        return {
            "content": f"{synthesis}\n\nPatterns: {patterns}\n\nImplications: {implications}",
            "summary": synthesis or result[:200],
            "patterns": patterns,
            "implications": implications
        }
        
    except Exception as e:
        logger.error(f"Failed to synthesize knowledge: {e}")
        # Fallback: concatenate summaries
        summaries = [item.get('summary', '') for item in items if item.get('summary')]
        return {
            "content": "\n".join(summaries),
            "summary": summaries[0] if summaries else "",
            "patterns": "",
            "implications": ""
        }


async def generate_summary(content: str, level: str = "data") -> str:
    """
    Generate a summary for DIKW content at a specific level.
    
    Args:
        content: The content to summarize
        level: The DIKW level (affects summary style)
        
    Returns:
        Generated summary string
    """
    if not content:
        return ""
    
    try:
        from ....llm import ask
        
        level_guidance = {
            "data": "Extract the key facts from this raw data.",
            "information": "Summarize the meaningful patterns in this information.",
            "knowledge": "Distill the core insight from this knowledge.",
            "wisdom": "Express the strategic principle from this wisdom."
        }
        
        prompt = f"""{level_guidance.get(level, 'Summarize this content.')}

Content: {content}

Provide a concise summary (1-2 sentences) appropriate for the {level} level."""
        
        summary = await ask(prompt, max_tokens=100)
        return summary.strip()
        
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return content[:200]
