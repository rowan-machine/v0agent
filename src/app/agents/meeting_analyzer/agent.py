# src/app/agents/meeting_analyzer/agent.py
"""
Meeting Analyzer Agent

Main agent class for meeting intelligence and signal extraction.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from ..base import BaseAgent, AgentConfig
from .constants import SIGNAL_TYPES
from .parser import parse_adaptive
from .extractor import (
    extract_signals_from_sections,
    extract_signals_keyword_fallback,
    parse_ai_signal_response,
    merge_signals,
    deduplicate_signals,
)

logger = logging.getLogger(__name__)


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
        prompts_dir = Path(__file__).parent.parent.parent.parent.parent / "prompts" / "agents" / "meeting_analyzer"
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
            signals = merge_signals(signals, ai_signals)
        
        # Step 4: Deduplicate and validate signals
        signals = deduplicate_signals(signals)
        
        return {
            "success": True,
            "signals": signals,
            "parsed_sections": parsed_sections,
            "meeting_name": meeting_name,
            "meeting_date": meeting_date,
            "signal_counts": {k: len(v) for k, v in signals.items() if isinstance(v, list)},
        }
    
    # =========================================================================
    # PARSING (delegate to parser module)
    # =========================================================================
    
    def parse_adaptive(self, text: str) -> Dict[str, str]:
        """Parse meeting text adaptively."""
        return parse_adaptive(text)
    
    # =========================================================================
    # SIGNAL EXTRACTION (delegate to extractor module)
    # =========================================================================
    
    def extract_signals_from_sections(self, parsed_sections: Dict[str, str]) -> Dict[str, Any]:
        """Extract signals from parsed sections."""
        return extract_signals_from_sections(parsed_sections)
    
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
        """
        if not self.jinja_env:
            return extract_signals_keyword_fallback(meeting_text)
        
        try:
            # Get learning context from user feedback (PC-1 integration)
            learning_context = ""
            try:
                from ...services.signal_learning import get_learning_context_for_extraction
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
            
            return parse_ai_signal_response(response)
        except Exception as e:
            logger.error(f"AI signal extraction failed: {e}")
            return extract_signals_keyword_fallback(meeting_text)
    
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


__all__ = ["MeetingAnalyzerAgent"]
