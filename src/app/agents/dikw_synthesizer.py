"""
DIKW Synthesizer Agent - Knowledge Pyramid Management (Checkpoint 2.5)

AI-powered knowledge management that handles:
- Signal promotion through DIKW levels (Data → Information → Knowledge → Wisdom)
- Multi-item synthesis and merging
- Confidence-based validation
- AI-assisted content refinement
- Tag generation and clustering
- Evolution tracking

Extracted from main.py following the migration plan.
Maintains backward compatibility through adapter functions.

DIKW Pyramid Levels:
- Data: Raw signals and observations
- Information: Contextualized and structured data
- Knowledge: Actionable insights and patterns
- Wisdom: Strategic principles and timeless lessons
"""

from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import json
import logging

from jinja2 import Environment, FileSystemLoader
from ..agents.base import BaseAgent, AgentConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DIKW CONSTANTS - Moved from main.py
# =============================================================================

DIKW_LEVELS = ['data', 'information', 'knowledge', 'wisdom']

DIKW_NEXT_LEVEL = {
    'data': 'information', 
    'information': 'knowledge', 
    'knowledge': 'wisdom'
}

DIKW_PREV_LEVEL = {
    'information': 'data',
    'knowledge': 'information',
    'wisdom': 'knowledge'
}

# Level descriptions for context
DIKW_LEVEL_DESCRIPTIONS = {
    'data': "Raw facts, observations, and signals without context",
    'information': "Contextualized data with meaning and structure",
    'knowledge': "Actionable insights, patterns, and applied understanding",
    'wisdom': "Strategic principles, timeless lessons, and guiding truths"
}

# Prompts for each level (used in promotion and summarization)
LEVEL_PROMPTS = {
    'data': "Briefly describe this raw signal in one sentence",
    'information': "Explain the context and meaning of this signal",
    'knowledge': "What actionable insight or pattern does this represent?",
    'wisdom': "What strategic principle or lesson can be derived from this?"
}

PROMOTION_PROMPTS = {
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

SYNTHESIS_PROMPTS = {
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


class DIKWSynthesizerAgent(BaseAgent):
    """
    DIKW Synthesizer - SignalFlow's knowledge pyramid manager.
    
    Capabilities:
    - Promote signals through DIKW levels
    - Merge multiple items into synthesized insights
    - Validate and track confidence scores
    - Generate AI-powered summaries and tags
    - Track evolution history
    - Provide mindmap visualization data
    
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
        prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts" / "agents" / "dikw_synthesizer"
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
            from ..llm import ask as ask_llm
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
    
    @staticmethod
    def build_mindmap_tree(items: List[Dict]) -> Dict[str, Any]:
        """Build hierarchical tree structure for mindmap visualization."""
        tree = {
            "name": "Knowledge",
            "type": "root",
            "children": []
        }
        
        # Group by level
        levels = {level: [] for level in DIKW_LEVELS}
        for item in items:
            level = item.get('level', 'data')
            if level in levels:
                levels[level].append(item)
        
        # Build tree
        for level in DIKW_LEVELS:
            level_node = {
                "name": level.capitalize(),
                "type": "level",
                "level": level,
                "children": []
            }
            for item in levels[level][:20]:  # Limit per level
                content = item.get('content', '')
                level_node["children"].append({
                    "id": item.get('id'),
                    "name": content[:40] + ('...' if len(content) > 40 else ''),
                    "type": "item",
                    "level": level,
                    "summary": item.get('summary', ''),
                    "tags": item.get('tags', '')
                })
            tree["children"].append(level_node)
        
        return tree
    
    @staticmethod
    def build_graph_data(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Build nodes and links for force-directed graph visualization."""
        nodes = [{"id": "root", "name": "Knowledge", "type": "root", "level": "root"}]
        links = []
        
        # Group by level
        levels = {level: [] for level in DIKW_LEVELS}
        for item in items:
            level = item.get('level', 'data')
            if level in levels:
                levels[level].append(item)
        
        for level in DIKW_LEVELS:
            level_id = f"level_{level}"
            nodes.append({
                "id": level_id, 
                "name": level.capitalize(), 
                "type": "level", 
                "level": level
            })
            links.append({"source": "root", "target": level_id})
            
            for item in levels[level][:15]:
                item_id = f"item_{item.get('id')}"
                content = item.get('content', '')
                nodes.append({
                    "id": item_id,
                    "name": content[:30] + ('...' if len(content) > 30 else ''),
                    "type": "item",
                    "level": level,
                    "summary": item.get('summary', '')
                })
                links.append({"source": level_id, "target": item_id})
        
        return nodes, links
    
    @staticmethod
    def build_tag_clusters(items: List[Dict]) -> Dict[str, List[Dict]]:
        """Build tag clusters from items."""
        tag_clusters = {}
        for item in items:
            tags = (item.get('tags') or '').split(',') if item.get('tags') else []
            for tag in tags:
                tag = tag.strip().lower()
                if tag:
                    if tag not in tag_clusters:
                        tag_clusters[tag] = []
                    tag_clusters[tag].append({
                        "id": item.get('id'),
                        "level": item.get('level'),
                        "content": (item.get('content') or '')[:50]
                    })
        return tag_clusters


# =============================================================================
# MODULE-LEVEL SINGLETON AND ADAPTER FUNCTIONS
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
    tree = DIKWSynthesizerAgent.build_mindmap_tree(items)
    nodes, links = DIKWSynthesizerAgent.build_graph_data(items)
    tag_clusters = DIKWSynthesizerAgent.build_tag_clusters(items)
    
    # Count stats
    levels = {level: [] for level in DIKW_LEVELS}
    for item in items:
        level = item.get('level', 'data')
        if level in levels:
            levels[level].append(item)
    
    counts = {
        "data": len(levels['data']),
        "information": len(levels['information']),
        "knowledge": len(levels['knowledge']),
        "wisdom": len(levels['wisdom']),
        "tags": len(tag_clusters),
        "connections": len(links)
    }
    
    return {
        "tree": tree,
        "nodes": nodes,
        "links": links,
        "tagClusters": tag_clusters,
        "counts": counts
    }


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
