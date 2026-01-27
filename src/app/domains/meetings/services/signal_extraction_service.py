# src/app/domains/meetings/services/signal_extraction_service.py
"""
Signal Extraction Service

Business logic for extracting structured signals from meeting content.
"""

import logging
from typing import Dict, Any, List, Optional

from ..constants import SIGNAL_TYPES

logger = logging.getLogger(__name__)


class SignalExtractionService:
    """Service for extracting signals from meeting notes and transcripts."""
    
    def __init__(self):
        self._parser = None
        self._extractor = None
    
    @property
    def parser(self):
        """Lazy load parser to avoid circular imports."""
        if self._parser is None:
            from ....mcp.parser import parse_meeting_summary
            self._parser = parse_meeting_summary
        return self._parser
    
    @property
    def extractor(self):
        """Lazy load extractor to avoid circular imports."""
        if self._extractor is None:
            from ....mcp.extract import extract_structured_signals
            self._extractor = extract_structured_signals
        return self._extractor
    
    def extract_from_notes(self, notes: str) -> List[Dict[str, Any]]:
        """
        Extract signals from meeting notes.
        
        Args:
            notes: Synthesized meeting notes
            
        Returns:
            List of extracted signals
        """
        parsed = self.parser(notes)
        signals = self.extractor(parsed)
        return signals
    
    def extract_with_ai(
        self, 
        content: str,
        signal_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Use AI to extract signals from unstructured content.
        
        Args:
            content: Raw content text
            signal_types: Types of signals to extract (defaults to all)
            
        Returns:
            List of extracted signals
        """
        from ....llm import ask as ask_llm
        import json
        
        types = signal_types or SIGNAL_TYPES
        types_str = ", ".join(types)
        
        prompt = f"""Extract structured signals from this meeting content.

Signal types to extract: {types_str}

Content:
{content[:8000]}

Return a JSON array of signals, each with:
- "type": one of [{types_str}]
- "content": the signal text
- "owner": person responsible (if applicable)
- "due_date": if mentioned
- "priority": high/medium/low if determinable
- "confidence": 0.0-1.0 for extraction confidence

Return ONLY valid JSON array, no other text."""

        try:
            result = ask_llm(prompt, model="gpt-4o-mini")
            # Clean up response
            result = result.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            signals = json.loads(result)
            return signals if isinstance(signals, list) else []
        except Exception as e:
            logger.error(f"AI signal extraction failed: {e}")
            return []
    
    def categorize_signals(
        self, 
        signals: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize signals by type.
        
        Args:
            signals: List of extracted signals
            
        Returns:
            Dict mapping signal type to list of signals
        """
        categorized = {st: [] for st in SIGNAL_TYPES}
        categorized["other"] = []
        
        for signal in signals:
            signal_type = signal.get("type", "other")
            if signal_type in categorized:
                categorized[signal_type].append(signal)
            else:
                categorized["other"].append(signal)
        
        return categorized
    
    def deduplicate_signals(
        self, 
        signals: List[Dict[str, Any]],
        similarity_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate signals based on content similarity.
        
        Args:
            signals: List of signals
            similarity_threshold: Threshold for considering signals duplicates
            
        Returns:
            Deduplicated list of signals
        """
        if not signals:
            return []
        
        unique = []
        seen_content = set()
        
        for signal in signals:
            content = signal.get("content", "").lower().strip()
            # Simple dedup by exact match after normalization
            normalized = " ".join(content.split())
            
            if normalized not in seen_content:
                seen_content.add(normalized)
                unique.append(signal)
        
        return unique


def get_extraction_service() -> SignalExtractionService:
    """Get the signal extraction service instance."""
    return SignalExtractionService()
