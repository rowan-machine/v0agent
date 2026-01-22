"""
Meeting Analyzer Agent - SignalFlow Meeting Intelligence (Checkpoint 2.4)

AI-powered meeting analysis that provides:
- Signal extraction from meeting summaries (decisions, actions, blockers, risks, ideas)
- Adaptive heading-based parsing for multiple summary formats (Teams, Pocket, etc.)
- Screenshot analysis with vision integration
- Multi-source transcript processing
- Semantic signal grouping and deduplication

Extracted from meetings.py and mcp/extract.py following the migration plan.
Maintains backward compatibility through adapter functions.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import logging
import re

from jinja2 import Environment, FileSystemLoader
from ..agents.base import BaseAgent, AgentConfig

logger = logging.getLogger(__name__)


# =============================================================================
# SIGNAL TYPES AND CATEGORIES
# =============================================================================

SIGNAL_TYPES = {
    "decision": {
        "keywords": ["decided", "agreed", "finalized", "approved", "confirmed", "committed to"],
        "emoji": "✅",
        "dikw_level": "information",
    },
    "action_item": {
        "keywords": ["will", "needs to", "should", "must", "action:", "todo:", "task:"],
        "emoji": "📋",
        "dikw_level": "data",
    },
    "blocker": {
        "keywords": ["blocked", "waiting on", "depends on", "can't proceed", "impediment"],
        "emoji": "🚫",
        "dikw_level": "data",
    },
    "risk": {
        "keywords": ["risk", "concern", "might", "could fail", "uncertain", "unsure"],
        "emoji": "⚠️",
        "dikw_level": "information",
    },
    "idea": {
        "keywords": ["idea:", "suggestion:", "could we", "what if", "maybe we should"],
        "emoji": "💡",
        "dikw_level": "data",
    },
    "key_signal": {
        "keywords": ["key insight", "important", "critical", "main takeaway"],
        "emoji": "🔑",
        "dikw_level": "knowledge",
    },
}


# =============================================================================
# ADAPTIVE HEADING PATTERNS
# Supports multiple summary formats: Teams, Pocket, manual, etc.
# =============================================================================

HEADING_PATTERNS = {
    # Standard markdown headers
    "markdown_h1": r"^#\s+(.+)$",
    "markdown_h2": r"^##\s+(.+)$",
    "markdown_h3": r"^###\s+(.+)$",
    # Bold text as headers
    "bold": r"^\*\*(.+?)\*\*\s*:?\s*$",
    # Colon-terminated headers
    "colon": r"^([A-Za-z][A-Za-z\s/]+):\s*$",
    # Emoji-prefixed headers
    "emoji": r"^([\U0001F300-\U0001F9FF])\s*(.+)$",
}

# Map common heading variations to canonical signal types
HEADING_TO_SIGNAL_TYPE = {
    # Decisions
    "decision": "decision",
    "decisions": "decision",
    "agreed": "decision",
    "confirmed": "decision",
    "approved": "decision",
    # Actions
    "action": "action_item",
    "actions": "action_item",
    "action item": "action_item",
    "action items": "action_item",
    "tasks": "action_item",
    "todo": "action_item",
    "next steps": "action_item",
    "commitments": "action_item",
    "work identified": "action_item",
    # Blockers
    "blocker": "blocker",
    "blockers": "blocker",
    "blocked": "blocker",
    "impediments": "blocker",
    # Risks
    "risk": "risk",
    "risks": "risk",
    "concerns": "risk",
    "risks / open questions": "risk",
    "open questions": "risk",
    # Ideas
    "idea": "idea",
    "ideas": "idea",
    "suggestions": "idea",
    "proposals": "idea",
    # Key signals
    "key signal": "key_signal",
    "key signals": "key_signal",
    "insights": "key_signal",
    "takeaways": "key_signal",
    "outcomes": "key_signal",
    # Context/Notes (not signals, but useful metadata)
    "context": "context",
    "background": "context",
    "notes": "notes",
    "summary": "summary",
    "synthesized signals": "synthesized",
}


class MeetingAnalyzerAgent(BaseAgent):
    """
    Meeting Analyzer - SignalFlow's meeting intelligence agent.
    
    Capabilities:
    - Extract structured signals from meeting summaries
    - Support adaptive heading-based parsing for multiple formats
    - Analyze screenshots with vision AI
    - Process multi-source transcripts (Teams, Pocket, etc.)
    - Group and deduplicate signals semantically
    - Link transcripts/documents to meetings for two-layer context
    
    Prompts:
    - system.jinja2: Main analyzer persona
    - extract_signals.jinja2: AI-powered signal extraction
    - analyze_screenshot.jinja2: Vision analysis for screenshots
    - summarize_transcript.jinja2: Transcript summarization
    """
    
    def __init__(
        self,
        config: AgentConfig,
        llm_client=None,
        tool_registry=None,
        model_router=None,
        guardrails=None,
        db_connection=None,
    ):
        super().__init__(
            config=config,
            llm_client=llm_client,
            tool_registry=tool_registry,
            model_router=model_router,
            guardrails=guardrails,
        )
        self.db_connection = db_connection
        
        # Initialize Jinja2 environment for prompt templates
        prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts" / "agents" / "meeting_analyzer"
        if prompts_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
            logger.info(f"Loaded Meeting Analyzer prompts from {prompts_dir}")
        else:
            self.jinja_env = None
            logger.warning(f"Meeting Analyzer prompts directory not found: {prompts_dir}")
    
    def get_system_prompt(self, meeting: Dict = None, context: Dict = None) -> str:
        """Generate system prompt from Jinja2 template."""
        if not self.jinja_env:
            return self._get_fallback_system_prompt()
        
        try:
            template = self.jinja_env.get_template("system.jinja2")
            return template.render(
                meeting=meeting or {},
                context=context or {},
                signal_types=SIGNAL_TYPES,
            )
        except Exception as e:
            logger.error(f"Failed to render system prompt: {e}")
            return self._get_fallback_system_prompt()
    
    def _get_fallback_system_prompt(self) -> str:
        """Fallback system prompt if templates aren't available."""
        return """You are a meeting intelligence agent specializing in extracting actionable 
signals from meeting notes and transcripts.

Extract these signal types:
- Decisions: What was agreed or decided
- Action Items: Tasks assigned to people  
- Blockers: What's preventing progress
- Risks: Potential problems or concerns
- Ideas: Suggestions or proposals
- Key Signals: Important insights or takeaways

Be thorough but avoid duplicates. Attribute actions to specific people when mentioned."""

    # =========================================================================
    # CORE ANALYSIS METHODS
    # =========================================================================
    
    async def run(
        self,
        meeting_text: str,
        meeting_name: str = None,
        meeting_date: str = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a meeting and extract signals.
        
        Args:
            meeting_text: The meeting summary or transcript text
            meeting_name: Optional meeting name/title
            meeting_date: Optional meeting date
            conversation_history: Previous messages (for chat context)
            context: Additional context (linked docs, etc.)
        
        Returns:
            Dict with signals, metadata, and optional follow-up suggestions
        """
        context = context or {}
        
        # Step 1: Parse structure adaptively based on headings
        parsed_sections = self.parse_adaptive(meeting_text)
        
        # Step 2: Extract signals from parsed sections
        signals = self.extract_signals_from_sections(parsed_sections)
        
        # Step 3: If we have few signals, use AI to enhance extraction
        if self._should_use_ai_extraction(signals):
            ai_signals = await self._extract_signals_with_ai(meeting_text, context)
            signals = self._merge_signals(signals, ai_signals)
        
        # Step 4: Deduplicate and validate signals
        signals = self._deduplicate_signals(signals)
        
        return {
            "success": True,
            "signals": signals,
            "parsed_sections": parsed_sections,
            "meeting_name": meeting_name,
            "meeting_date": meeting_date,
            "signal_counts": {k: len(v) for k, v in signals.items() if isinstance(v, list)},
        }
    
    # =========================================================================
    # ADAPTIVE PARSING
    # =========================================================================
    
    def parse_adaptive(self, text: str) -> Dict[str, str]:
        """
        Adaptively parse meeting text by detecting heading patterns.
        
        Supports multiple formats:
        - Teams summary format
        - Pocket dynamic summaries
        - Manual markdown notes
        - Plain text with colon-headers
        
        Args:
            text: Raw meeting summary text
        
        Returns:
            Dict mapping section names to content
        """
        result = {}
        current_section = None
        buffer: List[str] = []
        
        lines = text.splitlines()
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines but preserve them in content
            if not stripped:
                buffer.append(line)
                continue
            
            # Skip HTML aside tags
            if stripped.startswith("<aside") or stripped.endswith("</aside>"):
                continue
            
            # Try to detect a heading
            heading = self._detect_heading(stripped)
            
            if heading:
                # Save previous section
                if current_section:
                    result[current_section] = "\n".join(buffer).strip()
                current_section = heading
                buffer = []
                continue
            
            buffer.append(line)
        
        # Save final section
        if current_section:
            result[current_section] = "\n".join(buffer).strip()
        elif buffer:
            # No sections detected - treat entire text as notes
            result["notes"] = "\n".join(buffer).strip()
        
        return result
    
    def _detect_heading(self, line: str) -> Optional[str]:
        """
        Detect if a line is a heading and return the canonical heading name.
        
        Args:
            line: A single line of text
        
        Returns:
            Canonical heading name or None
        """
        # Remove markdown formatting
        cleaned = line.lstrip("#").strip().strip("*").strip()
        
        # Try each heading pattern
        for pattern_name, pattern in HEADING_PATTERNS.items():
            match = re.match(pattern, line)
            if match:
                if pattern_name == "emoji":
                    # For emoji patterns, use the text part
                    heading_text = match.group(2).lower().strip()
                else:
                    heading_text = match.group(1).lower().strip() if match.groups() else cleaned.lower()
                
                # Map to canonical type if known, otherwise use original
                return HEADING_TO_SIGNAL_TYPE.get(heading_text, cleaned)
        
        # Check if the cleaned text matches known headers
        cleaned_lower = cleaned.lower()
        if cleaned_lower in HEADING_TO_SIGNAL_TYPE:
            return HEADING_TO_SIGNAL_TYPE[cleaned_lower]
        
        return None
    
    # =========================================================================
    # SIGNAL EXTRACTION
    # =========================================================================
    
    def extract_signals_from_sections(self, parsed_sections: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract structured signals from parsed sections.
        
        Args:
            parsed_sections: Dict of section_name -> content
        
        Returns:
            Dict with signal lists by type
        """
        signals = {
            "decisions": [],
            "action_items": [],
            "blockers": [],
            "risks": [],
            "ideas": [],
            "key_signals": [],
            "context": "",
            "notes": "",
        }
        
        # Check for synthesized signals section (highest priority)
        synthesized_key = next(
            (k for k in parsed_sections if "synthesized" in k.lower()),
            None
        )
        if synthesized_key:
            synthesized_signals = self._extract_from_synthesized(parsed_sections[synthesized_key])
            signals = self._merge_signals(signals, synthesized_signals)
        
        # Process each section
        for section_name, content in parsed_sections.items():
            if not content:
                continue
            
            section_lower = section_name.lower()
            
            # Map section to signal type
            if section_lower in ["decision", "decisions"]:
                signals["decisions"].extend(self._extract_items(content))
            elif section_lower in ["action_item", "action items", "tasks", "commitments", "work identified"]:
                signals["action_items"].extend(self._extract_items(content))
            elif section_lower in ["blocker", "blockers", "blocked"]:
                signals["blockers"].extend(self._extract_items(content))
            elif section_lower in ["risk", "risks", "concerns", "risks / open questions"]:
                signals["risks"].extend(self._extract_items(content))
            elif section_lower in ["idea", "ideas", "suggestions"]:
                signals["ideas"].extend(self._extract_items(content))
            elif section_lower in ["key_signal", "key signals", "insights", "outcomes"]:
                signals["key_signals"].extend(self._extract_items(content))
            elif section_lower in ["context", "background"]:
                signals["context"] = content
            elif section_lower in ["notes", "summary"]:
                signals["notes"] = content
        
        return signals
    
    def _extract_items(self, content: str) -> List[str]:
        """
        Extract individual items from section content.
        
        Args:
            content: Section text content
        
        Returns:
            List of extracted items
        """
        items = []
        
        for line in content.splitlines():
            stripped = line.strip()
            
            # Skip empty lines and markers
            if not stripped or stripped in ["🚦", "🧩", "✨", "📝", "🟩", "🟪"]:
                continue
            
            # Skip sub-headers
            if stripped.startswith("###") or stripped.startswith("**"):
                continue
            
            # Remove bullet points and clean
            item = stripped.lstrip("-•*").strip()
            
            if item and len(item) > 2:  # Minimum length check
                items.append(item)
        
        return items
    
    def _extract_from_synthesized(self, text: str) -> Dict[str, List[str]]:
        """
        Extract signals from a synthesized signals block with internal sections.
        
        Args:
            text: Synthesized signals section content
        
        Returns:
            Dict with signal lists
        """
        result = {
            "decisions": [],
            "action_items": [],
            "blockers": [],
            "risks": [],
            "ideas": [],
            "key_signals": [],
        }
        
        current_section = None
        
        for line in text.splitlines():
            stripped = line.strip()
            
            if not stripped or stripped in ["🚦", "🧩", "✨", "📝"]:
                continue
            
            # Check for inline section headers
            stripped_lower = stripped.lower()
            if "decision" in stripped_lower and stripped_lower.endswith(":"):
                current_section = "decisions"
                continue
            elif "action" in stripped_lower and stripped_lower.endswith(":"):
                current_section = "action_items"
                continue
            elif "block" in stripped_lower and stripped_lower.endswith(":"):
                current_section = "blockers"
                continue
            elif "risk" in stripped_lower and stripped_lower.endswith(":"):
                current_section = "risks"
                continue
            elif "idea" in stripped_lower and stripped_lower.endswith(":"):
                current_section = "ideas"
                continue
            elif "key" in stripped_lower and "signal" in stripped_lower:
                current_section = "key_signals"
                continue
            
            # Add to current section
            if current_section:
                item = stripped.lstrip("-•*").strip()
                if item and item not in result[current_section]:
                    result[current_section].append(item)
        
        return result
    
    # =========================================================================
    # AI-ENHANCED EXTRACTION
    # =========================================================================
    
    def _should_use_ai_extraction(self, signals: Dict[str, Any]) -> bool:
        """Check if we should use AI to enhance signal extraction."""
        total_signals = sum(len(v) for v in signals.values() if isinstance(v, list))
        return total_signals < 3  # Use AI if we found few signals
    
    async def _extract_signals_with_ai(
        self,
        meeting_text: str,
        context: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """
        Use AI to extract signals when rule-based parsing finds few.
        
        Integrates with SignalLearningService (PC-1) to include user feedback
        patterns in the extraction prompt.
        
        Args:
            meeting_text: The meeting text
            context: Additional context
        
        Returns:
            Dict with extracted signals
        """
        if not self.jinja_env:
            return self._extract_signals_keyword_fallback(meeting_text)
        
        try:
            # Get learning context from user feedback (PC-1 integration)
            learning_context = ""
            try:
                from ..services.signal_learning import get_learning_context_for_extraction
                learning_context = get_learning_context_for_extraction()
            except Exception as e:
                logger.debug(f"Could not load signal learning context: {e}")
            
            template = self.jinja_env.get_template("extract_signals.jinja2")
            prompt = template.render(
                meeting_text=meeting_text[:4000],  # Limit context size
                signal_types=SIGNAL_TYPES,
                learning_context=learning_context,  # Add feedback-based hints
            )
            
            response = await self.ask_llm(
                prompt,
                system_prompt=self.get_system_prompt(context=context),
                task_type="extraction",
            )
            
            return self._parse_ai_signal_response(response)
        except Exception as e:
            logger.error(f"AI signal extraction failed: {e}")
            return self._extract_signals_keyword_fallback(meeting_text)
    
    def _extract_signals_keyword_fallback(self, text: str) -> Dict[str, List[str]]:
        """
        Keyword-based signal extraction as fallback.
        
        Args:
            text: Meeting text
        
        Returns:
            Dict with extracted signals
        """
        result = {
            "decisions": [],
            "action_items": [],
            "blockers": [],
            "risks": [],
            "ideas": [],
            "key_signals": [],
        }
        
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            
            lower = stripped.lower()
            
            for signal_type, info in SIGNAL_TYPES.items():
                for keyword in info["keywords"]:
                    if keyword.lower() in lower:
                        # Map signal type to result key
                        key = signal_type + "s" if not signal_type.endswith("s") else signal_type
                        if key == "action_items":
                            key = "action_items"
                        elif key == "key_signals":
                            key = "key_signals"
                        
                        if key in result and stripped not in result[key]:
                            result[key].append(stripped)
                        break
        
        return result
    
    def _parse_ai_signal_response(self, response: str) -> Dict[str, List[str]]:
        """
        Parse AI response containing extracted signals.
        
        Args:
            response: AI model response text
        
        Returns:
            Dict with signal lists
        """
        result = {
            "decisions": [],
            "action_items": [],
            "blockers": [],
            "risks": [],
            "ideas": [],
            "key_signals": [],
        }
        
        # Try to parse as JSON first
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                for key in result:
                    if key in parsed and isinstance(parsed[key], list):
                        result[key] = parsed[key]
                return result
        except json.JSONDecodeError:
            pass
        
        # Fall back to line-by-line parsing
        current_section = None
        for line in response.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            
            # Detect section headers
            if "decision" in lower:
                current_section = "decisions"
            elif "action" in lower:
                current_section = "action_items"
            elif "blocker" in lower:
                current_section = "blockers"
            elif "risk" in lower:
                current_section = "risks"
            elif "idea" in lower:
                current_section = "ideas"
            elif "key" in lower and "signal" in lower:
                current_section = "key_signals"
            elif current_section and stripped.startswith("-"):
                item = stripped.lstrip("-•*").strip()
                if item and item not in result[current_section]:
                    result[current_section].append(item)
        
        return result
    
    # =========================================================================
    # SIGNAL PROCESSING UTILITIES
    # =========================================================================
    
    def _merge_signals(
        self,
        base: Dict[str, Any],
        additional: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """
        Merge additional signals into base, avoiding duplicates.
        
        Args:
            base: Base signals dict
            additional: Additional signals to merge
        
        Returns:
            Merged signals dict
        """
        for key, items in additional.items():
            if key in base and isinstance(base[key], list):
                for item in items:
                    if item not in base[key]:
                        base[key].append(item)
        
        return base
    
    def _deduplicate_signals(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove duplicate and near-duplicate signals.
        
        Args:
            signals: Dict with signal lists
        
        Returns:
            Deduplicated signals
        """
        for key, value in signals.items():
            if isinstance(value, list):
                seen = set()
                unique = []
                for item in value:
                    # Normalize for comparison
                    normalized = item.lower().strip()
                    if normalized not in seen:
                        seen.add(normalized)
                        unique.append(item)
                signals[key] = unique
        
        return signals
    
    # =========================================================================
    # SCREENSHOT ANALYSIS
    # =========================================================================
    
    async def analyze_screenshot(
        self,
        image_base64: str,
        meeting_context: Dict[str, Any] = None,
    ) -> str:
        """
        Analyze a screenshot using vision AI.
        
        Args:
            image_base64: Base64 encoded image
            meeting_context: Optional meeting context
        
        Returns:
            Analysis summary text
        """
        prompt = """Analyze this screenshot from a meeting and provide:
1. Main content or topic visible
2. Any visible text, names, or dates
3. Any action items or decisions visible
4. Key takeaways

Be concise but thorough."""
        
        try:
            # Use vision-capable model via model router
            response = await self.ask_llm(
                prompt,
                task_type="vision",
                images=[image_base64],
            )
            return response
        except Exception as e:
            logger.error(f"Screenshot analysis failed: {e}")
            return f"Screenshot analysis unavailable: {e}"


# =============================================================================
# ADAPTER FUNCTIONS - For backward compatibility with meetings.py
# =============================================================================

_meeting_analyzer_instance: Optional[MeetingAnalyzerAgent] = None


def get_meeting_analyzer() -> MeetingAnalyzerAgent:
    """Get or create the singleton MeetingAnalyzerAgent instance."""
    global _meeting_analyzer_instance
    
    if _meeting_analyzer_instance is None:
        from ..agents.registry import get_registry
        registry = get_registry()
        
        _meeting_analyzer_instance = registry.get("meeting_analyzer")
        if _meeting_analyzer_instance is None:
            # Register default instance
            config = AgentConfig(
                name="meeting_analyzer",
                description="Meeting intelligence and signal extraction",
                capabilities=["signal_extraction", "screenshot_analysis", "transcript_processing"],
            )
            _meeting_analyzer_instance = MeetingAnalyzerAgent(config=config)
            registry.register("meeting_analyzer", _meeting_analyzer_instance)
    
    return _meeting_analyzer_instance


def parse_meeting_summary_adaptive(text: str) -> Dict[str, str]:
    """
    Adapter for backward compatibility with mcp/parser.py.
    
    Args:
        text: Meeting summary text
    
    Returns:
        Dict of parsed sections
    """
    agent = get_meeting_analyzer()
    return agent.parse_adaptive(text)


def extract_signals_from_meeting(parsed_sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Adapter for backward compatibility with mcp/extract.py.
    
    Args:
        parsed_sections: Parsed meeting sections
    
    Returns:
        Dict with extracted signals
    """
    agent = get_meeting_analyzer()
    return agent.extract_signals_from_sections(parsed_sections)


# Export for module use
__all__ = [
    "MeetingAnalyzerAgent",
    "get_meeting_analyzer",
    "parse_meeting_summary_adaptive",
    "extract_signals_from_meeting",
    "SIGNAL_TYPES",
    "HEADING_TO_SIGNAL_TYPE",
]
