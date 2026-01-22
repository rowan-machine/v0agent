"""
Career Coach Agent - SignalFlow Career Development Assistant (Checkpoint 2.3)

AI-powered career coaching that provides:
- Growth suggestions based on profile and context
- Standup analysis with sentiment and feedback
- Career insights from skills and projects
- Conversational career guidance

Extracted from api/career.py following the migration plan.
Maintains backward compatibility through an adapter layer.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json
import logging
import re

from jinja2 import Environment, FileSystemLoader
from ..agents.base import BaseAgent, AgentConfig

logger = logging.getLogger(__name__)


# =============================================================================
# CAREER CAPABILITIES - Moved from api/career.py
# =============================================================================

CAREER_REPO_CAPABILITIES = {
    "capabilities": [
        "Meeting ingestion with signal extraction (decisions, action items, blockers, risks, ideas)",
        "DIKW pyramid promotion and synthesis for validated knowledge",
        "Tickets with AI summaries, decomposition, and implementation planning",
        "Quick AI updates with per-item actions (approve, reject, archive, create task, waiting-for)",
        "Accountability (waiting-for) tracking and status management",
        "Search and query across meetings and documents",
        "Workflow mode tracking with sprint-aligned checklists",
        "AI memory for retained context",
        "Career profile + AI-generated growth suggestions",
        "Session authentication and settings control",
    ],
    "tools_and_skills": [
        "Python 3.11 with FastAPI",
        "SQLite for local-first storage",
        "Jinja2 templates + Tailwind CSS for UI",
        "OpenAI-powered LLM integration",
        "Markdown rendering for summaries and notes",
    ],
    "unlocks_for_data_engineers": [
        "Turn meetings into prioritized, trackable work items",
        "Promote raw signals into structured knowledge (DIKW)",
        "Decompose data platform tickets into executable subtasks",
        "Track blockers/risks and accountability follow-ups",
        "Maintain sprint modes to separate planning vs execution",
        "Use AI quick asks for status, decisions, and action items",
        "Centralize project context for faster onboarding",
    ],
}


def format_capabilities_context() -> str:
    """Format capabilities as context string for prompts."""
    caps = "\n".join([f"- {c}" for c in CAREER_REPO_CAPABILITIES["capabilities"]])
    tools = "\n".join([f"- {t}" for t in CAREER_REPO_CAPABILITIES["tools_and_skills"]])
    unlocks = "\n".join([f"- {u}" for u in CAREER_REPO_CAPABILITIES["unlocks_for_data_engineers"]])
    return (
        "Tool capabilities:\n" + caps + "\n\n"
        "Architecture, tools, and skills:\n" + tools + "\n\n"
        "Practical unlocks for data engineers:\n" + unlocks
    )


class CareerCoachAgent(BaseAgent):
    """
    Career Coach - SignalFlow's career development assistant.
    
    Capabilities:
    - Generate personalized growth suggestions
    - Analyze standups with sentiment detection
    - Provide career insights from skills/projects
    - Conversational career coaching
    - Connect work context to career goals
    
    Prompts:
    - system.jinja2: Main career coach persona
    - generate_suggestions.jinja2: Growth opportunity generation
    - analyze_standup.jinja2: Standup feedback with sentiment
    - generate_insights.jinja2: Career insight summaries
    - summarize_chat.jinja2: Chat summary generation
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
        prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts" / "agents" / "career_coach"
        if prompts_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
            logger.info(f"Loaded Career Coach prompts from {prompts_dir}")
        else:
            self.jinja_env = None
            logger.warning(f"Career Coach prompts directory not found: {prompts_dir}")
    
    def get_system_prompt(self, profile: Dict = None, context: Dict = None) -> str:
        """Generate system prompt from Jinja2 template."""
        if not self.jinja_env:
            return self._get_fallback_system_prompt()
        
        try:
            template = self.jinja_env.get_template("system.jinja2")
            return template.render(
                profile=profile or {},
                context=context or {},
                capabilities_context=format_capabilities_context(),
            )
        except Exception as e:
            logger.error(f"Failed to render system prompt: {e}")
            return self._get_fallback_system_prompt()
    
    def _get_fallback_system_prompt(self) -> str:
        """Fallback system prompt if templates aren't available."""
        return """You are a friendly, supportive career coach. Think of yourself as a mentor 
catching up with someone over coffee.

Be warm, encouraging, and practical. If they share an accomplishment, celebrate it!
If they're struggling, empathize first, then offer gentle guidance.
Keep responses conversational - think "wise friend" not "corporate HR presentation"."""
    
    async def run(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a career coaching message.
        
        Args:
            message: User's message
            conversation_history: Previous messages
            context: Current context (profile, tickets, etc.)
        
        Returns:
            Dict with response, success, and optional summary
        """
        conversation_history = conversation_history or []
        context = context or {}
        
        # Get profile from context or database
        profile = context.get("profile") or await self._load_profile()
        
        # Build system prompt with context
        system_prompt = self.get_system_prompt(profile=profile, context=context)
        
        # Prepare messages for LLM
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for msg in conversation_history[-6:]:  # Last 6 messages
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        try:
            # Get model from router
            model = "gpt-4o-mini"
            if self.model_router:
                selection = self.model_router.select("coaching", agent_name="career_coach")
                model = selection.model
            
            # Call LLM
            if self.llm_client:
                response = await self._call_llm(messages, model=model)
            else:
                # Fallback to direct call
                from ..llm import ask as ask_llm
                response = ask_llm(message, model=model)
            
            # Generate summary for storage
            summary = await self._generate_summary(message, response)
            
            return {
                "response": response,
                "success": True,
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"Career chat failed: {e}")
            return {
                "response": f"I'm sorry, I encountered an error. Please try again. (Error: {str(e)})",
                "success": False,
                "error": str(e),
            }
    
    async def generate_suggestions(
        self,
        profile: Dict,
        context: Optional[Dict] = None,
        count: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate personalized career growth suggestions.
        
        Args:
            profile: Career profile dict
            context: Optional context (meetings, documents, tickets)
            count: Number of suggestions to generate
        
        Returns:
            Dict with suggestions list and status
        """
        context = context or {}
        
        # Build prompt
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("generate_suggestions.jinja2")
                prompt = template.render(
                    profile=profile,
                    context=context,
                    career_summary=context.get("career_summary"),
                    count=count,
                )
            except Exception as e:
                logger.error(f"Template error: {e}")
                prompt = self._build_suggestions_prompt_fallback(profile, context, count)
        else:
            prompt = self._build_suggestions_prompt_fallback(profile, context, count)
        
        try:
            # Get model
            model = "gpt-4o-mini"
            if self.model_router:
                selection = self.model_router.select("generation", agent_name="career_coach")
                model = selection.model
            
            # Call LLM
            from ..llm import ask as ask_llm
            response = ask_llm(prompt, model=model)
            
            # Parse JSON response
            suggestions = self._parse_suggestions_response(response)
            
            return {
                "success": True,
                "suggestions": suggestions,
                "count": len(suggestions),
            }
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")
            return {
                "success": False,
                "error": str(e),
                "suggestions": [],
            }
    
    async def analyze_standup(
        self,
        content: str,
        profile: Dict,
        tickets: List[Dict] = None,
        recent_standups: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a standup update with sentiment and feedback.
        
        Args:
            content: Standup content text
            profile: Career profile
            tickets: Active sprint tickets
            recent_standups: Previous standup entries
        
        Returns:
            Dict with sentiment, key_themes, and feedback
        """
        tickets = tickets or []
        recent_standups = recent_standups or []
        
        # Build prompt
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("analyze_standup.jinja2")
                prompt = template.render(
                    profile=profile,
                    tickets=tickets,
                    recent_standups=recent_standups,
                    content=content,
                )
            except Exception as e:
                logger.error(f"Template error: {e}")
                prompt = self._build_standup_prompt_fallback(content, profile, tickets, recent_standups)
        else:
            prompt = self._build_standup_prompt_fallback(content, profile, tickets, recent_standups)
        
        try:
            # Call LLM
            from ..llm import ask as ask_llm
            response = ask_llm(prompt, model="gpt-4o-mini")
            
            # Parse response
            result = self._parse_standup_response(response)
            result["success"] = True
            return result
        except Exception as e:
            logger.error(f"Failed to analyze standup: {e}")
            return {
                "success": False,
                "error": str(e),
                "sentiment": "neutral",
                "key_themes": "",
                "feedback": "Could not generate feedback.",
            }
    
    async def generate_insights(
        self,
        profile: Dict,
        skills: List[Dict] = None,
        projects: List[Dict] = None,
        ai_memories: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate career insights from skills and projects.
        
        Args:
            profile: Career profile
            skills: Tracked skills with proficiency
            projects: Completed projects
            ai_memories: AI implementation memories
        
        Returns:
            Dict with insights markdown
        """
        skills = skills or []
        projects = projects or []
        ai_memories = ai_memories or []
        
        # Build prompt
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("generate_insights.jinja2")
                prompt = template.render(
                    profile=profile,
                    skills=skills,
                    projects=projects,
                    ai_memories=ai_memories,
                )
            except Exception as e:
                logger.error(f"Template error: {e}")
                prompt = self._build_insights_prompt_fallback(profile, skills, projects, ai_memories)
        else:
            prompt = self._build_insights_prompt_fallback(profile, skills, projects, ai_memories)
        
        try:
            from ..llm import ask as ask_llm
            insights = ask_llm(prompt, model="gpt-4o-mini")
            
            return {
                "success": True,
                "insights": insights,
            }
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            return {
                "success": False,
                "error": str(e),
                "insights": "",
            }
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _load_profile(self) -> Dict:
        """Load career profile from database."""
        if not self.db_connection:
            return {}
        
        try:
            row = self.db_connection.execute(
                "SELECT * FROM career_profile WHERE id = 1"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return {}
    
    async def _call_llm(self, messages: List[Dict], model: str = "gpt-4o-mini") -> str:
        """Call LLM with messages."""
        if hasattr(self.llm_client, 'chat'):
            # OpenAI-style client
            response = await self.llm_client.chat.completions.create(
                model=model,
                messages=messages,
            )
            return response.choices[0].message.content
        else:
            # Fallback to simple ask
            from ..llm import ask as ask_llm
            combined = "\n".join([m["content"] for m in messages])
            return ask_llm(combined, model=model)
    
    async def _generate_summary(self, message: str, response: str) -> str:
        """Generate a summary of the chat exchange."""
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("summarize_chat.jinja2")
                prompt = template.render(message=message, response=response)
            except Exception:
                prompt = f"Summarize into 3-5 bullet points:\nUser: {message}\nAssistant: {response}"
        else:
            prompt = f"Summarize into 3-5 bullet points:\nUser: {message}\nAssistant: {response}"
        
        try:
            from ..llm import ask as ask_llm
            return ask_llm(prompt, model="gpt-4o-mini")
        except Exception:
            return ""
    
    def _parse_suggestions_response(self, response: str) -> List[Dict]:
        """Parse JSON suggestions from LLM response."""
        try:
            # Find JSON array in response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(response[json_start:json_end])
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Failed to parse suggestions JSON")
            return []
    
    def _parse_standup_response(self, response: str) -> Dict:
        """Parse standup analysis response."""
        lines = response.strip().split('\n')
        sentiment = 'neutral'
        key_themes = ''
        feedback_lines = []
        in_feedback = False
        
        for line in lines:
            if line.startswith('SENTIMENT:'):
                sentiment = line.replace('SENTIMENT:', '').strip().lower()
                if sentiment not in ('positive', 'neutral', 'blocked', 'struggling'):
                    sentiment = 'neutral'
            elif line.startswith('KEY_THEMES:'):
                key_themes = line.replace('KEY_THEMES:', '').strip()
            elif line.startswith('FEEDBACK:'):
                in_feedback = True
            elif in_feedback:
                feedback_lines.append(line)
        
        feedback = '\n'.join(feedback_lines).strip()
        if not feedback:
            feedback = response  # Use full response if parsing failed
        
        return {
            "sentiment": sentiment,
            "key_themes": key_themes,
            "feedback": feedback,
        }
    
    # =========================================================================
    # Fallback Prompt Builders
    # =========================================================================
    
    def _build_suggestions_prompt_fallback(
        self, profile: Dict, context: Dict, count: int
    ) -> str:
        """Fallback prompt for suggestions generation."""
        return f"""Based on this career profile, generate {count} specific, actionable growth opportunities:

Current Role: {profile.get('current_role', 'Not specified')}
Target Role: {profile.get('target_role', 'Not specified')}
Strengths: {profile.get('strengths', 'Not specified')}
Areas to Develop: {profile.get('weaknesses', 'Not specified')}
Goals: {profile.get('goals', 'Not specified')}

Return as JSON array with fields: suggestion_type, title, description, rationale, difficulty, time_estimate, related_goal"""
    
    def _build_standup_prompt_fallback(
        self, content: str, profile: Dict, tickets: List, recent_standups: List
    ) -> str:
        """Fallback prompt for standup analysis."""
        return f"""Analyze this standup update:

{content}

Provide SENTIMENT (positive/neutral/blocked/struggling), KEY_THEMES, and FEEDBACK."""
    
    def _build_insights_prompt_fallback(
        self, profile: Dict, skills: List, projects: List, ai_memories: List
    ) -> str:
        """Fallback prompt for insights generation."""
        return f"""Generate career insights (3-5 bullet points) for:

Role: {profile.get('current_role', 'Unknown')}
Target: {profile.get('target_role', 'Unknown')}
Skills: {len(skills)} tracked
Projects: {len(projects)} completed

Format as markdown with 🎯 Career Focus header."""


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_career_coach_instance: Optional[CareerCoachAgent] = None


def get_career_coach_agent(
    db_connection=None,
    llm_client=None,
    model_router=None,
    guardrails=None,
) -> CareerCoachAgent:
    """
    Get or create the Career Coach agent singleton.
    
    Args:
        db_connection: Database connection for data access
        llm_client: LLM client for AI calls
        model_router: Model router for model selection
        guardrails: Guardrails for safety checks
    
    Returns:
        CareerCoachAgent instance
    """
    global _career_coach_instance
    
    if _career_coach_instance is None:
        config = AgentConfig(
            name="career_coach",
            description="Career development coaching and growth suggestions",
            primary_model="gpt-4o-mini",
        )
        _career_coach_instance = CareerCoachAgent(
            config=config,
            db_connection=db_connection,
            llm_client=llm_client,
            model_router=model_router,
            guardrails=guardrails,
        )
    
    return _career_coach_instance


# =============================================================================
# ADAPTER FUNCTIONS - Backward compatibility with api/career.py
# =============================================================================

def get_career_capabilities() -> Dict:
    """Get career repo capabilities (adapter for backward compatibility)."""
    return CAREER_REPO_CAPABILITIES


async def career_chat_adapter(
    message: str,
    profile: Dict,
    context: Dict = None,
    include_context: bool = True,
    db_connection=None,
) -> Dict[str, Any]:
    """
    Adapter for career chat that matches api/career.py interface.
    
    Args:
        message: User message
        profile: Career profile dict
        context: Overlay context (meetings, documents, tickets)
        include_context: Whether to include context in prompt
        db_connection: Database connection
    
    Returns:
        Dict with status, response, and summary
    """
    agent = get_career_coach_agent(db_connection=db_connection)
    
    ctx = {}
    if include_context and context:
        ctx = context
    ctx["profile"] = profile
    
    result = await agent.run(message=message, context=ctx)
    
    return {
        "status": "ok" if result.get("success") else "error",
        "response": result.get("response", ""),
        "summary": result.get("summary", ""),
    }


async def generate_suggestions_adapter(
    profile: Dict,
    context: Dict = None,
    include_context: bool = True,
    db_connection=None,
) -> Dict[str, Any]:
    """
    Adapter for suggestion generation matching api/career.py interface.
    
    Returns:
        Dict with status, count, and created IDs (for DB storage)
    """
    agent = get_career_coach_agent(db_connection=db_connection)
    
    ctx = context if include_context else {}
    result = await agent.generate_suggestions(profile=profile, context=ctx)
    
    if result.get("success"):
        return {
            "status": "ok",
            "count": result.get("count", 0),
            "suggestions": result.get("suggestions", []),
        }
    else:
        return {
            "status": "error",
            "error": result.get("error", "Unknown error"),
        }


async def analyze_standup_adapter(
    content: str,
    profile: Dict,
    tickets: List[Dict] = None,
    recent_standups: List[Dict] = None,
    db_connection=None,
) -> Dict[str, Any]:
    """
    Adapter for standup analysis matching api/career.py interface.
    
    Returns:
        Dict with sentiment, key_themes, and feedback
    """
    agent = get_career_coach_agent(db_connection=db_connection)
    
    result = await agent.analyze_standup(
        content=content,
        profile=profile,
        tickets=tickets,
        recent_standups=recent_standups,
    )
    
    return {
        "status": "ok" if result.get("success") else "error",
        "sentiment": result.get("sentiment", "neutral"),
        "key_themes": result.get("key_themes", ""),
        "feedback": result.get("feedback", ""),
    }


# Export constants for backward compatibility
__all__ = [
    "CareerCoachAgent",
    "get_career_coach_agent",
    "CAREER_REPO_CAPABILITIES",
    "format_capabilities_context",
    # Adapter functions
    "get_career_capabilities",
    "career_chat_adapter",
    "generate_suggestions_adapter",
    "analyze_standup_adapter",
]
