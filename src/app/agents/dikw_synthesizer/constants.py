# src/app/agents/dikw_synthesizer/constants.py
"""
DIKW Synthesizer Constants

Defines the DIKW pyramid levels, descriptions, and prompts.
"""

from typing import Dict

# DIKW Pyramid Levels
DIKW_LEVELS = ['data', 'information', 'knowledge', 'wisdom']

DIKW_NEXT_LEVEL: Dict[str, str] = {
    'data': 'information', 
    'information': 'knowledge', 
    'knowledge': 'wisdom'
}

DIKW_PREV_LEVEL: Dict[str, str] = {
    'information': 'data',
    'knowledge': 'information',
    'wisdom': 'knowledge'
}

# Level descriptions for context
DIKW_LEVEL_DESCRIPTIONS: Dict[str, str] = {
    'data': "Raw facts, observations, and signals without context",
    'information': "Contextualized data with meaning and structure",
    'knowledge': "Actionable insights, patterns, and applied understanding",
    'wisdom': "Strategic principles, timeless lessons, and guiding truths"
}

# Prompts for each level (used in promotion and summarization)
LEVEL_PROMPTS: Dict[str, str] = {
    'data': "Briefly describe this raw signal in one sentence",
    'information': "Explain the context and meaning of this signal",
    'knowledge': "What actionable insight or pattern does this represent?",
    'wisdom': "What strategic principle or lesson can be derived from this?"
}

PROMOTION_PROMPTS: Dict[str, str] = {
    'information': """Transform this raw data into structured information. 
Explain what it means in context and why it matters.

Data: {content}

Provide the promoted information-level content:""",
    
    'knowledge': """Extract actionable knowledge from this information. 
What patterns, insights, or principles emerge that can guide decisions?

Information: {content}

Provide the promoted knowledge-level content:""",
    
    'wisdom': """Distill strategic wisdom from this knowledge. 
What fundamental principle or timeless lesson should guide future actions and decisions?

Knowledge: {content}

Provide the promoted wisdom-level content:"""
}

SYNTHESIS_PROMPTS: Dict[str, str] = {
    'information': """Transform this raw data into structured information. 
What does it mean in context?

Data: {content}""",
    
    'knowledge': """Extract actionable knowledge from this information. 
What patterns or insights emerge?

Information: {content}""",
    
    'wisdom': """Distill strategic wisdom from this knowledge. 
What principles should guide future decisions?

Knowledge: {content}"""
}

MERGE_PROMPT = """Synthesize these {count} {current_level}-level items into a single {next_level}-level insight:

Items:
{combined_content}

Previous summaries:
{combined_summaries}

Create a unified {next_level}-level synthesis that captures the essence of all these items."""


__all__ = [
    "DIKW_LEVELS",
    "DIKW_NEXT_LEVEL",
    "DIKW_PREV_LEVEL",
    "DIKW_LEVEL_DESCRIPTIONS",
    "LEVEL_PROMPTS",
    "PROMOTION_PROMPTS",
    "SYNTHESIS_PROMPTS",
    "MERGE_PROMPT",
]
