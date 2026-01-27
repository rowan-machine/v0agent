# src/app/agents/arjuna/standup.py
"""
Arjuna Standup Mixin - Standup-related functionality.

This mixin provides all standup-related methods for the Arjuna agent:
- Standup context gathering
- Standup draft generation
- Standup formatting for prompts
- Standup creation
"""

from datetime import date, timedelta
from typing import Any, Dict
import json
import logging

logger = logging.getLogger(__name__)


class ArjunaStandupMixin:
    """
    Mixin providing standup functionality for ArjunaAgent.
    
    Methods:
    - _get_standup_context(): Gather all activity for standup generation
    - _format_standup_context_for_prompt(): Format context as readable text
    - generate_standup_draft(): AI-powered standup draft generation
    - _create_standup(): Save a standup entry
    """
    
    def _get_standup_context(self) -> Dict[str, Any]:
        """
        Get comprehensive context for standup updates.
        
        Gathers:
        - Meetings attended today/yesterday
        - Action items completed/checked off
        - Ticket checklist items completed
        - Test plans created/updated
        - Current blockers
        - Tickets worked on
        
        Returns dict with all relevant activity for standup generation.
        """
        conn = self._get_db_connection()
        if not conn:
            return {"error": "No database connection"}
        
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        context = {
            "today": today,
            "yesterday": yesterday,
            "meetings_today": [],
            "meetings_yesterday": [],
            "completed_action_items": [],
            "tickets_worked_on": [],
            "checklist_items_done": [],
            "test_plans_created": [],
            "blockers": [],
            "waiting_for": [],
        }
        
        try:
            # Meetings today and yesterday
            meetings = conn.execute(
                """SELECT id, meeting_name, meeting_date, synthesized_notes 
                   FROM meeting_summaries 
                   WHERE meeting_date IN (?, ?)
                   ORDER BY meeting_date DESC, created_at DESC""",
                (today, yesterday)
            ).fetchall()
            
            for m in meetings:
                meeting_info = {
                    "id": m["id"],
                    "name": m["meeting_name"],
                    "date": m["meeting_date"],
                    "summary": (m["synthesized_notes"] or "")[:200]
                }
                if m["meeting_date"] == today:
                    context["meetings_today"].append(meeting_info)
                else:
                    context["meetings_yesterday"].append(meeting_info)
            
            # Completed action items (recently updated to 'complete')
            completed = conn.execute(
                """SELECT description, responsible_party, updated_at
                   FROM accountability_items 
                   WHERE status = 'complete' AND DATE(updated_at) IN (?, ?)
                   ORDER BY updated_at DESC LIMIT 10""",
                (today, yesterday)
            ).fetchall()
            context["completed_action_items"] = [
                {"description": a["description"], "completed_at": a["updated_at"]}
                for a in completed
            ]
            
            # Tickets worked on (updated today/yesterday)
            worked_tickets = conn.execute(
                """SELECT ticket_id, title, status, task_decomposition, updated_at
                   FROM tickets 
                   WHERE DATE(updated_at) IN (?, ?)
                   ORDER BY updated_at DESC LIMIT 10""",
                (today, yesterday)
            ).fetchall()
            
            for t in worked_tickets:
                ticket_info = {
                    "ticket_id": t["ticket_id"],
                    "title": t["title"],
                    "status": t["status"],
                    "updated_at": t["updated_at"],
                    "checklist_done": []
                }
                # Parse checklist for completed items
                if t["task_decomposition"]:
                    try:
                        tasks = json.loads(t["task_decomposition"])
                        ticket_info["checklist_done"] = [
                            task.get("text", str(task))[:80]
                            for task in tasks if task.get("done", False)
                        ]
                    except:
                        pass
                context["tickets_worked_on"].append(ticket_info)
            
            # Test plans created/updated
            test_plans = conn.execute(
                """SELECT test_plan_id, title, status, created_at, updated_at
                   FROM test_plans 
                   WHERE DATE(created_at) IN (?, ?) OR DATE(updated_at) IN (?, ?)
                   ORDER BY updated_at DESC LIMIT 5""",
                (today, yesterday, today, yesterday)
            ).fetchall()
            context["test_plans_created"] = [
                {"test_plan_id": tp["test_plan_id"], "title": tp["title"], "status": tp["status"]}
                for tp in test_plans
            ]
            
            # Current blockers
            blockers = conn.execute(
                """SELECT signal_text, created_at FROM signal_status 
                   WHERE signal_type = 'blocker' AND status NOT IN ('rejected', 'completed')
                   ORDER BY created_at DESC LIMIT 5"""
            ).fetchall()
            context["blockers"] = [b["signal_text"] for b in blockers]
            
            # Waiting for items
            waiting = conn.execute(
                """SELECT description, responsible_party FROM accountability_items
                   WHERE status = 'waiting'
                   ORDER BY created_at DESC LIMIT 5"""
            ).fetchall()
            context["waiting_for"] = [
                {"who": w["responsible_party"], "what": w["description"][:60]}
                for w in waiting
            ]
            
        except Exception as e:
            logger.error(f"Failed to get standup context: {e}")
            context["error"] = str(e)
        
        return context
    
    def _format_standup_context_for_prompt(self, ctx: Dict[str, Any]) -> str:
        """Format standup context as a readable prompt section."""
        lines = ["## Activity Summary for Standup\n"]
        
        # Yesterday's meetings
        if ctx.get("meetings_yesterday"):
            lines.append("**Meetings attended yesterday:**")
            for m in ctx["meetings_yesterday"][:3]:
                lines.append(f"- {m['name']}")
            lines.append("")
        
        # Today's meetings
        if ctx.get("meetings_today"):
            lines.append("**Meetings today:**")
            for m in ctx["meetings_today"][:3]:
                lines.append(f"- {m['name']}")
            lines.append("")
        
        # Completed action items
        if ctx.get("completed_action_items"):
            lines.append("**Action items completed:**")
            for a in ctx["completed_action_items"][:5]:
                lines.append(f"- {a['description'][:60]}")
            lines.append("")
        
        # Tickets worked on
        if ctx.get("tickets_worked_on"):
            lines.append("**Tickets worked on:**")
            for t in ctx["tickets_worked_on"][:5]:
                lines.append(f"- {t['ticket_id']}: {t['title'][:40]} ({t['status']})")
                if t.get("checklist_done"):
                    for item in t["checklist_done"][:3]:
                        lines.append(f"  ✓ {item}")
            lines.append("")
        
        # Test plans
        if ctx.get("test_plans_created"):
            lines.append("**Test plans created/updated:**")
            for tp in ctx["test_plans_created"][:3]:
                lines.append(f"- {tp['test_plan_id']}: {tp['title']}")
            lines.append("")
        
        # Blockers
        if ctx.get("blockers"):
            lines.append("**Current blockers:**")
            for b in ctx["blockers"][:3]:
                lines.append(f"- {b[:60]}")
            lines.append("")
        
        # Waiting for
        if ctx.get("waiting_for"):
            lines.append("**Waiting for:**")
            for w in ctx["waiting_for"][:3]:
                lines.append(f"- {w['who']}: {w['what']}")
            lines.append("")
        
        return "\n".join(lines) if len(lines) > 1 else "No recent activity found."
    
    async def generate_standup_draft(self) -> Dict[str, Any]:
        """
        Generate a draft standup update based on recent activity.
        
        Returns:
            Dict with:
            - draft: The generated standup text
            - context: Activity used to generate it
            - offer_to_log: True (always offer to save)
        """
        ctx = self._get_standup_context()
        
        if ctx.get("error"):
            return {"success": False, "error": ctx["error"]}
        
        # Format context for the prompt
        context_text = self._format_standup_context_for_prompt(ctx)
        
        # Generate standup using LLM
        prompt = f"""Based on the following activity summary, generate a concise standup update
in the format: Yesterday, Today, Blockers.

{context_text}

Generate a professional standup update (3-5 bullet points max per section).
If no activity in a section, skip it.
Be specific about what was done/planned."""

        try:
            # Use the LLM client from the agent
            if hasattr(self, 'llm_client') and self.llm_client:
                response = await self.llm_client.generate(prompt)
                draft = response.get("content", "")
            else:
                # Fallback if no LLM client
                draft = self._generate_simple_standup_draft(ctx)
            
            return {
                "success": True,
                "draft": draft,
                "context": ctx,
                "offer_to_log": True
            }
        except Exception as e:
            logger.error(f"Failed to generate standup draft: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_simple_standup_draft(self, ctx: Dict[str, Any]) -> str:
        """Generate a simple standup draft without LLM."""
        lines = []
        
        # Yesterday section
        yesterday_items = []
        if ctx.get("meetings_yesterday"):
            for m in ctx["meetings_yesterday"][:2]:
                yesterday_items.append(f"Attended {m['name']}")
        if ctx.get("completed_action_items"):
            for a in ctx["completed_action_items"][:2]:
                yesterday_items.append(f"Completed: {a['description'][:50]}")
        
        if yesterday_items:
            lines.append("**Yesterday:**")
            for item in yesterday_items:
                lines.append(f"- {item}")
            lines.append("")
        
        # Today section
        today_items = []
        if ctx.get("meetings_today"):
            for m in ctx["meetings_today"][:2]:
                today_items.append(f"Attending {m['name']}")
        if ctx.get("tickets_worked_on"):
            for t in ctx["tickets_worked_on"][:2]:
                today_items.append(f"Working on {t['ticket_id']}: {t['title'][:30]}")
        
        if today_items:
            lines.append("**Today:**")
            for item in today_items:
                lines.append(f"- {item}")
            lines.append("")
        
        # Blockers section
        if ctx.get("blockers"):
            lines.append("**Blockers:**")
            for b in ctx["blockers"][:2]:
                lines.append(f"- {b[:50]}")
        
        return "\n".join(lines) if lines else "No recent activity to summarize."
    
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
