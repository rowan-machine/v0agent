# src/app/domains/meetings/services/synthesis_service.py
"""
Meeting Synthesis Service

Business logic for synthesizing meeting notes from various sources.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class MeetingSynthesisService:
    """Service for synthesizing meeting notes from transcripts and other sources."""
    
    def __init__(self):
        self._llm = None
    
    @property
    def llm(self):
        """Lazy load LLM to avoid circular imports."""
        if self._llm is None:
            from ....llm import ask
            self._llm = ask
        return self._llm
    
    def synthesize_from_transcript(
        self, 
        transcript: str,
        meeting_type: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Synthesize structured notes from a transcript.
        
        Args:
            transcript: Raw transcript text
            meeting_type: Type of meeting (standup, planning, etc.)
            additional_context: Any additional context to include
            
        Returns:
            Synthesized notes as formatted text
        """
        type_guidance = ""
        if meeting_type == "standup":
            type_guidance = "Focus on: what was done, what's planned, blockers."
        elif meeting_type == "planning":
            type_guidance = "Focus on: sprint goals, story points, assignments."
        elif meeting_type == "retrospective":
            type_guidance = "Focus on: what went well, improvements, action items."
        
        prompt = f"""Synthesize this meeting transcript into structured notes.
{type_guidance}

Transcript:
{transcript[:10000]}

{f'Additional context: {additional_context}' if additional_context else ''}

Create clear, actionable notes with:
- Key decisions (with rationale)
- Action items (with owners and dates if mentioned)
- Important discussion points
- Risks or blockers
- Follow-ups needed"""

        return self.llm(prompt, model="gpt-4o-mini")
    
    def merge_multiple_sources(
        self,
        sources: List[Dict[str, Any]]
    ) -> str:
        """
        Merge notes from multiple sources (Teams, Pocket, manual notes).
        
        Args:
            sources: List of dicts with 'type', 'content', 'timestamp'
            
        Returns:
            Merged, deduplicated notes
        """
        combined = "\n\n---\n\n".join([
            f"[{s['type']}] {s.get('timestamp', 'Unknown time')}:\n{s['content']}"
            for s in sources
        ])
        
        prompt = f"""Merge these meeting notes from different sources into a single coherent summary.
Remove duplicates and organize by topic.

Sources:
{combined}

Create a unified summary that preserves all unique information."""

        return self.llm(prompt, model="gpt-4o-mini")
    
    def generate_title(self, content: str) -> str:
        """Generate a descriptive title for a meeting."""
        prompt = f"""Generate a short, descriptive title (5-8 words) for this meeting:

{content[:2000]}

Just return the title, nothing else."""

        return self.llm(prompt, model="gpt-4o-mini").strip()


def get_synthesis_service() -> MeetingSynthesisService:
    """Get the meeting synthesis service instance."""
    return MeetingSynthesisService()
