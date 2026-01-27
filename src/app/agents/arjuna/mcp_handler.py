# src/app/agents/arjuna/mcp_handler.py
"""
Arjuna MCP Command Handler

Handles MCP short notation commands for the Arjuna agent.
Extracted from _arjuna_core.py for better organization.
"""

import json
import logging
from typing import Any, Dict

from ...mcp.command_parser import get_command_help

logger = logging.getLogger(__name__)


class ArjunaMCPMixin:
    """
    Mixin class for MCP command handling in Arjuna agent.
    
    Provides methods for:
    - Parsing and executing MCP commands
    - Routing commands to appropriate handlers
    - Inter-agent command delegation
    """
    
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
            from ...mcp.subcommand_router import get_subcommand_router
            
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


__all__ = ["ArjunaMCPMixin"]
