"""
Ticket Agent - SignalFlow Ticket Management Intelligence

Handles AI-powered ticket operations:
- Summary generation (context-aware, tag-guided)
- Implementation planning (uses GPT-4o for premium quality)
- Task decomposition (atomic subtasks with estimates)

Follows PAGE-AGNOSTIC design pattern from Giga Memory:
- No page references - only data and tasks
- Functional adapters for backward compatibility
- Composable with other agents via task queue

Extracted from tickets.py following the migration plan.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json
import re
import logging

from jinja2 import Environment, FileSystemLoader
from ..agents.base import BaseAgent, AgentConfig
from ..llm import ask

logger = logging.getLogger(__name__)


# =============================================================================
# TICKET AGENT CLASS
# =============================================================================

class TicketAgent(BaseAgent):
    """
    Agent for intelligent ticket management.
    
    Provides AI-powered features:
    - Summary generation with tag-based formatting
    - Implementation planning with premium models
    - Task decomposition into atomic subtasks
    
    Design: Page-agnostic, modular, composable
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the ticket agent."""
        if config is None:
            config = AgentConfig(
                name="Ticket Agent",
                description="AI-powered ticket management and planning",
                primary_model="gpt-4o-mini",
            )
        super().__init__(config)
        
        # Initialize Jinja2 environment for prompts
        prompts_path = Path(__file__).parent.parent.parent.parent / "prompts" / "agents" / "ticket_agent"
        if prompts_path.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(prompts_path)),
                autoescape=False,
            )
        else:
            self.jinja_env = None
            logger.warning(f"Prompts directory not found: {prompts_path}")
    
    # =========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # =========================================================================
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for the ticket agent."""
        return """You are a ticket management assistant. Your role is to help with:
- Summarizing ticket information clearly and concisely
- Creating implementation plans with actionable steps
- Decomposing tickets into subtasks
- Identifying dependencies, risks, and blockers

Always provide structured, actionable output that helps developers understand what needs to be done."""
    
    async def run(self, action: str = "summarize", **kwargs) -> Any:
        """
        Main entry point for the ticket agent.
        
        Args:
            action: The action to perform - 'summarize', 'plan', or 'decompose'
            **kwargs: Additional arguments passed to the specific action
            
        Returns:
            Result from the requested action
        """
        if action == "summarize":
            ticket = kwargs.get("ticket", {})
            format_hint = kwargs.get("format_hint", "")
            return await self.summarize(ticket, format_hint)
        elif action == "plan":
            ticket = kwargs.get("ticket", {})
            return await self.generate_plan(ticket)
        elif action == "decompose":
            ticket = kwargs.get("ticket", {})
            max_subtasks = kwargs.get("max_subtasks", 5)
            return await self.decompose(ticket, max_subtasks)
        else:
            raise ValueError(f"Unknown action: {action}. Valid actions: summarize, plan, decompose")
    
    # =========================================================================
    # SUMMARY GENERATION
    # =========================================================================
    
    async def summarize(
        self,
        ticket: Dict[str, Any],
        format_hint: str = "",
    ) -> Dict[str, Any]:
        """
        Generate AI summary for a ticket.
        
        Supports tag-based formatting hints:
        - brief/short: 2-3 sentences
        - detailed/verbose: comprehensive coverage
        - technical/tech: implementation focus
        - business/stakeholder: business framing
        - bullet/bullets: bullet points
        - checklist: checkbox format
        
        Args:
            ticket: Ticket data dict (from database)
            format_hint: Optional custom formatting instructions
        
        Returns:
            Dict with summary, success, saved status
        """
        if not ticket:
            return {"success": False, "error": "No ticket provided"}
        
        # Extract formatting hints from tags
        tags = ticket.get('tags') or ""
        tag_list = [t.strip().lower() for t in tags.split(',') if t.strip()]
        
        # Build format guidance from tags
        tag_hints = []
        if 'brief' in tag_list or 'short' in tag_list:
            tag_hints.append("Keep it very brief - 2-3 sentences max.")
        if 'detailed' in tag_list or 'verbose' in tag_list:
            tag_hints.append("Provide detailed coverage of all aspects.")
        if 'technical' in tag_list or 'tech' in tag_list:
            tag_hints.append("Focus on technical implementation details.")
        if 'business' in tag_list or 'stakeholder' in tag_list:
            tag_hints.append("Frame in business/stakeholder terms, not technical.")
        if 'bullet' in tag_list or 'bullets' in tag_list:
            tag_hints.append("Use bullet points for key items.")
        if 'checklist' in tag_list:
            tag_hints.append("Format as a checklist with checkboxes.")
        
        tag_guidance = "\n".join(tag_hints) if tag_hints else ""
        custom_guidance = format_hint if format_hint else ""
        
        # Build optional sections
        tag_section = f"**Format guidance from tags:**\n{tag_guidance}\n\n" if tag_guidance else ""
        custom_section = f"**Custom formatting instructions:**\n{custom_guidance}\n\n" if custom_guidance else ""
        
        # Use Jinja2 template if available
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("summarize.jinja2")
                prompt = template.render(
                    ticket=ticket,
                    tag_section=tag_section,
                    custom_section=custom_section,
                    tags=tags,
                )
            except Exception as e:
                logger.warning(f"Template render failed, using inline prompt: {e}")
                prompt = self._build_summary_prompt(ticket, tags, tag_section, custom_section)
        else:
            prompt = self._build_summary_prompt(ticket, tags, tag_section, custom_section)
        
        try:
            # Use standard model for summarization (cost-effective)
            summary = ask(prompt)
            
            return {
                "success": True,
                "summary": summary,
                "ticket_id": ticket.get("id"),
                "tags_used": tag_list if tag_hints else [],
            }
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_summary_prompt(
        self,
        ticket: Dict[str, Any],
        tags: str,
        tag_section: str,
        custom_section: str,
    ) -> str:
        """Build the summary prompt inline."""
        return f"""Summarize this ticket for a senior data engineer.

**Ticket:** {ticket.get('ticket_id', 'N/A')} - {ticket.get('title', 'Untitled')}

**Description:**
{ticket.get('description') or 'No description provided'}

**Tags:** {tags or 'None'}

{tag_section}{custom_section}**Output format:**
- **Goal:** What needs to be done (1-2 sentences)
- **Key Details:** Technical specifics, affected systems, or data flows
- **Dependencies:** Any blockers, prerequisites, or related work
- **Complexity:** Low/Medium/High with brief rationale

Be concise and actionable. Use markdown formatting."""
    
    # =========================================================================
    # IMPLEMENTATION PLANNING
    # =========================================================================
    
    async def generate_plan(
        self,
        ticket: Dict[str, Any],
        use_premium_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate implementation plan for a ticket.
        
        Uses GPT-4o for premium quality planning.
        
        Args:
            ticket: Ticket data dict
            use_premium_model: Whether to use GPT-4o (default True)
        
        Returns:
            Dict with plan, success status
        """
        if not ticket:
            return {"success": False, "error": "No ticket provided"}
        
        # Use Jinja2 template if available
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("generate_plan.jinja2")
                prompt = template.render(ticket=ticket)
            except Exception as e:
                logger.warning(f"Template render failed, using inline prompt: {e}")
                prompt = self._build_plan_prompt(ticket)
        else:
            prompt = self._build_plan_prompt(ticket)
        
        try:
            # Use GPT-4o for implementation planning (good quality, available via OpenAI)
            model = "gpt-4o" if use_premium_model else None
            plan = ask(prompt, model=model)
            
            return {
                "success": True,
                "plan": plan,
                "ticket_id": ticket.get("id"),
                "model_used": model or "default",
            }
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_plan_prompt(self, ticket: Dict[str, Any]) -> str:
        """Build the implementation plan prompt inline."""
        ai_summary_section = f"AI Summary: {ticket['ai_summary']}" if ticket.get('ai_summary') else ""
        
        return f"""Create a sprint implementation plan for this ticket. You're helping a senior data engineer working with Airflow, Python, GitLab, and AWS.

Ticket: {ticket.get('ticket_id', 'N/A')} - {ticket.get('title', 'Untitled')}

Description:
{ticket.get('description') or 'No description provided'}

{ai_summary_section}

Create a practical implementation plan with:
1. **Approach** - High-level strategy (2-3 sentences)
2. **Steps** - Numbered list of implementation steps
3. **Files to modify** - Key files/DAGs/modules likely affected
4. **Testing** - How to validate the work
5. **Risks** - Potential issues to watch for

Be specific and actionable. Assume access to local development environment."""
    
    # =========================================================================
    # TASK DECOMPOSITION
    # =========================================================================
    
    async def decompose(
        self,
        ticket: Dict[str, Any],
        min_tasks: int = 4,
        max_tasks: int = 8,
    ) -> Dict[str, Any]:
        """
        Decompose a ticket into atomic subtasks with time estimates.
        
        Args:
            ticket: Ticket data dict
            min_tasks: Minimum number of subtasks (default 4)
            max_tasks: Maximum number of subtasks (default 8)
        
        Returns:
            Dict with tasks array, success status
        """
        if not ticket:
            return {"success": False, "error": "No ticket provided"}
        
        # Use Jinja2 template if available
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("decompose.jinja2")
                prompt = template.render(
                    ticket=ticket,
                    min_tasks=min_tasks,
                    max_tasks=max_tasks,
                )
            except Exception as e:
                logger.warning(f"Template render failed, using inline prompt: {e}")
                prompt = self._build_decompose_prompt(ticket, min_tasks, max_tasks)
        else:
            prompt = self._build_decompose_prompt(ticket, min_tasks, max_tasks)
        
        try:
            result = ask(prompt)
            
            # Parse the JSON response
            json_match = re.search(r'\[[\s\S]*\]', result)
            if json_match:
                tasks = json.loads(json_match.group())
                
                # Validate task structure
                validated_tasks = []
                for task in tasks:
                    if isinstance(task, dict) and "text" in task:
                        validated_tasks.append({
                            "text": task["text"],
                            "estimate": task.get("estimate", "1h"),
                            "status": "pending",
                        })
                
                return {
                    "success": True,
                    "tasks": validated_tasks,
                    "ticket_id": ticket.get("id"),
                    "ai_response": result,
                }
            else:
                return {
                    "success": False,
                    "error": "Could not parse task breakdown",
                    "ai_response": result,
                }
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in decomposition: {e}")
            return {"success": False, "error": "Invalid JSON in AI response"}
        except Exception as e:
            logger.error(f"Decomposition failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_decompose_prompt(
        self,
        ticket: Dict[str, Any],
        min_tasks: int,
        max_tasks: int,
    ) -> str:
        """Build the task decomposition prompt inline."""
        ai_summary_section = f"AI Summary: {ticket['ai_summary']}" if ticket.get('ai_summary') else ""
        plan_section = f"Implementation Plan: {ticket['implementation_plan']}" if ticket.get('implementation_plan') else ""
        
        return f"""Break down this ticket into specific, actionable subtasks. You're helping a senior data engineer working with Airflow, Python, GitLab, and AWS.

Ticket: {ticket.get('ticket_id', 'N/A')} - {ticket.get('title', 'Untitled')}

Description:
{ticket.get('description') or 'No description provided'}

{ai_summary_section}
{plan_section}

Generate {min_tasks}-{max_tasks} specific, atomic tasks that would complete this ticket.
Return ONLY a JSON array of objects with "text" (task description) and "estimate" (time estimate like "1h", "2h", "30m").

Example format:
[
  {{"text": "Create new DAG file for data pipeline", "estimate": "2h"}},
  {{"text": "Add unit tests for transformer function", "estimate": "1h"}}
]

Return ONLY the JSON array, no markdown or explanation."""


# =============================================================================
# ADAPTER FUNCTIONS (for backward compatibility with tickets.py routes)
# =============================================================================

async def summarize_ticket_adapter(
    ticket_pk: str,
    format_hint: str = "",
) -> Dict[str, Any]:
    """
    Adapter function for /api/tickets/{id}/generate-summary endpoint.
    
    Maintains backward compatibility with existing API.
    """
    from ..services import tickets_supabase
    
    # Fetch ticket from Supabase
    ticket = tickets_supabase.get_ticket_by_id(ticket_pk)
    
    if not ticket:
        return {"success": False, "error": "Ticket not found"}
    
    # Create agent and generate summary
    agent = TicketAgent()
    result = await agent.summarize(ticket, format_hint)
    
    # Auto-save the generated summary if successful
    if result.get("success") and result.get("summary"):
        try:
            tickets_supabase.update_ticket(ticket_pk, {
                "ai_summary": result["summary"]
            })
            result["saved"] = True
        except Exception as e:
            logger.warning(f"Failed to save summary: {e}")
            result["saved"] = False
    
    return result


async def generate_plan_adapter(ticket_pk: str) -> Dict[str, Any]:
    """
    Adapter function for /api/tickets/{id}/generate-plan endpoint.
    
    Maintains backward compatibility with existing API.
    """
    from ..services import tickets_supabase
    
    # Fetch ticket from Supabase
    ticket = tickets_supabase.get_ticket_by_id(ticket_pk)
    
    if not ticket:
        return {"success": False, "error": "Ticket not found"}
    
    # Create agent and generate plan
    agent = TicketAgent()
    result = await agent.generate_plan(ticket)
    
    return result


async def decompose_ticket_adapter(ticket_pk: str) -> Dict[str, Any]:
    """
    Adapter function for /api/tickets/{id}/generate-decomposition endpoint.
    
    Maintains backward compatibility with existing API.
    """
    from ..services import tickets_supabase
    
    # Fetch ticket from Supabase
    ticket = tickets_supabase.get_ticket_by_id(ticket_pk)
    
    if not ticket:
        return {"success": False, "error": "Ticket not found"}
    
    # Create agent and decompose
    agent = TicketAgent()
    result = await agent.decompose(ticket)
    
    return result


# Synchronous wrappers for non-async contexts
def summarize_ticket_sync(ticket_pk: str, format_hint: str = "") -> Dict[str, Any]:
    """Synchronous wrapper for summarize_ticket_adapter."""
    import asyncio
    return asyncio.run(summarize_ticket_adapter(ticket_pk, format_hint))


def generate_plan_sync(ticket_pk: str) -> Dict[str, Any]:
    """Synchronous wrapper for generate_plan_adapter."""
    import asyncio
    return asyncio.run(generate_plan_adapter(ticket_pk))


def decompose_ticket_sync(ticket_pk: str) -> Dict[str, Any]:
    """Synchronous wrapper for decompose_ticket_adapter."""
    import asyncio
    return asyncio.run(decompose_ticket_adapter(ticket_pk))


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "TicketAgent",
    "summarize_ticket_adapter",
    "generate_plan_adapter",
    "decompose_ticket_adapter",
    "summarize_ticket_sync",
    "generate_plan_sync",
    "decompose_ticket_sync",
]
