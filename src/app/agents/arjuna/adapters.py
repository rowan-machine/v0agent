# src/app/agents/arjuna/adapters.py
"""
Arjuna Agent Adapters - Module-level adapter functions for backward compatibility.

These functions provide a synchronous API for code that needs to call
the Arjuna agent without async/await. They delegate to the ArjunaAgent
instance internally.

NOTE: For new code, prefer using ArjunaAgent directly with async/await.
"""

from typing import Any, Dict, List, Optional
import asyncio
import logging

from ..base import AgentConfig

logger = logging.getLogger(__name__)


# Global agent instance for adapter functions
_arjuna_instance = None


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
        from ...llm import _openai_client_once
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        resp = _openai_client_once().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()


def get_arjuna_agent():
    """
    Get or create the global Arjuna agent instance.
    
    Returns:
        ArjunaAgentCore instance (using decomposed mixin-based implementation)
    """
    global _arjuna_instance
    
    if _arjuna_instance is None:
        # Use the new mixin-based ArjunaAgentCore from core.py
        from .core import ArjunaAgentCore
        
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
        _arjuna_instance = ArjunaAgentCore(
            config=config,
            llm_client=SimpleLLMClient(),
        )
    
    return _arjuna_instance


def get_follow_up_suggestions(action: str, intent: str, result: dict) -> List[Dict[str, str]]:
    """
    Adapter: Get follow-up suggestions (delegates to ArjunaAgent).
    
    Args:
        action: The action that was performed
        intent: The parsed intent
        result: The execution result
    
    Returns:
        List of suggestion dicts with emoji, text, message
    """
    agent = get_arjuna_agent()
    return agent._get_follow_up_suggestions(action, intent, result)


def get_focus_recommendations() -> Dict[str, Any]:
    """
    Adapter: Get focus recommendations (delegates to ArjunaAgent).
    
    Returns:
        Dict with recommendations, priorities, and context
    """
    agent = get_arjuna_agent()
    return agent._get_focus_recommendations()


def get_system_context() -> Dict[str, Any]:
    """
    Adapter: Get system context (delegates to ArjunaAgent).
    
    Returns:
        Dict with sprint, tickets, and system state
    """
    agent = get_arjuna_agent()
    return agent._get_system_context()


def parse_assistant_intent(
    message: str,
    context: dict,
    history: list,
    thread_id: str = None,
) -> dict:
    """
    Adapter: Parse assistant intent (delegates to ArjunaAgent).
    
    This is a synchronous adapter. For async code, use ArjunaAgent directly.
    
    Args:
        message: User's message
        context: System context
        history: Conversation history
        thread_id: Optional thread ID for LangSmith tracing
    
    Returns:
        Dict with intent, entities, confidence, response_text
    """
    agent = get_arjuna_agent()
    
    # Set thread_id on agent for LangSmith tracing
    if thread_id:
        agent._thread_id = thread_id
    
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
            "response_text": "I had trouble understanding that. Could you rephrase?",
        }


def execute_intent(intent_data: dict) -> dict:
    """
    Adapter: Execute intent (delegates to ArjunaAgent).
    
    This is a synchronous adapter. For async code, use ArjunaAgent directly.
    
    Args:
        intent_data: Parsed intent data from parse_assistant_intent
    
    Returns:
        Dict with success, action, result, error
    """
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


# ============================================================================
# ASYNC ADAPTER FUNCTIONS
# These are for use in FastAPI async routes (e.g., api/assistant.py)
# ============================================================================

async def parse_assistant_intent_async(
    message: str,
    context: dict,
    history: list,
    thread_id: str = None,
) -> dict:
    """
    Async adapter: Parse assistant intent (delegates to ArjunaAgent).
    
    Use this version in async FastAPI routes instead of the sync parse_assistant_intent.
    
    Args:
        message: User's message
        context: System context
        history: Conversation history
        thread_id: Optional thread ID for LangSmith tracing
    
    Returns:
        Dict with intent, entities, response_text, and run_id for feedback
    """
    agent = get_arjuna_agent()
    
    # Set thread_id on agent for LangSmith tracing
    if thread_id:
        agent._thread_id = thread_id
    
    # Check for focus queries (can be done synchronously)
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
                "run_id": getattr(agent, "last_run_id", None),
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
                "run_id": getattr(agent, "last_run_id", None),
            }
    
    # Check for 1-on-1 prep queries
    oneone_keywords = ['1-on-1', '1:1', 'one-on-one', 'one on one', '1 on 1', 
                       'working on', 'top 3', 'need help', 'blockers', 'blocked',
                       'observations', 'feedback', 'discuss', 'prepare for']
    if any(kw in message.lower() for kw in oneone_keywords):
        try:
            result = await agent.quick_ask(query=message)
            if result.get("success"):
                return {
                    "intent": "ask_question",
                    "confidence": 1.0,
                    "entities": {},
                    "clarifications": [],
                    "response_text": result.get("response", ""),
                    "suggested_page": None,
                    "run_id": getattr(agent, "last_run_id", None),
                }
        except Exception as e:
            logger.error(f"ArjunaAgent quick_ask failed: {e}")
            # Fall through to normal parsing
    
    # For other intents, use the agent's async _parse_intent method
    try:
        return await agent._parse_intent(message, context, history)
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}")
        return {
            "intent": "ask_question",
            "confidence": 0.5,
            "entities": {},
            "clarifications": [],
            "response_text": "I had trouble understanding that. Could you rephrase?",
        }


async def execute_intent_async(intent_data: dict) -> dict:
    """
    Async adapter: Execute intent (delegates to ArjunaAgent).
    
    Use this version in async FastAPI routes instead of the sync execute_intent.
    
    Args:
        intent_data: Parsed intent data from parse_assistant_intent
    
    Returns:
        Dict with success, action, result, error
    """
    agent = get_arjuna_agent()
    
    try:
        return await agent._execute_intent(intent_data)
    except Exception as e:
        logger.error(f"Intent execution failed: {e}")
        return {"success": False, "error": str(e)}


async def quick_ask(
    topic: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Adapter: Quick AI questions from dashboard (delegates to ArjunaAgent).
    
    Args:
        topic: Predefined topic (blockers, decisions, action_items, etc.)
        query: Custom query string
    
    Returns:
        Dict with response, success status, and run_id for feedback
    """
    agent = get_arjuna_agent()
    result = await agent.quick_ask(topic=topic, query=query)
    # Include run_id for user feedback
    result["run_id"] = getattr(agent, "last_run_id", None)
    return result


def quick_ask_sync(
    topic: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synchronous adapter for quick_ask (for use in sync contexts).
    
    Args:
        topic: Predefined topic (blockers, decisions, action_items, etc.)
        query: Custom query string
    
    Returns:
        Dict with response and success status
    """
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
            "success": True,
        }
    except Exception as e:
        logger.error(f"Status interpretation failed: {e}")
        return {
            "mode": "implementation",
            "activity": status_text,
            "context": "",
            "success": False,
        }


__all__ = [
    "SimpleLLMClient",
    "get_arjuna_agent",
    # Sync adapters (for backward compatibility)
    "get_follow_up_suggestions",
    "get_focus_recommendations",
    "get_system_context",
    "parse_assistant_intent",
    "execute_intent",
    # Async adapters (for FastAPI routes)
    "parse_assistant_intent_async",
    "execute_intent_async",
    "quick_ask",
    "quick_ask_sync",
    "interpret_user_status_adapter",
]
