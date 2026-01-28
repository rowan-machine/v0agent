# src/app/agents/arjuna/core.py
"""
Arjuna Agent Core - Main agent class using composition with mixins.

This module contains the core ArjunaAgent class that orchestrates
all the specialized mixins for different capabilities.

NOTE: This is a new implementation using mixin composition.
The original monolithic implementation is in _arjuna_core.py.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import logging

from jinja2 import Environment, FileSystemLoader

from ..base import BaseAgent, AgentConfig
from ..context import get_sprint_context, format_sprint_context_for_prompt

# Import constants
from .constants import (
    AVAILABLE_MODELS,
    SYSTEM_PAGES,
    MODEL_ALIASES,
    FOCUS_KEYWORDS,
)

# Import mixins for composition
from .context import ArjunaContextMixin
from .focus import ArjunaFocusMixin
from .standup import ArjunaStandupMixin
from .tools import ArjunaToolsMixin
from .mcp_handler import ArjunaMCPMixin
from .chain_executor import ArjunaChainMixin
from .intents import ArjunaIntentMixin
from .tickets import ArjunaTicketMixin

# Import MCP command utilities
from ...mcp.commands import MCP_COMMANDS, MCP_INFERENCE_PATTERNS
from ...mcp.command_parser import parse_mcp_command, infer_mcp_command, get_command_help

logger = logging.getLogger(__name__)


class ArjunaAgentCore(
    BaseAgent,
    ArjunaContextMixin,
    ArjunaFocusMixin,
    ArjunaStandupMixin,
    ArjunaToolsMixin,
    ArjunaMCPMixin,
    ArjunaChainMixin,
    ArjunaIntentMixin,
    ArjunaTicketMixin,
):
    """
    Arjuna - SignalFlow's smart conversational assistant.
    
    Uses mixin composition for clean separation of concerns:
    - ArjunaContextMixin: System context gathering
    - ArjunaFocusMixin: Focus recommendations
    - ArjunaStandupMixin: Standup logging
    - ArjunaToolsMixin: Helper utilities
    - ArjunaMCPMixin: MCP command handling
    - ArjunaChainMixin: Chain command execution
    - ArjunaIntentMixin: Intent parsing/execution
    - ArjunaTicketMixin: Ticket CRUD operations
    
    Capabilities:
    - Parse natural language into structured intents
    - Parse MCP short notation commands for quick actions
    - Create and update tickets
    - Track accountability items
    - Log standups
    - Change AI model settings
    - Update sprint configuration
    - Provide focus recommendations
    - Navigate users to relevant pages
    - Answer questions about the app
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
        """
        Initialize the Arjuna agent.
        
        Args:
            config: Agent configuration
            llm_client: LLM client for AI calls
            tool_registry: Registry of available tools
            model_router: Router for model selection
            guardrails: Safety guardrails
            db_connection: Database connection (optional)
        """
        super().__init__(
            config=config,
            llm_client=llm_client,
            tool_registry=tool_registry,
            model_router=model_router,
            guardrails=guardrails,
        )
        self.db_connection = db_connection
        self._thread_id = None
        # Note: last_run_id is managed by BaseAgent as a property
        
        # Initialize Jinja2 environment for prompt templates
        prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts" / "agents" / "arjuna"
        if prompts_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
            logger.info(f"Loaded Arjuna prompts from {prompts_dir}")
        else:
            self.jinja_env = None
            logger.warning(f"Arjuna prompts directory not found: {prompts_dir}")
    
    def get_system_prompt(self) -> str:
        """Generate system prompt from Jinja2 template."""
        if not self.jinja_env:
            return self._get_fallback_system_prompt()
        
        try:
            template = self.jinja_env.get_template("system.jinja2")
            return template.render(
                pages=SYSTEM_PAGES,
                sprint=None,  # Will be filled by context
                current_model="gpt-4o-mini",
                available_models=AVAILABLE_MODELS,
                ticket_stats={},
                recent_tickets=[],
                waiting_for=[],
                todays_standups=[],
                history=[],
            )
        except Exception as e:
            logger.error(f"Failed to render system prompt: {e}")
            return self._get_fallback_system_prompt()
    
    def _get_fallback_system_prompt(self) -> str:
        """Fallback system prompt if templates aren't available."""
        return """You are Arjuna 🙏, a smart assistant for the SignalFlow productivity app.
        
Greet users with "Hare Krishna!" when appropriate.
Help with: creating tickets, tracking accountability, navigating the app,
updating sprint settings, and answering questions about features.

Be warm, helpful, and proactive. Make reasonable assumptions rather than
asking too many questions."""
    
    async def run(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and return the response.
        
        Supports both natural language and MCP short notation commands.
        
        Args:
            message: User's message (natural language or /command)
            conversation_history: Previous messages in the conversation
            context: Current system context (sprint, tickets, etc.)
        
        Returns:
            Dict with response, success, action, and optional navigation
        """
        conversation_history = conversation_history or []
        context = context or self._get_system_context()
        
        # Check for MCP short notation commands first (explicit /command or @agent)
        mcp_cmd = parse_mcp_command(message)
        if mcp_cmd:
            return await self._handle_mcp_command(mcp_cmd, context)
        
        # Check for inferred MCP commands from natural language
        inferred_cmd = infer_mcp_command(message, context)
        if inferred_cmd and inferred_cmd.get("confidence", 0) >= 0.6:
            logger.info(
                f"Inferred MCP command: {inferred_cmd['command']}/{inferred_cmd['subcommand']} "
                f"(confidence: {inferred_cmd['confidence']:.2f})"
            )
            return await self._handle_mcp_command(inferred_cmd, context)
        
        # Check for focus queries (special handling)
        if self._is_focus_query(message):
            return await self._handle_focus_query()
        
        # Parse user intent
        intent_data = await self._parse_intent(message, context, conversation_history)
        
        # Check for clarifications needed
        if intent_data.get("clarifications") and intent_data.get("intent") == "needs_clarification":
            return {
                "response": intent_data.get("response_text", "I need more information."),
                "clarifications": intent_data.get("clarifications"),
                "needs_input": True,
                "success": True,
            }
        
        # Execute the intent
        execution_result = await self._execute_intent(intent_data)
        
        if not execution_result.get("success"):
            return {
                "response": f"Sorry, I encountered an error: {execution_result.get('error')}",
                "success": False,
            }
        
        # Build response
        response_text = intent_data.get("response_text", "Done!")
        response_text = self._enhance_response(response_text, execution_result)
        
        # Generate follow-up suggestions
        follow_ups = self._get_follow_up_suggestions(
            execution_result.get("action"),
            intent_data.get("intent"),
            execution_result,
        )
        
        return {
            "response": response_text,
            "success": True,
            "action": execution_result.get("action"),
            "result": execution_result,
            "suggested_page": intent_data.get("suggested_page") or execution_result.get("navigate_to"),
            "follow_ups": follow_ups,
        }
    
    def _enhance_response(self, response_text: str, execution_result: Dict[str, Any]) -> str:
        """Enhance response with execution details."""
        action = execution_result.get("action")
        
        if action == "create_ticket":
            ticket = execution_result.get("ticket", {})
            if ticket:
                ticket_id = ticket.get("ticket_id", "")
                response_text = f"✅ Created ticket **{ticket_id}**: {ticket.get('title', '')}\n\n{response_text}"
        
        elif action == "update_ticket":
            ticket = execution_result.get("ticket", {})
            if ticket:
                response_text = f"✅ Updated ticket **{ticket.get('ticket_id', '')}**\n\n{response_text}"
        
        elif action == "list_tickets":
            tickets = execution_result.get("tickets", [])
            if tickets:
                count = len(tickets)
                response_text = f"📋 Found **{count}** ticket{'s' if count != 1 else ''}\n\n{response_text}"
        
        return response_text
    
    def _get_follow_up_suggestions(
        self,
        action: Optional[str],
        intent: Optional[str],
        result: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Generate contextual follow-up suggestions based on action performed."""
        
        default_suggestions = [
            {"emoji": "📋", "text": "My Tickets", "message": "What are my open tickets?"},
            {"emoji": "🎯", "text": "Focus", "message": "What should I focus on today?"},
            {"emoji": "💡", "text": "Help", "message": "What else can you help me with?"},
        ]
        
        if action == "create_ticket":
            return [
                {"emoji": "➕", "text": "Create Another", "message": "Create a task for "},
                {"emoji": "📋", "text": "View Tickets", "message": "Show me all my tickets"},
                {"emoji": "🎯", "text": "High Priority", "message": "What are my high priority tickets?"},
            ]
        
        elif action == "list_tickets":
            tickets = result.get("tickets", [])
            suggestions = [{"emoji": "➕", "text": "New Task", "message": "Create a task for "}]
            if any(t.get("status") == "blocked" for t in tickets):
                suggestions.append({"emoji": "🚫", "text": "Unblock", "message": "Help me unblock a ticket"})
            if any(t.get("status") == "in_progress" for t in tickets):
                suggestions.append({"emoji": "✅", "text": "Complete", "message": "Mark a ticket as done"})
            suggestions.append({"emoji": "🔍", "text": "Filter", "message": "Show blocked tickets"})
            return suggestions[:4]
        
        elif action == "change_model":
            return [
                {"emoji": "🤖", "text": "Try GPT-4o", "message": "Switch to GPT-4o"},
                {"emoji": "🧠", "text": "Try Claude", "message": "Switch to Claude Sonnet"},
                {"emoji": "⚡", "text": "Fast Model", "message": "Switch to GPT-4o-mini"},
            ]
        
        elif action == "focus_recommendations":
            return [
                {"emoji": "📋", "text": "View Tickets", "message": "Show me all my tickets"},
                {"emoji": "🚫", "text": "Blockers", "message": "What are my blocked tickets?"},
                {"emoji": "➕", "text": "New Task", "message": "Create a task for "},
                {"emoji": "📊", "text": "Sprint", "message": "What is the sprint status?"},
            ]
        
        elif intent in ("help", "explain"):
            return [
                {"emoji": "📋", "text": "My Tickets", "message": "What are my tickets?"},
                {"emoji": "🤖", "text": "Change Model", "message": "Switch to GPT-4o"},
                {"emoji": "📅", "text": "Meetings", "message": "Search meetings for "},
                {"emoji": "➕", "text": "New Task", "message": "Create a task for "},
            ]
        
        return default_suggestions
    
    async def quick_ask(
        self,
        topic: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Quick AI questions from dashboard.
        
        Args:
            topic: Predefined topic (blockers, decisions, action_items, etc.)
            query: Custom query string
        
        Returns:
            Dict with response, success status
        """
        from ...llm import _openai_client_once
        
        # Build prompt based on topic or query
        if topic:
            topic_prompts = {
                "blockers": "What are my current blockers and how can I resolve them?",
                "decisions": "What recent decisions should I be aware of?",
                "action_items": "What are my pending action items?",
                "priorities": "What should be my top priorities today?",
                "sprint_status": "What is the current sprint status?",
            }
            prompt = topic_prompts.get(topic, query or "What can I help you with?")
        else:
            prompt = query or "What can I help you with?"
        
        # Get context
        context = self._get_system_context()
        
        # Build system prompt
        system_prompt = f"""You are Arjuna, a helpful assistant for SignalFlow.
        
Current context:
- Sprint: {context.get('sprint', {}).get('name', 'Unknown')}
- Open tickets: {context.get('ticket_stats', {}).get('total', 0)}
- Blocked: {context.get('ticket_stats', {}).get('blocked', 0)}

Be concise but helpful. Use emojis sparingly."""
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            
            resp = _openai_client_once().chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            
            return {
                "response": resp.choices[0].message.content.strip(),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Quick ask failed: {e}")
            return {
                "response": f"Sorry, I encountered an error: {str(e)}",
                "success": False,
            }
    
    async def ask_llm(
        self,
        prompt: str,
        task_type: str = "general",
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Ask the LLM a question.
        
        Args:
            prompt: The question/prompt
            task_type: Type of task (for model routing)
            system_prompt: Optional system prompt override
        
        Returns:
            LLM response text
        """
        from ...llm import _openai_client_once
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        resp = _openai_client_once().chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )
        
        return resp.choices[0].message.content.strip()


# Alias for backward compatibility
ArjunaAgentComposed = ArjunaAgentCore
