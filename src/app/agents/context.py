"""
Shared Sprint Context Module

Provides comprehensive sprint context that all agents can use to understand
the current state of work, including:
- Sprint tickets with checklist progress
- Action items from meetings
- Test plans and their task progress
- Active blockers
- Waiting-for items

This context enables agents to be "up to speed" on what's on your plate.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_sprint_context(conn) -> Dict[str, Any]:
    """
    Get comprehensive sprint context for AI agents.
    
    Returns a dictionary with:
    - sprint_info: Current sprint details
    - tickets: Sprint tickets with checklist progress
    - action_items: Pending action items from meetings
    - test_plans: Active test plans with task progress
    - blockers: Active blockers requiring attention
    - waiting_for: Items waiting on others
    - recent_signals: Recent meeting signals
    
    Args:
        conn: SQLite connection
    
    Returns:
        Dict with full sprint context
    """
    def safe_get(row, key, default=None):
        """Safely get value from sqlite3.Row, returning default if key doesn't exist."""
        try:
            return row[key] if key in row.keys() else default
        except:
            return default
    
    context = {
        "timestamp": datetime.now().isoformat(),
        "sprint_info": None,
        "tickets": [],
        "action_items": [],
        "test_plans": [],
        "blockers": [],
        "waiting_for": [],
        "recent_decisions": [],
        "summary": {}
    }
    
    try:
        # =================================================================
        # SPRINT INFO
        # =================================================================
        sprint = conn.execute(
            "SELECT * FROM sprint_settings WHERE id = 1"
        ).fetchone()
        
        if sprint:
            days_left = None
            # Handle both old (start_date/end_date) and new (sprint_start_date/sprint_length_days) schemas
            start_date = safe_get(sprint, "start_date") or safe_get(sprint, "sprint_start_date")
            end_date = safe_get(sprint, "end_date")
            
            if not end_date and start_date and safe_get(sprint, "sprint_length_days"):
                # Calculate end date from start + length
                try:
                    start = datetime.strptime(start_date, "%Y-%m-%d")
                    end_date = (start + timedelta(days=sprint["sprint_length_days"])).strftime("%Y-%m-%d")
                except:
                    pass
            
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    days_left = (end_dt - datetime.now()).days
                except:
                    pass
            
            context["sprint_info"] = {
                "name": safe_get(sprint, "sprint_name"),
                "goal": safe_get(sprint, "sprint_goal"),
                "start_date": start_date,
                "end_date": end_date,
                "days_left": days_left,
                "current_phase": safe_get(sprint, "current_phase"),
            }
        
        # =================================================================
        # SPRINT TICKETS WITH CHECKLIST PROGRESS
        # =================================================================
        tickets = conn.execute(
            """
            SELECT 
                id, ticket_id, title, description, status, priority,
                sprint_points, task_decomposition, implementation_plan
            FROM tickets 
            WHERE in_sprint = 1
            ORDER BY 
                CASE status
                    WHEN 'blocked' THEN 1
                    WHEN 'in_progress' THEN 2
                    WHEN 'in_review' THEN 3
                    WHEN 'todo' THEN 4
                    WHEN 'done' THEN 5
                END,
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END
            """
        ).fetchall()
        
        for t in tickets:
            ticket_data = {
                "ticket_id": t["ticket_id"],
                "title": t["title"],
                "description": (safe_get(t, "description") or "")[:200],
                "status": t["status"],
                "priority": safe_get(t, "priority"),
                "points": safe_get(t, "sprint_points"),
            }
            
            # Parse checklist/task decomposition
            if safe_get(t, "task_decomposition"):
                try:
                    tasks = json.loads(t["task_decomposition"])
                    if isinstance(tasks, list):
                        total = len(tasks)
                        done = sum(1 for task in tasks if task.get("done", False))
                        ticket_data["checklist"] = {
                            "total": total,
                            "done": done,
                            "progress_pct": round(done / total * 100) if total > 0 else 0,
                            "items": [
                                {
                                    "text": task.get("text", task.get("title", str(task)))[:100],
                                    "done": task.get("done", False)
                                }
                                for task in tasks
                            ]
                        }
                except:
                    pass
            
            context["tickets"].append(ticket_data)
        
        # =================================================================
        # ACTION ITEMS / ACCOUNTABILITY ITEMS
        # =================================================================
        # Use accountability_items table (action items from meetings/signals)
        action_items = conn.execute(
            """
            SELECT id, description, responsible_party, context, status, 
                   source_type, due_date, created_at
            FROM accountability_items
            WHERE status != 'complete'
            ORDER BY 
                CASE WHEN due_date IS NOT NULL THEN 0 ELSE 1 END,
                due_date ASC,
                created_at DESC
            LIMIT 15
            """
        ).fetchall()
        
        for a in action_items:
            context["action_items"].append({
                "id": a["id"],
                "content": a["description"],
                "responsible_party": safe_get(a, "responsible_party"),
                "status": a["status"],
                "source": safe_get(a, "source_type"),
                "due_date": safe_get(a, "due_date"),
                "created": safe_get(a, "created_at", "")[:10] if safe_get(a, "created_at") else None,
            })
        
        # =================================================================
        # TEST PLANS WITH TASK PROGRESS
        # =================================================================
        test_plans = conn.execute(
            """
            SELECT 
                id, test_plan_id, title, description, status, priority,
                task_decomposition, acceptance_criteria, linked_ticket_id
            FROM test_plans
            WHERE in_sprint = 1 AND status != 'completed'
            ORDER BY 
                CASE status WHEN 'in_progress' THEN 1 ELSE 2 END,
                priority DESC
            LIMIT 10
            """
        ).fetchall()
        
        for tp in test_plans:
            plan_data = {
                "test_plan_id": tp["test_plan_id"],
                "title": tp["title"],
                "description": (safe_get(tp, "description") or "")[:150],
                "status": tp["status"],
                "priority": safe_get(tp, "priority"),
                "linked_ticket": safe_get(tp, "linked_ticket_id"),
            }
            
            if safe_get(tp, "task_decomposition"):
                try:
                    tasks = json.loads(tp["task_decomposition"])
                    if isinstance(tasks, list):
                        total = len(tasks)
                        done = sum(1 for task in tasks if task.get("done", False))
                        plan_data["tasks"] = {
                            "total": total,
                            "done": done,
                            "progress_pct": round(done / total * 100) if total > 0 else 0,
                            "items": [
                                {
                                    "text": task.get("text", task.get("title", str(task)))[:80],
                                    "done": task.get("done", False)
                                }
                                for task in tasks
                            ]
                        }
                except:
                    pass
            
            context["test_plans"].append(plan_data)
        
        # =================================================================
        # ACTIVE BLOCKERS (from signal_status table)
        # =================================================================
        blockers = conn.execute(
            """
            SELECT s.id, s.signal_text, s.created_at, s.meeting_id, m.meeting_name
            FROM signal_status s
            LEFT JOIN meeting_summaries m ON s.meeting_id = m.id
            WHERE s.signal_type = 'blocker' AND s.status NOT IN ('rejected', 'completed')
            ORDER BY s.created_at DESC
            LIMIT 10
            """
        ).fetchall()
        
        for b in blockers:
            context["blockers"].append({
                "id": b["id"],
                "content": b["signal_text"],
                "from_meeting": safe_get(b, "meeting_name"),
                "created": safe_get(b, "created_at", "")[:10] if safe_get(b, "created_at") else None,
            })
        
        # Also include blocked tickets
        blocked_tickets = [t for t in context["tickets"] if t["status"] == "blocked"]
        for bt in blocked_tickets:
            context["blockers"].append({
                "ticket_id": bt["ticket_id"],
                "content": f"Ticket {bt['ticket_id']} is blocked: {bt['title']}",
                "type": "ticket_blocked",
            })
        
        # =================================================================
        # WAITING-FOR (ACCOUNTABILITY ITEMS)
        # =================================================================
        waiting = conn.execute(
            """
            SELECT id, description, responsible_party, due_date, context, status
            FROM accountability_items
            WHERE status = 'waiting'
            ORDER BY due_date ASC NULLS LAST, created_at DESC
            LIMIT 10
            """
        ).fetchall()
        
        for w in waiting:
            context["waiting_for"].append({
                "id": w["id"],
                "description": w["description"],
                "who": w["responsible_party"],
                "due_date": w["due_date"],
                "context": w["context"],
            })
        
        # =================================================================
        # RECENT DECISIONS (last 7 days) - from signal_status table
        # =================================================================
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        decisions = conn.execute(
            """
            SELECT s.id, s.signal_text, s.created_at, m.meeting_name
            FROM signal_status s
            LEFT JOIN meeting_summaries m ON s.meeting_id = m.id
            WHERE s.signal_type = 'decision' AND s.created_at >= ?
            ORDER BY s.created_at DESC
            LIMIT 10
            """,
            (week_ago,)
        ).fetchall()
        
        for d in decisions:
            context["recent_decisions"].append({
                "content": d["signal_text"],
                "from_meeting": safe_get(d, "meeting_name"),
                "date": safe_get(d, "created_at", "")[:10] if safe_get(d, "created_at") else None,
            })
        
        # =================================================================
        # SUMMARY STATISTICS
        # =================================================================
        ticket_counts = {}
        total_checklist_items = 0
        completed_checklist_items = 0
        
        for t in context["tickets"]:
            status = t["status"]
            ticket_counts[status] = ticket_counts.get(status, 0) + 1
            if "checklist" in t:
                total_checklist_items += t["checklist"]["total"]
                completed_checklist_items += t["checklist"]["done"]
        
        context["summary"] = {
            "tickets_by_status": ticket_counts,
            "total_tickets": len(context["tickets"]),
            "pending_action_items": len(context["action_items"]),
            "active_test_plans": len(context["test_plans"]),
            "active_blockers": len(context["blockers"]),
            "waiting_for_count": len(context["waiting_for"]),
            "checklist_progress": {
                "total": total_checklist_items,
                "done": completed_checklist_items,
                "pct": round(completed_checklist_items / total_checklist_items * 100) if total_checklist_items > 0 else 0
            },
        }
        
    except Exception as e:
        logger.error(f"Failed to get sprint context: {e}")
    
    return context


def format_sprint_context_for_prompt(context: Dict[str, Any]) -> str:
    """
    Format sprint context as a human-readable string for LLM prompts.
    
    Args:
        context: Sprint context dictionary from get_sprint_context()
    
    Returns:
        Formatted string suitable for including in prompts
    """
    lines = []
    
    # Sprint Info
    if context.get("sprint_info"):
        sprint = context["sprint_info"]
        lines.append("## Current Sprint")
        lines.append(f"- Name: {sprint['name'] or 'Unnamed Sprint'}")
        if sprint.get("goal"):
            lines.append(f"- Goal: {sprint['goal']}")
        if sprint.get("days_left") is not None:
            if sprint["days_left"] < 0:
                lines.append(f"- ⚠️ Sprint ended {abs(sprint['days_left'])} days ago!")
            elif sprint["days_left"] == 0:
                lines.append("- ⚠️ Sprint ends TODAY!")
            elif sprint["days_left"] <= 3:
                lines.append(f"- ⏰ {sprint['days_left']} days left (ending soon!)")
            else:
                lines.append(f"- {sprint['days_left']} days remaining")
        lines.append("")
    
    # Summary
    if context.get("summary"):
        s = context["summary"]
        lines.append("## Sprint Summary")
        lines.append(f"- Tickets: {s.get('total_tickets', 0)} total")
        if s.get("tickets_by_status"):
            status_parts = [f"{count} {status}" for status, count in s["tickets_by_status"].items()]
            lines.append(f"  - By status: {', '.join(status_parts)}")
        if s.get("checklist_progress", {}).get("total", 0) > 0:
            cp = s["checklist_progress"]
            lines.append(f"- Checklist Progress: {cp['done']}/{cp['total']} tasks ({cp['pct']}%)")
        lines.append(f"- Pending Action Items: {s.get('pending_action_items', 0)}")
        lines.append(f"- Active Blockers: {s.get('active_blockers', 0)}")
        lines.append(f"- Waiting For: {s.get('waiting_for_count', 0)}")
        lines.append("")
    
    # Blockers (highest priority)
    if context.get("blockers"):
        lines.append("## 🚨 Active Blockers")
        for b in context["blockers"][:5]:
            lines.append(f"- {b['content'][:100]}")
        lines.append("")
    
    # In-progress tickets with checklists
    in_progress = [t for t in context.get("tickets", []) if t["status"] == "in_progress"]
    if in_progress:
        lines.append("## 🔄 In Progress")
        for t in in_progress[:5]:
            progress = ""
            if "checklist" in t:
                cl = t["checklist"]
                progress = f" [{cl['done']}/{cl['total']}]"
            lines.append(f"- {t['ticket_id']}: {t['title'][:50]}{progress}")
            if "checklist" in t:
                for item in t["checklist"]["items"][:3]:
                    check = "✓" if item["done"] else "○"
                    lines.append(f"  {check} {item['text'][:60]}")
        lines.append("")
    
    # Action Items
    if context.get("action_items"):
        lines.append("## ✅ Pending Action Items")
        for a in context["action_items"][:5]:
            owner = f" ({a.get('responsible_party', 'TBD')})" if a.get('responsible_party') else ""
            lines.append(f"- {a['content'][:80]}{owner}")
        lines.append("")
    
    # Test Plans
    if context.get("test_plans"):
        lines.append("## 🧪 Active Test Plans")
        for tp in context["test_plans"][:3]:
            progress = ""
            if "tasks" in tp:
                tasks = tp["tasks"]
                progress = f" [{tasks['done']}/{tasks['total']}]"
            lines.append(f"- {tp['test_plan_id']}: {tp['title'][:40]}{progress}")
        lines.append("")
    
    # Waiting For
    if context.get("waiting_for"):
        lines.append("## ⏳ Waiting For")
        for w in context["waiting_for"][:5]:
            due = f" (due: {w['due_date']})" if w.get("due_date") else ""
            lines.append(f"- {w['who']}: {w['description'][:60]}{due}")
        lines.append("")
    
    return "\n".join(lines)


def get_sprint_context_summary(conn) -> str:
    """
    Get a brief one-line summary of sprint status.
    
    Returns something like:
    "Sprint 'Q1 Goals' - 3 days left | 2 blocked, 3 in progress, 5 todo | 45% checklist done"
    """
    context = get_sprint_context(conn)
    
    parts = []
    
    # Sprint name and time
    if context.get("sprint_info"):
        sprint = context["sprint_info"]
        name = sprint.get("name") or "Current Sprint"
        parts.append(f"Sprint '{name}'")
        if sprint.get("days_left") is not None:
            if sprint["days_left"] <= 0:
                parts.append("ENDED")
            else:
                parts.append(f"{sprint['days_left']} days left")
    
    # Status counts
    if context.get("summary", {}).get("tickets_by_status"):
        status = context["summary"]["tickets_by_status"]
        status_parts = []
        if status.get("blocked"):
            status_parts.append(f"{status['blocked']} blocked")
        if status.get("in_progress"):
            status_parts.append(f"{status['in_progress']} in progress")
        if status.get("todo"):
            status_parts.append(f"{status['todo']} todo")
        if status_parts:
            parts.append(", ".join(status_parts))
    
    # Checklist progress
    if context.get("summary", {}).get("checklist_progress", {}).get("total", 0) > 0:
        cp = context["summary"]["checklist_progress"]
        parts.append(f"{cp['pct']}% tasks done")
    
    return " | ".join(parts)
