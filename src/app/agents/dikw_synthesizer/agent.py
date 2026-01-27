# src/app/agents/dikw_synthesizer/agent.py
"""
DIKW Synthesizer Agent

Main agent class for knowledge pyramid management.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from ..base import BaseAgent, AgentConfig
from .constants import (
    DIKW_LEVELS,
    DIKW_LEVEL_DESCRIPTIONS,
    DIKW_NEXT_LEVEL,
    DIKW_PREV_LEVEL,
    MERGE_PROMPT,
    SYNTHESIS_PROMPTS,
)

logger = logging.getLogger(__name__)


class DIKWSynthesizerAgent(BaseAgent):
    """
    Agent for DIKW (Data-Information-Knowledge-Wisdom) pyramid management.
    
    Capabilities:
    - Promote signals/items through DIKW levels
    - Merge multiple items into higher-level synthesis
    - Validate/invalidate items to adjust confidence
    - Generate AI summaries appropriate for each level
    - Auto-generate relevant tags
    - AI-powered review and suggestions
    
    Prompts:
    - system.jinja2: Main synthesizer persona
    - promote.jinja2: Level promotion prompts
    - merge.jinja2: Multi-item synthesis
    - summarize.jinja2: Level-appropriate summaries
    - generate_tags.jinja2: Tag generation
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
        prompts_dir = Path(__file__).parent.parent.parent.parent.parent / "prompts" / "agents" / "dikw_synthesizer"
        if prompts_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
            logger.info(f"Loaded DIKW Synthesizer prompts from {prompts_dir}")
        else:
            self.jinja_env = None
            logger.warning(f"DIKW Synthesizer prompts directory not found: {prompts_dir}")
    
    def get_system_prompt(self, context: Optional[Dict] = None) -> str:
        """Generate system prompt from Jinja2 template."""
        if not self.jinja_env:
            return self._get_fallback_system_prompt()
        
        try:
            template = self.jinja_env.get_template("system.jinja2")
            return template.render(
                dikw_levels=DIKW_LEVELS,
                level_descriptions=DIKW_LEVEL_DESCRIPTIONS,
                context=context or {},
            )
        except Exception as e:
            logger.error(f"Failed to render system prompt: {e}")
            return self._get_fallback_system_prompt()
    
    def _get_fallback_system_prompt(self) -> str:
        """Fallback system prompt if templates aren't available."""
        return """You are a knowledge synthesizer that helps transform raw signals into structured wisdom.

The DIKW Pyramid:
- Data: Raw facts and observations
- Information: Contextualized data with meaning
- Knowledge: Actionable insights and patterns
- Wisdom: Strategic principles and timeless lessons

Your role is to help users promote content up this pyramid, maintaining quality and depth at each level."""
    
    async def run(
        self,
        action: str,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a DIKW operation.
        
        Args:
            action: One of 'promote', 'merge', 'validate', 'summarize', 'refine', 'generate_tags'
            data: Action-specific data
            context: Optional context for the operation
        
        Returns:
            Dict with operation result and status
        """
        context = context or {}
        
        action_handlers = {
            'promote': self._handle_promote,
            'promote_signal': self._handle_promote_signal,
            'merge': self._handle_merge,
            'validate': self._handle_validate,
            'summarize': self._handle_summarize,
            'refine': self._handle_refine,
            'generate_tags': self._handle_generate_tags,
            'ai_review': self._handle_ai_review,
        }
        
        handler = action_handlers.get(action)
        if not handler:
            return {
                'success': False,
                'error': f"Unknown action: {action}. Valid actions: {list(action_handlers.keys())}"
            }
        
        try:
            return await handler(data, context)
        except Exception as e:
            logger.error(f"DIKW action '{action}' failed: {e}")
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # ACTION HANDLERS
    # =========================================================================
    
    async def _handle_promote_signal(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Promote a signal to the DIKW pyramid (starts as Data level)."""
        signal_text = data.get("signal_text", "")
        signal_type = data.get("signal_type", "")
        meeting_id = data.get("meeting_id")
        target_level = data.get("level", "data")
        
        if not signal_text:
            return {'success': False, 'error': "Signal text is required"}
        
        # Generate AI summary appropriate for the level
        summary = await self._generate_level_summary(signal_text, target_level)
        
        # Auto-generate tags
        tags = await self._generate_tags(signal_text, target_level, signal_type)
        
        return {
            'success': True,
            'level': target_level,
            'content': signal_text,
            'summary': summary,
            'tags': tags,
            'signal_type': signal_type,
            'meeting_id': meeting_id,
        }
    
    async def _handle_promote(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Promote a DIKW item to the next level."""
        content = data.get("content", "")
        current_level = data.get("from_level", "data")
        to_level = data.get("to_level")
        provided_content = data.get("promoted_content")
        provided_summary = data.get("summary")
        
        if not content:
            return {'success': False, 'error': "Content is required"}
        
        if current_level == 'wisdom' and not to_level:
            return {'success': False, 'error': "Already at highest level"}
        
        # Determine target level
        next_level = to_level if to_level else DIKW_NEXT_LEVEL.get(current_level, 'wisdom')
        
        # Use provided content or keep original
        new_content = provided_content if provided_content else content
        
        # Generate AI synthesis if not provided
        if provided_summary:
            new_summary = provided_summary
        else:
            new_summary = await self._synthesize_promotion(new_content, next_level)
        
        # Generate tags for the promoted content
        existing_tags = data.get("tags", "")
        new_tags = await self._generate_tags(new_content, next_level, existing_tags)
        
        return {
            'success': True,
            'from_level': current_level,
            'to_level': next_level,
            'content': new_content,
            'summary': new_summary,
            'tags': new_tags,
        }
    
    async def _handle_merge(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge multiple items at the same level into a synthesized higher-level item."""
        items = data.get("items", [])
        
        if len(items) < 2:
            return {'success': False, 'error': "Need at least 2 items to merge"}
        
        # Verify all items are at same level
        levels = set(item.get('level') for item in items)
        if len(levels) > 1:
            return {'success': False, 'error': "All items must be at the same level"}
        
        current_level = items[0].get('level', 'data')
        if current_level == 'wisdom':
            next_level = 'wisdom'  # Merge wisdom into mega-wisdom
        else:
            next_level = DIKW_NEXT_LEVEL[current_level]
        
        # Combine content for synthesis
        combined_content = "\n\n".join([
            f"- {item.get('content', '')}" for item in items
        ])
        combined_summaries = "\n".join([
            f"- {item.get('summary', '')}" for item in items if item.get('summary')
        ])
        
        # Generate merged summary
        merged_summary = await self._synthesize_merge(
            items, current_level, next_level, combined_content, combined_summaries
        )
        
        # Calculate merged confidence
        confidences = [item.get('confidence', 0.5) for item in items]
        avg_confidence = sum(confidences) / len(confidences)
        new_confidence = min(1.0, avg_confidence + 0.15)
        
        # Total validations
        total_validations = sum(item.get('validation_count', 0) for item in items)
        
        return {
            'success': True,
            'merged_count': len(items),
            'from_level': current_level,
            'to_level': next_level,
            'content': combined_content,
            'summary': merged_summary,
            'confidence': new_confidence,
            'validation_count': total_validations,
        }
    
    async def _handle_validate(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle validation/invalidation of a DIKW item."""
        action = data.get("action", "validate")
        current_confidence = data.get("confidence", 0.5)
        current_validations = data.get("validation_count", 0)
        
        if action == "validate":
            new_confidence = min(1.0, current_confidence + 0.1)
            new_validations = current_validations + 1
        elif action == "invalidate":
            new_confidence = max(0.0, current_confidence - 0.1)
            new_validations = max(0, current_validations - 1)
        elif action == "archive":
            return {
                'success': True,
                'action': 'archive',
                'status': 'archived',
            }
        else:
            return {'success': False, 'error': f"Unknown validation action: {action}"}
        
        return {
            'success': True,
            'action': action,
            'confidence': new_confidence,
            'validation_count': new_validations,
        }
    
    async def _handle_summarize(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate AI summary for DIKW content."""
        content = data.get("content", "")
        level = data.get("level", "data")
        
        if not content:
            return {'success': False, 'error': "Content is required"}
        
        summary = await self._generate_level_summary(content, level)
        
        return {
            'success': True,
            'summary': summary,
            'level': level,
        }
    
    async def _handle_refine(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use AI to refine/improve DIKW content."""
        content = data.get("content", "")
        action = data.get("refine_action", "clarify")
        custom_prompt = data.get("prompt")
        
        if not content:
            return {'success': False, 'error': "Content is required"}
        
        prompt = custom_prompt or f"Refine this content ({action}): {content}"
        
        try:
            refined = await self._call_llm_text(prompt)
            return {
                'success': True,
                'refined': refined,
                'action': action,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _handle_generate_tags(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate tags for DIKW content."""
        content = data.get("content", "")
        level = data.get("level", "data")
        existing_tags = data.get("existing_tags", "")
        
        if not content:
            return {'success': False, 'error': "Content is required"}
        
        tags = await self._generate_tags(content, level, existing_tags)
        
        return {
            'success': True,
            'tags': tags,
        }
    
    async def _handle_ai_review(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """AI review and suggest improvements for DIKW items."""
        items = data.get("items", [])
        
        if not items:
            return {'success': True, 'reviews': []}
        
        # Build context for AI
        items_summary = "\n".join([
            f"[ID:{i.get('id')}] ({i.get('level')}) Content: {i.get('content', '')[:150]}... | Summary: {(i.get('summary') or 'None')[:80]}..."
            for i in items[:20]
        ])
        
        prompt = f"""Review these DIKW pyramid items and suggest improvements to their content (nugget name) and summaries.
Focus on clarity, specificity, and appropriate level of abstraction for each DIKW level.

Items to review:
{items_summary}

For each item that needs improvement, provide a JSON object with:
- id: the item ID
- improved_content: a clearer, more specific content/name (keep concise)
- improved_summary: a better summary appropriate for the DIKW level
- reason: brief explanation of what was improved

Return a JSON array of improvements (only include items that need changes):
"""
        
        try:
            response = await self._call_llm_text(prompt)
            result = json.loads(response.strip().strip('```json').strip('```'))
            
            reviews = []
            for review in result[:10]:
                item_id = review.get("id")
                item = next((i for i in items if i.get("id") == item_id), None)
                if item:
                    reviews.append({
                        "id": item_id,
                        "level": item.get("level"),
                        "current_content": item.get("content", "")[:100],
                        "current_summary": (item.get("summary") or "")[:80],
                        "improved_content": review.get("improved_content", item.get("content")),
                        "improved_summary": review.get("improved_summary", item.get("summary") or ""),
                        "reason": review.get("reason", "Improved for clarity")
                    })
            
            return {'success': True, 'reviews': reviews}
        except Exception as e:
            logger.error(f"AI review failed: {e}")
            return {'success': True, 'reviews': []}
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    async def _generate_level_summary(self, content: str, level: str) -> str:
        """Generate a summary appropriate for the DIKW level."""
        level_prompts = {
            'data': f"Briefly describe this raw data point in one clear sentence:\n\n{content}",
            'information': f"Explain the context and significance of this information:\n\n{content}",
            'knowledge': f"What actionable insight or pattern does this represent?\n\n{content}",
            'wisdom': f"What strategic principle or lesson can be derived from this?\n\n{content}"
        }
        
        prompt = level_prompts.get(level, level_prompts['data'])
        
        try:
            return await self._call_llm_text(prompt)
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return content[:200]
    
    async def _synthesize_promotion(self, content: str, to_level: str) -> str:
        """Generate synthesis for promoting content to a new level."""
        prompt = SYNTHESIS_PROMPTS.get(to_level, SYNTHESIS_PROMPTS['information'])
        prompt = prompt.format(content=content)
        
        try:
            return await self._call_llm_text(prompt)
        except Exception as e:
            logger.error(f"Failed to synthesize promotion: {e}")
            return f"Promoted to {to_level}"
    
    async def _synthesize_merge(
        self,
        items: List[Dict],
        current_level: str,
        next_level: str,
        combined_content: str,
        combined_summaries: str,
    ) -> str:
        """Generate synthesis for merging multiple items."""
        prompt = MERGE_PROMPT.format(
            count=len(items),
            current_level=current_level,
            next_level=next_level,
            combined_content=combined_content,
            combined_summaries=combined_summaries,
        )
        
        try:
            return await self._call_llm_text(prompt)
        except Exception as e:
            logger.error(f"Failed to synthesize merge: {e}")
            return f"Merged {len(items)} items: " + "; ".join([
                (i.get('summary') or '')[:50] for i in items if i.get('summary')
            ])
    
    async def _generate_tags(
        self, 
        content: str, 
        level: str, 
        existing_tags: str = ""
    ) -> str:
        """Generate relevant tags for DIKW content using AI."""
        prompt = f"""Generate 3-5 relevant, concise tags for this {level}-level DIKW item.

Content: {content[:500]}

Rules:
- Tags should be lowercase, single words or hyphenated-phrases
- Focus on: topic, domain, type of insight, actionability
- Examples: architecture, team-process, sprint-planning, technical-debt, decision
{f"Existing tags to consider: {existing_tags}" if existing_tags else ""}

Return ONLY comma-separated tags, nothing else:"""
        
        try:
            tags = await self._call_llm_text(prompt)
            # Clean up the response
            tags = tags.strip().replace('"', '').replace("'", '')
            return tags
        except Exception as e:
            logger.error(f"Failed to generate tags: {e}")
            return ""
    
    async def _call_llm_text(self, prompt: str) -> str:
        """Call LLM and get text response."""
        # Get model from router
        model = "gpt-4o-mini"
        if self.model_router:
            selection = self.model_router.select("synthesis", agent_name="dikw_synthesizer")
            model = selection.model
        
        if self.llm_client:
            messages = [{"role": "user", "content": prompt}]
            response = await self._call_llm(messages, model=model)
            return response.get("content", "") if isinstance(response, dict) else str(response)
        else:
            # Fallback to direct call
            from ...llm import ask as ask_llm
            return ask_llm(prompt, model=model)
    
    # =========================================================================
    # STATIC UTILITIES
    # =========================================================================
    
    @staticmethod
    def get_next_level(current_level: str) -> Optional[str]:
        """Get the next level in the DIKW hierarchy."""
        return DIKW_NEXT_LEVEL.get(current_level)
    
    @staticmethod
    def get_prev_level(current_level: str) -> Optional[str]:
        """Get the previous level in the DIKW hierarchy."""
        return DIKW_PREV_LEVEL.get(current_level)
    
    @staticmethod
    def is_valid_level(level: str) -> bool:
        """Check if a level is valid."""
        return level in DIKW_LEVELS
    
    @staticmethod
    def get_level_description(level: str) -> str:
        """Get description for a DIKW level."""
        return DIKW_LEVEL_DESCRIPTIONS.get(level, "Unknown level")
    
    @staticmethod
    def normalize_confidence(confidence: float) -> float:
        """Normalize confidence to 0-1 range (handles 0-100 input)."""
        if confidence > 1:
            return confidence / 100
        return confidence


__all__ = ["DIKWSynthesizerAgent"]
