# src/app/agents/arjuna/intents.py
"""
Arjuna Intent Parsing and Execution

Handles natural language intent parsing and execution.
Extracted from _arjuna_core.py for better organization.
"""

import json
import logging
from typing import Any, Dict, List

from .constants import AVAILABLE_MODELS

logger = logging.getLogger(__name__)


class ArjunaIntentMixin:
    """
    Mixin class for intent parsing and execution in Arjuna agent.
    
    Provides methods for:
    - LLM-based intent parsing
    - Intent prompt building
    - Intent execution dispatch
    """
    
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


__all__ = ["ArjunaIntentMixin"]
