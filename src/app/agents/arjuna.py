"""
Arjuna Agent - SignalFlow Smart Assistant (Checkpoint 2.2)

The primary conversational AI agent for SignalFlow. Handles:
- Natural language intent parsing
- Ticket creation/updates
- Navigation assistance  
- Sprint management
- Accountability tracking
- Standup logging
- Focus recommendations

Extracted from api/assistant.py following the migration plan.
Maintains backward compatibility through an adapter layer.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, date
from pathlib import Path
import asyncio
import json
import logging

from jinja2 import Environment, FileSystemLoader
from ..agents.base import BaseAgent, AgentConfig

logger = logging.getLogger(__name__)


# =============================================================================
# KNOWLEDGE BASES - Moved from api/assistant.py
# =============================================================================

AVAILABLE_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
    "claude-sonnet-4",
    "claude-opus-4",
]

SYSTEM_PAGES = {
    "dashboard": {
        "path": "/",
        "title": "Dashboard",
        "description": "Overview of sprint progress, workflow modes, and quick actions"
    },
    "tickets": {
        "path": "/tickets",
        "title": "Tickets",
        "description": "Manage tasks and work items with kanban board"
    },
    "signals": {
        "path": "/signals",
        "title": "Signals",
        "description": "Review extracted insights from meetings (decisions, actions, blockers)"
    },
    "dikw": {
        "path": "/dikw",
        "title": "DIKW Pyramid",
        "description": "Knowledge hierarchy - promote signals through Data→Info→Knowledge→Wisdom"
    },
    "meetings": {
        "path": "/meetings",
        "title": "Meetings",
        "description": "View and analyze meeting summaries and extracted signals"
    },
    "documents": {
        "path": "/documents",
        "title": "Documents",
        "description": "Documentation and knowledge base"
    },
    "career": {
        "path": "/career",
        "title": "Career Hub",
        "description": "Career development tracking, feedback, and growth planning"
    },
    "accountability": {
        "path": "/accountability",
        "title": "Accountability",
        "description": "Track waiting-for items and dependencies on others"
    },
    "workflow": {
        "path": "/workflow",
        "title": "Workflow Modes",
        "description": "Navigate through 7 workflow stages from ideation to execution"
    },
    "sprint": {
        "path": "/sprint",
        "title": "Sprint Settings",
        "description": "Configure sprint parameters and goals"
    },
    "search": {
        "path": "/search",
        "title": "Search",
        "description": "Semantic search across all content"
    },
    "query": {
        "path": "/query",
        "title": "Query",
        "description": "Ask questions about your data"
    },
}

# Model name normalization map
MODEL_ALIASES = {
    "gpt4": "gpt-4o",
    "gpt-4": "gpt-4o",
    "gpt4o": "gpt-4o",
    "gpt-4o": "gpt-4o",
    "gpt4omini": "gpt-4o-mini",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt4mini": "gpt-4o-mini",
    "mini": "gpt-4o-mini",
    "gpt4turbo": "gpt-4-turbo",
    "gpt-4-turbo": "gpt-4-turbo",
    "turbo": "gpt-4-turbo",
    "gpt35": "gpt-3.5-turbo",
    "gpt-3.5": "gpt-3.5-turbo",
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "claude": "claude-3-sonnet",
    "claude3": "claude-3-sonnet",
    "claudesonnet": "claude-3-sonnet",
    "claude-3-sonnet": "claude-3-sonnet",
    "sonnet": "claude-3-sonnet",
    "claudeopus": "claude-3-opus",
    "claude-3-opus": "claude-3-opus",
    "opus": "claude-3-opus",
    "claudehaiku": "claude-3-haiku",
    "claude-3-haiku": "claude-3-haiku",
    "haiku": "claude-3-haiku",
    "claude-sonnet-4": "claude-sonnet-4",
    "sonnet4": "claude-sonnet-4",
    "claude-opus-4": "claude-opus-4",
    "opus4": "claude-opus-4",
}

# Focus query keywords
FOCUS_KEYWORDS = [
    'focus', 'should i do', 'what next', 'prioritize', 
    'work on today', 'start with'
]


# =============================================================================
# MCP COMMAND IMPORTS
# Commands and parsing moved to mcp/ modules for better separation of concerns
# =============================================================================

from ..mcp.commands import MCP_COMMANDS, MCP_INFERENCE_PATTERNS
from ..mcp.command_parser import parse_mcp_command, infer_mcp_command, get_command_help


class ArjunaAgent(BaseAgent):
    """
    Arjuna - SignalFlow's smart conversational assistant.
    
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
    
    MCP Commands:
    - /arjuna focus - Get prioritized work recommendations
    - /arjuna ticket <title> - Create a ticket
    - /arjuna update <id> --status done - Update ticket
    - /arjuna help - Show all commands
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
            # High confidence inference - execute as MCP command
            logger.info(f"Inferred MCP command: {inferred_cmd['command']}/{inferred_cmd['subcommand']} (confidence: {inferred_cmd['confidence']:.2f})")
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
    
    async def _handle_mcp_command(
        self,
        mcp_cmd: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle MCP short notation command.
        
        Args:
            mcp_cmd: Parsed MCP command with command, subcommand, args
            context: Current system context
        
        Returns:
            Response dict
        """
        command = mcp_cmd["command"]
        subcommand = mcp_cmd["subcommand"]
        args = mcp_cmd.get("args", {})
        intent = mcp_cmd.get("intent")
        
        # Handle help command
        if subcommand == "help":
            help_arg = args.get("command") or args.get("extra", [None])[0] if args.get("extra") else None
            help_text = get_command_help(command if help_arg is None else help_arg, help_arg)
            return {
                "response": help_text,
                "success": True,
                "action": "show_help",
                "command_mode": True,
            }
        
        # Route Arjuna commands to intent system
        if command == "arjuna" and intent:
            intent_data = {
                "intent": intent,
                "entities": args,
                "confidence": 1.0,
                "clarifications": [],
                "response_text": f"Executing /{command} {subcommand}...",
            }
            
            # Execute the intent
            execution_result = await self._execute_intent(intent_data)
            
            if not execution_result.get("success"):
                return {
                    "response": f"❌ Command failed: {execution_result.get('error')}",
                    "success": False,
                    "command_mode": True,
                }
            
            # Build response with command acknowledgment
            response_text = f"✅ `/{command} {subcommand}` executed"
            response_text = self._enhance_response(response_text, execution_result)
            
            return {
                "response": response_text,
                "success": True,
                "action": execution_result.get("action"),
                "result": execution_result,
                "command_mode": True,
                "suggested_page": execution_result.get("navigate_to"),
            }
        
        # Route chain commands (multi-step task automation)
        if command == "chain":
            return await self._execute_chain_command(subcommand, args, context)
        
        # Route other agent commands (delegate to subcommand router)
        if command in ["query", "semantic", "agent", "career", "meeting", "dikw"]:
            return await self._route_agent_command(command, subcommand, args, context)
        
        # Unknown command handling
        return {
            "response": f"Unknown command: /{command} {subcommand}\n\nType `/help` for available commands.",
            "success": False,
            "command_mode": True,
        }
    
    async def _route_agent_command(
        self,
        command: str,
        subcommand: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Route command to appropriate agent via subcommand router.
        
        This delegates to the MCP subcommand router for inter-agent communication.
        """
        try:
            from ..mcp.subcommand_router import get_subcommand_router
            
            router = get_subcommand_router()
            
            # Map our commands to router tool names
            tool_map = {
                "query": "query_data",
                "semantic": "semantic_search",
                "agent": "query_agent",
            }
            
            tool_name = tool_map.get(command, command)
            
            # Check if tool is registered
            if tool_name not in router.list_tools():
                # Agent-specific commands handled by respective agents
                return {
                    "response": f"Command `/{command} {subcommand}` will be handled by the {command} agent.\n\n_Agent routing coming in Phase 2.3+_",
                    "success": True,
                    "action": "agent_route",
                    "command_mode": True,
                    "pending_agent": command,
                }
            
            # Route to subcommand handler
            result = router.route(tool_name, subcommand, args)
            
            return {
                "response": f"✅ `/{command} {subcommand}` completed\n\n{json.dumps(result, indent=2)}",
                "success": True,
                "action": f"{command}_{subcommand}",
                "result": result,
                "command_mode": True,
            }
        
        except ValueError as e:
            return {
                "response": f"❌ Command error: {e}",
                "success": False,
                "command_mode": True,
            }
        except Exception as e:
            logger.error(f"Error routing command /{command} {subcommand}: {e}")
            return {
                "response": f"❌ Error: {e}",
                "success": False,
                "command_mode": True,
            }
    
    async def _execute_chain_command(
        self,
        chain_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a multi-step chain command.
        
        Chain commands orchestrate multiple agent actions in sequence,
        passing results from one step to the next.
        
        Args:
            chain_name: Name of the chain (e.g., 'ticket-sprint', 'standup-feedback')
            args: Arguments for the chain
            context: Current system context
        
        Returns:
            Response dict with aggregated results
        """
        # Get chain definition from MCP_COMMANDS
        chain_config = MCP_COMMANDS.get("chain", {}).get("subcommands", {}).get(chain_name)
        
        if not chain_config:
            return {
                "response": f"❌ Unknown chain: `{chain_name}`\n\nAvailable chains:\n• ticket-sprint\n• standup-feedback\n• ticket-plan-decompose\n• focus-execute\n• blocked-escalate",
                "success": False,
                "command_mode": True,
            }
        
        steps = chain_config.get("steps", [])
        if not steps:
            return {
                "response": f"❌ Chain `{chain_name}` has no steps defined",
                "success": False,
                "command_mode": True,
            }
        
        # Execute chain steps
        results = []
        step_outputs = {}
        
        logger.info(f"Executing chain: {chain_name} with {len(steps)} steps")
        
        for i, step in enumerate(steps, 1):
            logger.info(f"Chain step {i}/{len(steps)}: {step}")
            
            try:
                step_result = await self._execute_chain_step(
                    step, args, context, step_outputs
                )
                
                if not step_result.get("success"):
                    # Chain step failed - report partial progress
                    error_msg = step_result.get("error", "Unknown error")
                    return {
                        "response": f"⚠️ Chain `{chain_name}` failed at step {i}/{len(steps)}: **{step}**\n\n❌ Error: {error_msg}\n\n**Completed steps:**\n" + "\n".join(
                            f"✅ {r['step']}" for r in results
                        ),
                        "success": False,
                        "partial_results": results,
                        "failed_step": step,
                        "command_mode": True,
                    }
                
                results.append({
                    "step": step,
                    "result": step_result,
                })
                step_outputs[step] = step_result
                
            except Exception as e:
                logger.error(f"Chain step {step} exception: {e}")
                return {
                    "response": f"⚠️ Chain `{chain_name}` exception at step {i}: **{step}**\n\n❌ {str(e)}",
                    "success": False,
                    "partial_results": results,
                    "command_mode": True,
                }
        
        # All steps completed successfully
        response_lines = [f"✅ Chain `{chain_name}` completed ({len(steps)} steps)\n"]
        
        for r in results:
            step_summary = r["result"].get("summary", r["result"].get("action", r["step"]))
            response_lines.append(f"  ✓ **{r['step']}**: {step_summary}")
        
        # Add final result if available
        final_result = results[-1]["result"] if results else {}
        if final_result.get("navigate_to"):
            response_lines.append(f"\n📍 Navigate to: [{final_result['navigate_to']}]({final_result['navigate_to']})")
        
        return {
            "response": "\n".join(response_lines),
            "success": True,
            "action": f"chain_{chain_name}",
            "chain_results": results,
            "command_mode": True,
            "suggested_page": final_result.get("navigate_to"),
        }
    
    async def _execute_chain_step(
        self,
        step: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
        previous_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a single step in a chain command.
        
        Maps step names to actual agent actions.
        """
        # Map step names to intent handlers
        step_handlers = {
            # Ticket operations
            "create_ticket": lambda: self._execute_intent({
                "intent": "create_ticket",
                "entities": {
                    "title": args.get("title", args.get("extra", ["New ticket"])[0] if args.get("extra") else "New ticket"),
                    "priority": args.get("priority", "medium"),
                    "description": args.get("description", ""),
                },
            }),
            "add_to_sprint": lambda: self._add_ticket_to_sprint(
                previous_outputs.get("create_ticket", {}).get("ticket_id")
            ),
            "generate_plan": lambda: self._generate_ticket_plan(
                previous_outputs.get("create_ticket", {}).get("ticket_id")
            ),
            "decompose_tasks": lambda: self._decompose_ticket(
                previous_outputs.get("create_ticket", {}).get("ticket_id")
            ),
            "update_ticket_status": lambda: self._execute_intent({
                "intent": "update_ticket",
                "entities": {
                    "ticket_id": args.get("ticket_id") or (
                        previous_outputs.get("get_focus_recommendations", {}).get("top_ticket_id")
                    ),
                    "status": "in_progress",
                },
            }),
            "update_ticket_blocked": lambda: self._execute_intent({
                "intent": "update_ticket",
                "entities": {
                    "ticket_id": args.get("ticket_id"),
                    "status": "blocked",
                },
            }),
            
            # Standup operations
            "create_standup": lambda: self._execute_intent({
                "intent": "create_standup",
                "entities": {
                    "yesterday": args.get("yesterday", ""),
                    "today_plan": args.get("today_plan", args.get("today", "")),
                    "blockers": args.get("blockers", ""),
                },
            }),
            "analyze_standup": lambda: self._analyze_standup_step(
                previous_outputs.get("create_standup", {})
            ),
            "suggest_improvements": lambda: {
                "success": True,
                "summary": "Suggestions provided in feedback",
                "action": "suggest_improvements",
            },
            
            # Meeting operations
            "analyze_meeting": lambda: self._analyze_meeting_step(args.get("notes", "")),
            "extract_signals": lambda: {
                "success": True,
                "summary": f"Extracted {previous_outputs.get('analyze_meeting', {}).get('signal_count', 0)} signals",
                "action": "extract_signals",
            },
            "promote_signals": lambda: self._promote_signals_step(
                previous_outputs.get("analyze_meeting", {}).get("signal_ids", [])
            ),
            
            # Focus operations
            "get_focus_recommendations": lambda: self._get_focus_step(),
            
            # Accountability operations
            "create_accountability": lambda: self._execute_intent({
                "intent": "create_accountability",
                "entities": {
                    "description": args.get("reason", args.get("description", "")),
                    "responsible_party": args.get("responsible_party", args.get("from", "")),
                },
            }),
        }
        
        handler = step_handlers.get(step)
        
        if not handler:
            return {
                "success": False,
                "error": f"Unknown step: {step}",
            }
        
        result = await handler() if asyncio.iscoroutinefunction(handler) else handler()
        return result
    
    async def _add_ticket_to_sprint(self, ticket_id: Optional[int]) -> Dict[str, Any]:
        """Add a ticket to the current sprint."""
        if not ticket_id:
            return {"success": False, "error": "No ticket ID provided"}
        
        try:
            with connect() as conn:
                # Get current sprint
                sprint = conn.execute(
                    "SELECT id, name FROM sprints WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                
                if not sprint:
                    return {"success": False, "error": "No active sprint found"}
                
                # Add ticket to sprint
                conn.execute(
                    "UPDATE tickets SET sprint_id = ?, updated_at = datetime('now') WHERE id = ?",
                    (sprint["id"], ticket_id)
                )
            
            return {
                "success": True,
                "summary": f"Added to sprint '{sprint['name']}'",
                "action": "add_to_sprint",
                "sprint_id": sprint["id"],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _generate_ticket_plan(self, ticket_id: Optional[int]) -> Dict[str, Any]:
        """Generate implementation plan for a ticket."""
        if not ticket_id:
            return {"success": False, "error": "No ticket ID provided"}
        
        try:
            # Use the ticket plan endpoint logic
            with connect() as conn:
                ticket = conn.execute(
                    "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
                ).fetchone()
            
            if not ticket:
                return {"success": False, "error": "Ticket not found"}
            
            return {
                "success": True,
                "summary": "Plan generation queued",
                "action": "generate_plan",
                "navigate_to": f"/tickets/{ticket_id}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _decompose_ticket(self, ticket_id: Optional[int]) -> Dict[str, Any]:
        """Decompose ticket into subtasks."""
        if not ticket_id:
            return {"success": False, "error": "No ticket ID provided"}
        
        return {
            "success": True,
            "summary": "Decomposition queued",
            "action": "decompose_tasks",
            "navigate_to": f"/tickets/{ticket_id}",
        }
    
    async def _analyze_standup_step(self, standup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a standup for coaching feedback."""
        try:
            from .career_coach import analyze_standup_adapter
            
            standup_text = standup_data.get("standup_text", "")
            if not standup_text:
                return {"success": True, "summary": "No standup to analyze", "action": "analyze_standup"}
            
            result = await analyze_standup_adapter(standup_text)
            return {
                "success": True,
                "summary": result.get("feedback", "Feedback generated")[:100],
                "action": "analyze_standup",
                "feedback": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _analyze_meeting_step(self, notes: str) -> Dict[str, Any]:
        """Analyze meeting notes and extract signals."""
        if not notes:
            return {"success": False, "error": "No meeting notes provided"}
        
        try:
            from .meeting_analyzer import MeetingAnalyzerAgent
            
            analyzer = MeetingAnalyzerAgent()
            result = await analyzer.analyze(notes)
            
            return {
                "success": True,
                "summary": f"Extracted {len(result.get('signals', []))} signals",
                "action": "analyze_meeting",
                "signal_count": len(result.get("signals", [])),
                "signal_ids": [s.get("id") for s in result.get("signals", []) if s.get("id")],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _promote_signals_step(self, signal_ids: List[int]) -> Dict[str, Any]:
        """Promote extracted signals to higher DIKW levels."""
        if not signal_ids:
            return {"success": True, "summary": "No signals to promote", "action": "promote_signals"}
        
        return {
            "success": True,
            "summary": f"Queued {len(signal_ids)} signals for promotion",
            "action": "promote_signals",
            "navigate_to": "/dikw",
        }
    
    async def _get_focus_step(self) -> Dict[str, Any]:
        """Get focus recommendations and extract top priority."""
        focus_data = self._get_focus_recommendations()
        recs = focus_data.get("recommendations", [])
        
        top_ticket_id = None
        if recs:
            for r in recs:
                if r.get("type") in ["blocker", "active", "todo"] and r.get("id"):
                    top_ticket_id = r["id"]
                    break
        
        return {
            "success": True,
            "summary": f"Found {len(recs)} items to focus on",
            "action": "get_focus_recommendations",
            "top_ticket_id": top_ticket_id,
            "recommendations": recs[:3],
        }

    def _is_focus_query(self, message: str) -> bool:
        """Check if the message is asking for focus recommendations."""
        message_lower = message.lower()
        return any(kw in message_lower for kw in FOCUS_KEYWORDS)
    
    async def _handle_focus_query(self) -> Dict[str, Any]:
        """Handle focus/prioritization queries with smart recommendations."""
        focus_data = self._get_focus_recommendations()
        recs = focus_data.get("recommendations", [])
        
        if recs:
            # Render using template if available
            if self.jinja_env:
                try:
                    template = self.jinja_env.get_template("focus.jinja2")
                    response_text = template.render(
                        recommendations=recs[:5],
                        total_count=focus_data.get("total_count", len(recs)),
                    )
                except Exception:
                    response_text = self._format_focus_response(recs, focus_data)
            else:
                response_text = self._format_focus_response(recs, focus_data)
            
            return {
                "response": response_text,
                "success": True,
                "action": "focus_recommendations",
                "focus_data": focus_data,
                "suggested_page": "/tickets" if any(
                    r["type"] in ["blocker", "active", "todo"] for r in recs
                ) else None,
            }
        else:
            return {
                "response": (
                    "Hare Krishna! 🙏 You're all caught up! No urgent items need attention right now.\n\n"
                    "Consider:\n"
                    "• Reviewing signals to build your knowledge base\n"
                    "• Planning ahead for upcoming work\n"
                    "• Taking a well-deserved break!"
                ),
                "success": True,
                "action": "focus_recommendations",
                "suggested_page": None,
            }
    
    def _format_focus_response(self, recs: List[Dict], focus_data: Dict) -> str:
        """Format focus recommendations as text."""
        parts = ["Hare Krishna! 🙏 Here's what I recommend you focus on:\n"]
        
        for i, rec in enumerate(recs[:5], 1):
            parts.append(f"**{i}. {rec['title']}**")
            parts.append(f"   {rec['text']}")
            parts.append(f"   _Why:_ {rec['reason']}\n")
        
        total = focus_data.get("total_count", len(recs))
        if total > 5:
            parts.append(f"\n_Plus {total - 5} more items to consider..._")
        
        return "\n".join(parts)
    
    async def _parse_intent(
        self,
        message: str,
        context: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Use LLM to understand user intent and extract structured data."""
        # Build system prompt with context
        system_prompt = self._build_intent_prompt(context, history)
        
        # Call LLM for intent parsing
        response = await self.ask_llm(
            prompt=f'USER MESSAGE: "{message}"\n\nAnalyze the user\'s intent and respond with JSON.',
            task_type="classification",
            context={"message": message, "history": history},
        )
        
        # Parse JSON response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            return json.loads(response)
        except Exception:
            # Fallback if JSON parsing fails
            return {
                "intent": "ask_question",
                "confidence": 0.5,
                "entities": {},
                "clarifications": [],
                "response_text": response,
            }
    
    def _build_intent_prompt(
        self,
        context: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> str:
        """Build the system prompt for intent parsing."""
        # Format conversation history
        history_text = ""
        if history:
            history_text = "\n\nRecent conversation:\n"
            for msg in history[-6:]:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_text += f"{role}: {msg.get('content', '')[:200]}\n"
        
        return f"""{self.get_system_prompt()}

CURRENT SYSTEM STATE:
Current AI Model: {context.get('current_ai_model', 'gpt-4o-mini')}
Available Models: {', '.join(context.get('available_models', AVAILABLE_MODELS))}

Sprint: {json.dumps(context.get('sprint', {}), indent=2) if context.get('sprint') else 'No sprint configured'}

Ticket Summary: {json.dumps(context.get('ticket_stats', {}), indent=2)}

Recent Tickets:
{json.dumps(context.get('recent_tickets', [])[:5], indent=2)}

Waiting For Items:
{json.dumps(context.get('waiting_for', []), indent=2)}

Today's Standups:
{json.dumps(context.get('todays_standups', []), indent=2)}
{history_text}

Analyze the user's intent and respond with JSON as specified."""
    
    async def _execute_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the parsed intent using the database connection."""
        intent = intent_data.get("intent")
        entities = intent_data.get("entities", {})
        
        # Get database connection
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "error": "Database connection not available"}
        
        try:
            if intent == "focus_recommendations":
                return {
                    "success": True,
                    "action": "focus_recommendations",
                    "focus_data": intent_data.get("focus_data", {}),
                }
            
            elif intent == "create_ticket":
                return self._create_ticket(conn, entities)
            
            elif intent == "update_ticket":
                return self._update_ticket(conn, entities)
            
            elif intent == "list_tickets":
                return self._list_tickets(conn, entities)
            
            elif intent == "create_accountability":
                return self._create_accountability(conn, entities)
            
            elif intent == "create_standup":
                return self._create_standup(conn, entities, intent_data)
            
            elif intent == "navigate":
                return self._handle_navigation(entities)
            
            elif intent == "change_model":
                return self._change_model(conn, entities)
            
            elif intent == "update_sprint":
                return self._update_sprint(conn, entities)
            
            elif intent == "reset_workflow":
                return self._reset_workflow(conn)
            
            elif intent == "search_meetings":
                return self._search_meetings(conn, entities)
            
            elif intent in ("ask_question", "greeting", "needs_clarification"):
                return {"success": True, "action": intent}
            
            return {"success": True, "intent": intent}
        
        except Exception as e:
            logger.error(f"Intent execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_db_connection(self):
        """Get database connection, with fallback to app.db module."""
        if self.db_connection:
            return self.db_connection
        
        try:
            from ..db import connect
            return connect()
        except ImportError:
            logger.error("Could not import database connection")
            return None
    
    def _create_ticket(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new ticket."""
        ticket_id = f"AJ-{datetime.now().strftime('%y%m%d-%H%M')}"
        conn.execute(
            """
            INSERT INTO tickets (ticket_id, title, description, status, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                entities.get("title", "Untitled Task"),
                entities.get("description", ""),
                entities.get("status", "backlog"),
                entities.get("priority", "medium"),
            ),
        )
        return {"success": True, "ticket_id": ticket_id, "action": "create_ticket"}
    
    def _update_ticket(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing ticket."""
        ticket_id = entities.get("ticket_id")
        if not ticket_id:
            return {"success": False, "error": "No ticket ID provided"}
        
        updates = []
        params = []
        
        if "status" in entities:
            updates.append("status = ?")
            params.append(entities["status"])
        if "priority" in entities:
            updates.append("priority = ?")
            params.append(entities["priority"])
        
        if updates:
            params.append(ticket_id)
            conn.execute(
                f"UPDATE tickets SET {', '.join(updates)} WHERE ticket_id = ?",
                params,
            )
        
        return {"success": True, "action": "update_ticket"}
    
    def _list_tickets(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """List tickets with optional status filter."""
        status_filter = entities.get("status")
        
        if status_filter:
            tickets = conn.execute(
                """SELECT ticket_id, title, status, priority FROM tickets 
                   WHERE status = ? ORDER BY created_at DESC LIMIT 10""",
                (status_filter,),
            ).fetchall()
        else:
            tickets = conn.execute(
                """SELECT ticket_id, title, status, priority FROM tickets 
                   ORDER BY created_at DESC LIMIT 10"""
            ).fetchall()
        
        return {
            "success": True,
            "tickets": [dict(t) for t in tickets],
            "action": "list_tickets",
        }
    
    def _create_accountability(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new accountability item."""
        conn.execute(
            """
            INSERT INTO accountability_items (description, responsible_party, context, source_type)
            VALUES (?, ?, ?, 'assistant')
            """,
            (
                entities.get("description", ""),
                entities.get("responsible_party", "Unknown"),
                entities.get("context", ""),
            ),
        )
        return {"success": True, "action": "create_accountability"}
    
    def _create_standup(
        self,
        conn,
        entities: Dict[str, Any],
        intent_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a standup entry."""
        standup_date = date.today().isoformat()
        
        content_parts = []
        if entities.get("yesterday"):
            content_parts.append(f"Yesterday: {entities['yesterday']}")
        if entities.get("today_plan"):
            content_parts.append(f"Today: {entities['today_plan']}")
        if entities.get("blockers"):
            content_parts.append(f"Blockers: {entities['blockers']}")
        
        content = "\n".join(content_parts) or intent_data.get("response_text") or "Standup update"
        
        cur = conn.execute(
            """
            INSERT INTO standup_updates (standup_date, content, feedback, sentiment, key_themes)
            VALUES (?, ?, NULL, 'neutral', '')
            """,
            (standup_date, content),
        )
        
        return {
            "success": True,
            "action": "create_standup",
            "standup_id": cur.lastrowid,
        }
    
    def _handle_navigation(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Handle navigation requests."""
        target = entities.get("target_page")
        if target and target in SYSTEM_PAGES:
            return {
                "success": True,
                "action": "navigate",
                "navigate_to": SYSTEM_PAGES[target]["path"],
            }
        return {"success": True, "action": "navigate"}
    
    def _change_model(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Change the AI model setting."""
        model = entities.get("model", "").lower().strip()
        normalized = MODEL_ALIASES.get(model.replace(" ", "").replace("-", ""), model)
        
        if normalized not in AVAILABLE_MODELS:
            return {
                "success": False,
                "error": f"Unknown model: {model}. Available: {', '.join(AVAILABLE_MODELS)}",
            }
        
        conn.execute(
            """
            INSERT INTO settings (key, value) 
            VALUES ('ai_model', ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')
            """,
            (normalized, normalized),
        )
        
        return {"success": True, "action": "change_model", "model": normalized}
    
    def _update_sprint(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Update sprint settings."""
        sprint_name = entities.get("sprint_name")
        sprint_goal = entities.get("sprint_goal")
        
        if not sprint_name and not sprint_goal:
            return {"success": False, "error": "No sprint name or goal provided"}
        
        updates = []
        params = []
        
        if sprint_name:
            updates.append("sprint_name = ?")
            params.append(sprint_name)
        if sprint_goal:
            updates.append("sprint_goal = ?")
            params.append(sprint_goal)
        
        if updates:
            params.append(1)  # id = 1
            conn.execute(
                f"UPDATE sprint_settings SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        
        return {
            "success": True,
            "action": "update_sprint",
            "sprint_name": sprint_name,
            "sprint_goal": sprint_goal,
        }
    
    def _reset_workflow(self, conn) -> Dict[str, Any]:
        """Reset all workflow progress."""
        modes = ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g']
        for mode in modes:
            conn.execute(
                "DELETE FROM settings WHERE key = ?",
                (f"workflow_progress_{mode}",),
            )
        return {"success": True, "action": "reset_workflow"}
    
    def _search_meetings(self, conn, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Search meeting summaries."""
        query = entities.get("query", "")
        meetings = conn.execute(
            """
            SELECT meeting_name, meeting_date, signals_json
            FROM meeting_summaries
            WHERE meeting_name LIKE ? OR raw_text LIKE ? OR signals_json LIKE ?
            ORDER BY meeting_date DESC
            LIMIT 5
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
        
        return {
            "success": True,
            "action": "search_meetings",
            "meetings": [dict(m) for m in meetings],
        }
    
    def _get_system_context(self) -> Dict[str, Any]:
        """Get current system state for context."""
        conn = self._get_db_connection()
        if not conn:
            return {}
        
        try:
            # Get sprint info
            sprint = conn.execute(
                "SELECT * FROM sprint_settings WHERE id = 1"
            ).fetchone()
            
            # Get current AI model
            model_row = conn.execute(
                "SELECT value FROM settings WHERE key = 'ai_model'"
            ).fetchone()
            current_model = model_row["value"] if model_row else "gpt-4o-mini"
            
            # Get ticket counts by status
            ticket_stats = conn.execute(
                """
                SELECT status, COUNT(*) as count 
                FROM tickets 
                GROUP BY status
                """
            ).fetchall()
            
            # Get recent tickets
            tickets = conn.execute(
                """
                SELECT ticket_id, title, status, priority 
                FROM tickets 
                ORDER BY created_at DESC 
                LIMIT 10
                """
            ).fetchall()
            
            return {
                "sprint": dict(sprint) if sprint else None,
                "current_ai_model": current_model,
                "available_models": AVAILABLE_MODELS,
                "ticket_stats": {row["status"]: row["count"] for row in ticket_stats},
                "recent_tickets": [dict(t) for t in tickets],
                "available_pages": SYSTEM_PAGES,
            }
        except Exception as e:
            logger.error(f"Failed to get system context: {e}")
            return {}
    
    def _get_focus_recommendations(self) -> Dict[str, Any]:
        """Get prioritized work recommendations."""
        conn = self._get_db_connection()
        if not conn:
            return {"recommendations": [], "total_count": 0}
        
        recommendations = []
        
        try:
            # 1. BLOCKERS (Highest priority)
            blockers = conn.execute(
                """SELECT ticket_id, title FROM tickets 
                   WHERE status = 'blocked' 
                   ORDER BY created_at ASC LIMIT 2"""
            ).fetchall()
            for b in blockers:
                recommendations.append({
                    "priority": 1,
                    "type": "blocker",
                    "title": f"🚫 Blocked: {b['ticket_id']}",
                    "text": b["title"],
                    "reason": "Blocked work stops everything downstream",
                    "action": "Identify who can unblock this and reach out",
                })
            
            # 2. IN-PROGRESS WORK
            in_progress = conn.execute(
                """SELECT ticket_id, title FROM tickets 
                   WHERE status = 'in_progress' 
                   ORDER BY updated_at DESC LIMIT 2"""
            ).fetchall()
            for t in in_progress:
                recommendations.append({
                    "priority": 2,
                    "type": "active",
                    "title": f"🔄 Continue: {t['ticket_id']}",
                    "text": t["title"],
                    "reason": "Finishing started work is more efficient than context-switching",
                    "action": "Continue where you left off",
                })
            
            # 3. SPRINT DEADLINE APPROACHING
            sprint = conn.execute(
                "SELECT * FROM sprint_settings WHERE id = 1"
            ).fetchone()
            if sprint and sprint["end_date"]:
                try:
                    end_date = datetime.strptime(sprint["end_date"], "%Y-%m-%d").date()
                    days_left = (end_date - date.today()).days
                    
                    if 0 <= days_left <= 3:
                        todo_count = conn.execute(
                            "SELECT COUNT(*) as c FROM tickets WHERE status IN ('todo', 'in_progress')"
                        ).fetchone()["c"]
                        
                        if todo_count > 0:
                            recommendations.append({
                                "priority": 2,
                                "type": "deadline",
                                "title": f"⏰ Sprint ends in {days_left} days!",
                                "text": f"{todo_count} items still in todo",
                                "reason": "Time is running out - consider scope reduction",
                                "action": "Review remaining work and prioritize ruthlessly",
                            })
                except Exception:
                    pass
            
            # 4. STALE WORK
            stale = conn.execute(
                """SELECT ticket_id, title, updated_at FROM tickets 
                   WHERE status = 'in_progress' 
                   AND date(updated_at) < date('now', '-2 days')
                   ORDER BY updated_at ASC LIMIT 1"""
            ).fetchall()
            for t in stale:
                recommendations.append({
                    "priority": 3,
                    "type": "stale",
                    "title": f"⏳ Stale: {t['ticket_id']}",
                    "text": t["title"],
                    "reason": "This has been in progress for days - is it blocked?",
                    "action": "Either complete it or mark it blocked",
                })
            
            # 5. WAITING-FOR ITEMS
            waiting = conn.execute(
                """SELECT description, responsible_party FROM accountability_items
                   WHERE status = 'waiting'
                   ORDER BY created_at ASC LIMIT 2"""
            ).fetchall()
            for w in waiting:
                recommendations.append({
                    "priority": 4,
                    "type": "waiting",
                    "title": f"⏳ Follow up: {w['responsible_party']}",
                    "text": w["description"][:60],
                    "reason": "Dependencies on others can become blockers",
                    "action": f"Check in with {w['responsible_party']}",
                })
            
            # 6. HIGH PRIORITY TODO
            if len(recommendations) < 3:
                high_priority = conn.execute(
                    """SELECT ticket_id, title FROM tickets 
                       WHERE status = 'todo' AND priority = 'high'
                       ORDER BY created_at ASC LIMIT 2"""
                ).fetchall()
                for t in high_priority:
                    recommendations.append({
                        "priority": 6,
                        "type": "todo",
                        "title": f"⭐ High Priority: {t['ticket_id']}",
                        "text": t["title"],
                        "reason": "High priority work should be started soon",
                        "action": "Start working on this ticket",
                    })
        
        except Exception as e:
            logger.error(f"Failed to get focus recommendations: {e}")
        
        recommendations.sort(key=lambda r: r["priority"])
        
        return {
            "recommendations": recommendations[:5],
            "total_count": len(recommendations),
        }
    
    def _get_follow_up_suggestions(
        self,
        action: Optional[str],
        intent: Optional[str],
        result: Dict[str, Any],
    ) -> List[str]:
        """Generate contextual follow-up suggestions."""
        suggestions = []
        
        if action == "create_ticket":
            suggestions = [
                "What's the priority?",
                "Add a description",
                "Show my tickets",
            ]
        elif action == "update_ticket":
            suggestions = [
                "Show my tickets",
                "What should I work on next?",
                "Create another ticket",
            ]
        elif action == "create_accountability":
            suggestions = [
                "Show waiting-for items",
                "Create a ticket from this",
            ]
        elif action == "create_standup":
            suggestions = [
                "What should I focus on?",
                "Show my tickets",
            ]
        elif action == "navigate":
            suggestions = [
                "Help me understand this page",
                "What can I do here?",
            ]
        elif action == "change_model":
            suggestions = [
                "What models are available?",
                "Tell me about this model",
            ]
        elif action == "focus_recommendations":
            suggestions = [
                "Start working on the first one",
                "Show me more details",
            ]
        elif intent == "greeting":
            suggestions = [
                "What can you help me with?",
                "What should I focus on?",
                "Show me my tickets",
            ]
        else:
            suggestions = [
                "What should I focus on?",
                "Create a ticket",
                "Show my progress",
            ]
        
        return suggestions
    
    async def _search_user_mentions_in_transcripts(self, user_name: str) -> str:
        """
        F2b: Search raw transcripts for user mentions using both keyword and semantic search.
        
        Searches:
        1. raw_text in meeting_summaries
        2. content in meeting_documents (Teams/Pocket transcripts)
        
        Handles transcript formats like "Rowan Neri 11:59 AM" by searching for:
        - First name only (e.g., "Rowan")
        - Full name if provided (e.g., "Rowan Neri")
        
        Returns context with snippets around user mentions.
        """
        context_parts = []
        
        # Build search patterns - handle "FirstName" or "FirstName LastName" formats
        # USER_NAME might be "Rowan" or "Rowan Neri"
        search_names = [user_name]
        name_parts = user_name.split()
        if len(name_parts) > 1:
            # If full name given, also search for first name alone
            search_names.append(name_parts[0])
        
        try:
            from ..db import connect
            
            with connect() as conn:
                seen_meeting_ids = set()
                
                for search_name in search_names:
                    # Search meeting_summaries.raw_text for user mentions
                    meetings_raw = conn.execute(
                        """SELECT ms.id, ms.meeting_name, ms.raw_text, ms.meeting_date
                           FROM meeting_summaries ms
                           WHERE LOWER(ms.raw_text) LIKE ?
                           ORDER BY COALESCE(ms.meeting_date, ms.created_at) DESC
                           LIMIT 10""",
                        (f"%{search_name.lower()}%",)
                    ).fetchall()
                    
                    for m in meetings_raw:
                        if m["id"] in seen_meeting_ids:
                            continue
                        seen_meeting_ids.add(m["id"])
                        
                        if m["raw_text"]:
                            # Search for any of the name variations in the snippet
                            snippet = self._extract_mention_snippet(m["raw_text"], search_name)
                            if snippet:
                                date_str = m["meeting_date"] or "Unknown date"
                                context_parts.append(f"**{m['meeting_name']}** ({date_str}):\n{snippet}")
                
                seen_doc_ids = set()
                
                for search_name in search_names:
                    # Search meeting_documents.content for user mentions
                    docs = conn.execute(
                        """SELECT md.id, md.content, md.source, md.doc_type, ms.meeting_name, ms.meeting_date
                           FROM meeting_documents md
                           JOIN meeting_summaries ms ON md.meeting_id = ms.id
                           WHERE LOWER(md.content) LIKE ?
                           ORDER BY COALESCE(ms.meeting_date, md.created_at) DESC
                           LIMIT 10""",
                        (f"%{search_name.lower()}%",)
                    ).fetchall()
                    
                    for d in docs:
                        if d["id"] in seen_doc_ids:
                            continue
                        seen_doc_ids.add(d["id"])
                        
                        if d["content"]:
                            snippet = self._extract_mention_snippet(d["content"], search_name)
                            if snippet:
                                date_str = d["meeting_date"] or "Unknown date"
                                source = d["source"] or d["doc_type"] or "Transcript"
                                context_parts.append(f"**{d['meeting_name']}** - {source} ({date_str}):\n{snippet}")
                
        except Exception as e:
            logger.error(f"Failed to search transcripts for user mentions: {e}")
        
        if not context_parts:
            return f"No mentions of {user_name} found in recent meeting transcripts."
        
        return "\n\n---\n\n".join(context_parts[:10])  # Limit to 10 snippets
    
    def _extract_mention_snippet(self, text: str, user_name: str, context_chars: int = 200) -> str:
        """
        Extract snippet around user mention with surrounding context.
        
        Returns multiple snippets if user is mentioned multiple times.
        """
        if not text or not user_name:
            return ""
        
        lower_text = text.lower()
        lower_name = user_name.lower()
        snippets = []
        
        start_pos = 0
        while True:
            match_pos = lower_text.find(lower_name, start_pos)
            if match_pos == -1:
                break
            
            # Get context around match
            snippet_start = max(0, match_pos - context_chars)
            snippet_end = min(len(text), match_pos + len(user_name) + context_chars)
            
            snippet = text[snippet_start:snippet_end].strip()
            
            # Add ellipsis if truncated
            if snippet_start > 0:
                snippet = "..." + snippet
            if snippet_end < len(text):
                snippet = snippet + "..."
            
            snippets.append(snippet)
            start_pos = match_pos + len(user_name)
            
            # Limit to 3 snippets per document
            if len(snippets) >= 3:
                break
        
        return "\n".join(snippets)
    
    async def _get_recent_meetings_context(self) -> str:
        """Get context from recent meetings for quick_ask."""
        try:
            from ..db import connect
            with connect() as conn:
                recent = conn.execute(
                    """SELECT meeting_name, synthesized_notes, signals_json 
                       FROM meeting_summaries 
                       ORDER BY COALESCE(meeting_date, created_at) DESC 
                       LIMIT 5"""
                ).fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch meeting context: {e}")
            return ""
        
        context_parts = []
        for m in recent:
            context_parts.append(f"Meeting: {m['meeting_name']}\n{m['synthesized_notes'][:1000]}")
            if m["signals_json"]:
                try:
                    signals = json.loads(m["signals_json"])
                    for stype in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                        items = signals.get(stype, [])
                        if items:
                            context_parts.append(f"{stype}: {', '.join(items[:3])}")
                except Exception:
                    pass
        
        return "\n\n".join(context_parts)
    
    async def quick_ask(
        self,
        topic: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle quick AI questions from the dashboard.
        
        Args:
            topic: Predefined topic (blockers, decisions, action_items, etc.)
            query: Custom query string
        
        Returns:
            Dict with response and success status
        """
        # Topic prompts for common dashboard questions
        # F2b: Get user name from environment
        import os
        user_name = os.getenv("USER_NAME", "Rowan")
        
        topic_prompts = {
            "blockers": "What are the current blockers or obstacles mentioned in recent meetings?",
            "decisions": "What key decisions were made in recent meetings?",
            "action_items": "What are the outstanding action items from recent meetings?",
            "ideas": "What new ideas or suggestions came up in recent meetings?",
            "risks": "What risks were identified in recent meetings?",
            "this_week": "Summarize what happened this week based on recent meetings and documents.",
            "rowan_mentions": f"What mentions of {user_name} or items assigned to {user_name} are there in recent meetings?",
            "reach_outs": "Who needs to be contacted or reached out to based on recent meetings? What follow-ups are needed?",
            "announcements": "What team-wide announcements or important updates were shared in recent meetings?",
        }
        
        # Build the question
        if topic:
            question = topic_prompts.get(topic, f"Tell me about {topic} from recent meetings.")
        else:
            question = query or "What's most important right now?"
        
        # F2b: Special handling for user mentions - search raw transcripts
        if topic == "rowan_mentions":
            context = await self._search_user_mentions_in_transcripts(user_name)
        else:
            # Standard context from recent meetings
            context = await self._get_recent_meetings_context()
        
        prompt = f"""Based on this context from recent meetings and documents:

{context}

Question: {question}

Provide a concise, helpful answer. Focus on the most relevant information. Use bullet points where appropriate."""

        try:
            response = await self.ask_llm(
                prompt=prompt,
                task_type="synthesis",  # Use synthesis model for summarization
            )
            return {"response": response, "success": True}
        except Exception as e:
            logger.error(f"Quick ask failed: {e}")
            return {"response": f"AI Error: {str(e)}", "success": False}
    
    def _enhance_response(
        self,
        response_text: str,
        execution_result: Dict[str, Any],
    ) -> str:
        """Add action-specific details to the response."""
        action = execution_result.get("action")
        
        if action == "create_ticket":
            response_text += f"\n\n✅ Created ticket: **{execution_result.get('ticket_id')}**"
        
        elif action == "create_accountability":
            response_text += "\n\n✅ Added to your waiting-for list!"
        
        elif action == "create_standup":
            response_text += "\n\n✅ Standup logged!"
        
        elif action == "change_model":
            response_text += f"\n\n✅ AI model changed to **{execution_result.get('model')}**"
        
        elif action == "update_sprint":
            details = []
            if execution_result.get("sprint_name"):
                details.append(f"name: **{execution_result.get('sprint_name')}**")
            if execution_result.get("sprint_goal"):
                details.append(f"goal: **{execution_result.get('sprint_goal')}**")
            response_text += f"\n\n✅ Sprint updated - {', '.join(details)}"
        
        elif action == "reset_workflow":
            response_text += "\n\n✅ All workflow progress has been reset! Ready for a fresh sprint."
        
        elif action == "search_meetings":
            meetings = execution_result.get("meetings", [])
            if meetings:
                response_text += "\n\n📅 **Found meetings:**\n"
                for m in meetings[:5]:
                    response_text += f"• {m.get('meeting_name')} ({m.get('meeting_date')})\n"
            else:
                response_text += "\n\nNo meetings found matching your search."
        
        elif action == "list_tickets":
            tickets = execution_result.get("tickets", [])
            if tickets:
                response_text += "\n\n📋 **Your tickets:**\n"
                status_emoji = {
                    "todo": "⬜",
                    "in_progress": "🔄",
                    "blocked": "🚫",
                    "done": "✅",
                }
                for t in tickets[:5]:
                    emoji = status_emoji.get(t.get("status"), "⬜")
                    response_text += f"• {emoji} {t.get('ticket_id')}: {t.get('title')}\n"
        
        return response_text


# =============================================================================
# ADAPTER FUNCTIONS - For backward compatibility with api/assistant.py
# =============================================================================

# Global agent instance for adapter
_arjuna_instance: Optional[ArjunaAgent] = None


class SimpleLLMClient:
    """Simple LLM client wrapper for use outside the registry."""
    
    async def ask(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Call the LLM."""
        from ..llm import _client_once
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        resp = _client_once().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()


def get_arjuna_agent() -> ArjunaAgent:
    """Get or create the global Arjuna agent instance."""
    global _arjuna_instance
    
    if _arjuna_instance is None:
        config = AgentConfig(
            name="arjuna",
            description="SignalFlow smart assistant for natural language interactions",
            primary_model="gpt-4o-mini",
            fallback_model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=1000,
            system_prompt_file="prompts/agents/arjuna/system.jinja2",
            tools=["create_ticket", "update_ticket", "navigate", "search"],
        )
        _arjuna_instance = ArjunaAgent(
            config=config,
            llm_client=SimpleLLMClient(),
        )
    
    return _arjuna_instance


# Adapter functions to maintain backward compatibility
def get_follow_up_suggestions(action: str, intent: str, result: dict) -> List[str]:
    """Adapter: Get follow-up suggestions (delegates to ArjunaAgent)."""
    agent = get_arjuna_agent()
    return agent._get_follow_up_suggestions(action, intent, result)


def get_focus_recommendations() -> Dict[str, Any]:
    """Adapter: Get focus recommendations (delegates to ArjunaAgent)."""
    agent = get_arjuna_agent()
    return agent._get_focus_recommendations()


def get_system_context() -> Dict[str, Any]:
    """Adapter: Get system context (delegates to ArjunaAgent)."""
    agent = get_arjuna_agent()
    return agent._get_system_context()


def parse_assistant_intent(message: str, context: dict, history: list) -> dict:
    """
    Adapter: Parse assistant intent (delegates to ArjunaAgent).
    
    Note: This is a synchronous adapter. For async code, use ArjunaAgent directly.
    """
    import asyncio
    
    agent = get_arjuna_agent()
    
    # Check for focus queries (synchronous path)
    if agent._is_focus_query(message):
        focus_data = agent._get_focus_recommendations()
        recs = focus_data.get("recommendations", [])
        
        if recs:
            response_text = agent._format_focus_response(recs, focus_data)
            return {
                "intent": "focus_recommendations",
                "confidence": 1.0,
                "entities": {},
                "clarifications": [],
                "response_text": response_text,
                "suggested_page": "/tickets" if any(
                    r["type"] in ["blocker", "active", "todo"] for r in recs
                ) else None,
                "focus_data": focus_data,
            }
        else:
            return {
                "intent": "focus_recommendations",
                "confidence": 1.0,
                "entities": {},
                "clarifications": [],
                "response_text": (
                    "Hare Krishna! 🙏 You're all caught up! No urgent items need attention right now.\n\n"
                    "Consider:\n"
                    "• Reviewing signals to build your knowledge base\n"
                    "• Planning ahead for upcoming work\n"
                    "• Taking a well-deserved break!"
                ),
                "suggested_page": None,
            }
    
    # For other intents, we need async - run in event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    agent._parse_intent(message, context, history),
                )
                return future.result()
        else:
            return loop.run_until_complete(
                agent._parse_intent(message, context, history)
            )
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}")
        return {
            "intent": "ask_question",
            "confidence": 0.5,
            "entities": {},
            "clarifications": [],
            "response_text": f"I had trouble understanding that. Could you rephrase?",
        }


def execute_intent(intent_data: dict) -> dict:
    """
    Adapter: Execute intent (delegates to ArjunaAgent).
    
    Note: This is a synchronous adapter. For async code, use ArjunaAgent directly.
    """
    import asyncio
    
    agent = get_arjuna_agent()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    agent._execute_intent(intent_data),
                )
                return future.result()
        else:
            return loop.run_until_complete(agent._execute_intent(intent_data))
    except Exception as e:
        logger.error(f"Intent execution failed: {e}")
        return {"success": False, "error": str(e)}


async def quick_ask(topic: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
    """
    Adapter: Quick AI questions from dashboard (delegates to ArjunaAgent).
    
    Args:
        topic: Predefined topic (blockers, decisions, action_items, etc.)
        query: Custom query string
    
    Returns:
        Dict with response and success status
    """
    agent = get_arjuna_agent()
    return await agent.quick_ask(topic=topic, query=query)


def quick_ask_sync(topic: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronous adapter for quick_ask (for use in sync contexts).
    
    Args:
        topic: Predefined topic (blockers, decisions, action_items, etc.)
        query: Custom query string
    
    Returns:
        Dict with response and success status
    """
    import asyncio
    
    agent = get_arjuna_agent()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    agent.quick_ask(topic=topic, query=query),
                )
                return future.result()
        else:
            return loop.run_until_complete(agent.quick_ask(topic=topic, query=query))
    except Exception as e:
        logger.error(f"Quick ask failed: {e}")
        return {"response": f"AI Error: {str(e)}", "success": False}


async def interpret_user_status_adapter(status_text: str) -> Dict[str, Any]:
    """
    Adapter: Interpret user status text into structured data.
    
    Migration Note (P1.8): Centralizes status interpretation logic.
    
    Args:
        status_text: Raw status text from user
    
    Returns:
        Dict with mode, activity, context fields
    """
    if not status_text:
        return {"mode": "implementation", "activity": "", "context": ""}
    
    prompt = f"""Interpret this user status and extract structured data:
Status: "{status_text}"

Return ONLY a JSON object with these fields:
- mode: one of [grooming, planning, standup, implementation]
- activity: short description of what they're doing
- context: any relevant context or details

Examples:
"Working on the airflow DAG refactor" -> {{"mode": "implementation", "activity": "refactoring airflow DAG", "context": "airflow"}}
"Preparing for sprint planning" -> {{"mode": "planning", "activity": "sprint planning prep", "context": "sprint planning"}}
"In standup" -> {{"mode": "standup", "activity": "daily standup", "context": "standup meeting"}}

Return only valid JSON, no markdown or explanation."""

    agent = get_arjuna_agent()
    
    try:
        result = await agent.ask_llm(prompt, task_type="classification")
        # Clean up markdown if present
        result = result.strip()
        if result.startswith("```json"):
            result = result.split("```json")[1].split("```")[0].strip()
        elif result.startswith("```"):
            result = result.split("```")[1].split("```")[0].strip()
        
        import json
        parsed = json.loads(result)
        
        return {
            "mode": parsed.get("mode", "implementation"),
            "activity": parsed.get("activity", status_text),
            "context": parsed.get("context", ""),
            "success": True
        }
    except Exception as e:
        logger.error(f"Status interpretation failed: {e}")
        return {
            "mode": "implementation",
            "activity": status_text,
            "context": "",
            "success": False
        }


# Export constants for backward compatibility
__all__ = [
    "ArjunaAgent",
    "get_arjuna_agent",
    "AVAILABLE_MODELS",
    "SYSTEM_PAGES",
    "MODEL_ALIASES",
    "FOCUS_KEYWORDS",
    # MCP Short Notation Commands
    "MCP_COMMANDS",
    "MCP_INFERENCE_PATTERNS",
    "parse_mcp_command",
    "infer_mcp_command",
    "get_command_help",
    # Adapter functions
    "get_follow_up_suggestions",
    "get_focus_recommendations",
    "get_system_context",
    "parse_assistant_intent",
    "execute_intent",
    "quick_ask",
    "quick_ask_sync",
    "interpret_user_status_adapter",
]
