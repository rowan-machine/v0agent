# src/app/agents/arjuna/chain_executor.py
"""
Arjuna Chain Command Executor

Handles multi-step chain commands for automated workflows.
Extracted from _arjuna_core.py for better organization.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Chain definitions - ordered steps for each chain
CHAIN_DEFINITIONS = {
    "quick-ticket": {
        "description": "Create a ticket and add to sprint",
        "steps": ["create_ticket", "add_to_sprint"],
    },
    "full-ticket": {
        "description": "Create ticket with plan and decompose",
        "steps": ["create_ticket", "add_to_sprint", "generate_plan", "decompose_tasks"],
    },
    "standup": {
        "description": "Create and analyze standup",
        "steps": ["create_standup", "analyze_standup", "suggest_improvements"],
    },
    "meeting": {
        "description": "Analyze meeting and extract signals",
        "steps": ["analyze_meeting", "extract_signals", "promote_signals"],
    },
    "focus-start": {
        "description": "Get focus recommendations and start top task",
        "steps": ["get_focus_recommendations", "update_ticket_status"],
    },
    "block-task": {
        "description": "Mark task as blocked and create accountability",
        "steps": ["update_ticket_blocked", "create_accountability"],
    },
}


class ArjunaChainMixin:
    """
    Mixin class for chain command execution in Arjuna agent.
    
    Provides methods for:
    - Multi-step workflow automation
    - Chain definition and execution
    - Step result aggregation
    """
    
    async def _execute_chain_command(
        self,
        chain_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a multi-step chain command.
        
        Args:
            chain_name: Name of the chain to execute
            args: Arguments for the chain
            context: Current system context
            
        Returns:
            Aggregated result from all chain steps
        """
        if chain_name not in CHAIN_DEFINITIONS:
            available = ", ".join(CHAIN_DEFINITIONS.keys())
            return {
                "response": f"Unknown chain: `{chain_name}`\n\nAvailable chains: {available}",
                "success": False,
                "command_mode": True,
            }
        
        chain_def = CHAIN_DEFINITIONS[chain_name]
        steps = chain_def["steps"]
        
        results = []
        previous_outputs = {}
        
        for step in steps:
            result = await self._execute_chain_step(step, args, context, previous_outputs)
            results.append({"step": step, "result": result})
            
            # Store output for subsequent steps
            previous_outputs[step] = result
            
            # Stop chain on failure (unless it's a non-critical step)
            if not result.get("success") and step not in ("suggest_improvements", "promote_signals"):
                return {
                    "response": f"❌ Chain `{chain_name}` failed at step `{step}`:\n\n{result.get('error', 'Unknown error')}",
                    "success": False,
                    "chain_name": chain_name,
                    "failed_step": step,
                    "results": results,
                    "command_mode": True,
                }
        
        # Build success response
        final_result = results[-1]["result"] if results else {}
        response_parts = [
            f"✅ Chain `{chain_name}` completed!",
            f"_{chain_def['description']}_",
            "",
            "**Steps executed:**",
        ]
        
        for r in results:
            step_status = "✅" if r["result"].get("success") else "⚠️"
            summary = r["result"].get("summary", r["result"].get("action", r["step"]))
            response_parts.append(f"- {step_status} {r['step']}: {summary}")
        
        return {
            "response": "\n".join(response_parts),
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


__all__ = ["ArjunaChainMixin", "CHAIN_DEFINITIONS"]
