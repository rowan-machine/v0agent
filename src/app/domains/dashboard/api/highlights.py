# src/app/domains/dashboard/api/highlights.py
"""
Dashboard Highlights API

Smart coaching highlights based on app state and user activity.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/highlights")
async def get_highlights(request: Request):
    """Get smart coaching highlights based on app state and user activity."""
    from ....services.meeting_service import meeting_service
    from ....services.ticket_service import ticket_service
    from ....repositories import get_settings_repository, get_signal_repository, get_dikw_repository
    from ....infrastructure.supabase_client import get_supabase_client
    
    settings_repo = get_settings_repository()
    signal_repo = get_signal_repository()
    dikw_repo = get_dikw_repository()
    supabase = get_supabase_client()
    
    # Get dismissed IDs from query param (passed from frontend localStorage)
    dismissed_ids = request.query_params.get('dismissed', '').split(',')
    dismissed_ids = [d.strip() for d in dismissed_ids if d.strip()]
    
    highlights = []
    
    # 1. Check for blocked tickets (HIGH PRIORITY) - from Supabase
    blocked_tickets = ticket_service.get_blocked_tickets(limit=3)
    for t in blocked_tickets:
        highlight_id = f"blocked-{t.get('ticket_id')}"
        if highlight_id not in dismissed_ids:
            highlights.append({
                "id": highlight_id,
                "type": "blocker",
                "label": "🚧 Blocked Ticket",
                "text": f"{t.get('ticket_id')}: {t.get('title')}",
                "action": "Unblock this ticket to keep making progress",
                "link": f"/tickets?focus={t.get('ticket_id')}",
                "link_text": "View Ticket"
            })
    
    # 2. Check for stale in-progress tickets (> 3 days old) - from Supabase
    stale_tickets = ticket_service.get_stale_in_progress_tickets(days=3, limit=2)
    for t in stale_tickets:
        highlight_id = f"stale-{t.get('ticket_id')}"
        if highlight_id not in dismissed_ids:
            highlights.append({
                "id": highlight_id,
                "type": "action",
                "label": "⏰ Stale Work",
                "text": f"{t.get('ticket_id')}: {t.get('title')}",
                "action": "This has been in progress for a while. Complete or update it?",
                "link": f"/tickets?focus={t.get('ticket_id')}",
                "link_text": "Update Status"
            })
    
    # 3. Check sprint progress using settings repository
    try:
        sprint = settings_repo.get_sprint_settings()
        if sprint and sprint.get('sprint_start_date'):
            start = datetime.strptime(sprint['sprint_start_date'], '%Y-%m-%d')
            length = sprint.get('sprint_length_days') or 14
            end = start + timedelta(days=length)
            now = datetime.now()
            progress = min(100, max(0, int((now - start).days / length * 100)))
            days_left = (end - now).days
            
            # Sprint ending soon
            if 0 < days_left <= 3 and f"sprint-ending" not in dismissed_ids:
                todo_count = ticket_service.get_tickets_count(statuses=["todo"])
                if todo_count > 0:
                    highlights.append({
                        "id": "sprint-ending",
                        "type": "risk",
                        "label": "⏳ Sprint Ending",
                        "text": f"{days_left} day{'s' if days_left != 1 else ''} left with {todo_count} todo items",
                        "action": "Review remaining work and prioritize",
                        "link": "/tickets",
                        "link_text": "View Tickets"
                    })
            
            # Sprint just started - set it up
            if progress < 10 and f"sprint-setup" not in dismissed_ids:
                ticket_count = ticket_service.get_tickets_count()
                if ticket_count == 0:
                    highlights.append({
                        "id": "sprint-setup",
                        "type": "action",
                        "label": "🚀 New Sprint",
                        "text": "Your sprint has started but no tickets yet",
                        "action": "Create tickets to track your work this sprint",
                        "link": "/tickets",
                        "link_text": "Add Tickets"
                    })
    except Exception:
        pass
    
    # 4. Check for unreviewed signals using signal repository
    try:
        unreviewed_count = signal_repo.get_unreviewed_count()
        if unreviewed_count > 5 and "review-signals" not in dismissed_ids:
            highlights.append({
                "id": "review-signals",
                "type": "action",
                "label": "📥 Unreviewed Signals",
                "text": f"{unreviewed_count} signals waiting for your review",
                "action": "Validate signals to build your knowledge base",
                "link": "/signals",
                "link_text": "Review Signals"
            })
    except Exception:
        pass
    
    # 5. Recent meeting with unprocessed signals (from Supabase)
    try:
        recent_meetings_for_highlights = meeting_service.get_meetings_with_signals(limit=1)
        if recent_meetings_for_highlights:
            recent_meeting = recent_meetings_for_highlights[0]
            try:
                signals = recent_meeting.get('signals', {})
                blockers = signals.get('blockers', [])
                actions = signals.get('action_items', [])
                
                # Highlight blockers from recent meeting
                for i, blocker in enumerate(blockers[:2]):
                    if blocker:
                        highlight_id = f"mtg-blocker-{recent_meeting['id']}-{i}"
                        if highlight_id not in dismissed_ids:
                            highlights.append({
                                "id": highlight_id,
                                "type": "blocker",
                                "label": "🚧 Meeting Blocker",
                                "text": blocker[:100] + ('...' if len(blocker) > 100 else ''),
                                "action": f"From: {recent_meeting['meeting_name']}",
                                "link": f"/meetings/{recent_meeting['id']}",
                                "link_text": "View Meeting"
                            })
                
                # Highlight action items from recent meeting
                for i, action in enumerate(actions[:2]):
                    if action:
                        highlight_id = f"mtg-action-{recent_meeting['id']}-{i}"
                        if highlight_id not in dismissed_ids:
                            highlights.append({
                                "id": highlight_id,
                                "type": "action",
                                "label": "📋 Action Item",
                                "text": action[:100] + ('...' if len(action) > 100 else ''),
                                "action": f"From: {recent_meeting['meeting_name']}",
                                "link": f"/meetings/{recent_meeting['id']}",
                                "link_text": "View Meeting"
                            })
            except Exception:
                pass
    except Exception:
        pass
    
    # 6. Accountability items (waiting for others)
    try:
        if supabase:
            result = supabase.table("accountability_items")\
                .select("id, description, responsible_party")\
                .eq("status", "waiting")\
                .order("created_at", desc=True)\
                .limit(2)\
                .execute()
            waiting = result.data or []
            for w in waiting:
                highlight_id = f"waiting-{w['id']}"
                if highlight_id not in dismissed_ids:
                    highlights.append({
                        "id": highlight_id,
                        "type": "waiting",
                        "label": "⏳ Waiting On",
                        "text": f"{w['responsible_party']}: {w['description'][:80]}",
                        "action": "Follow up if this is blocking you",
                        "link": "/accountability",
                        "link_text": "Waiting-For List"
                    })
    except Exception:
        pass
    
    # 7. Check for empty DIKW (encourage knowledge building)
    try:
        pyramid = dikw_repo.get_pyramid()
        dikw_count = sum(pyramid.counts.values()) if pyramid else 0
        if dikw_count == 0 and "dikw-empty" not in dismissed_ids:
            highlights.append({
                "id": "dikw-empty",
                "type": "idea",
                "label": "💡 Knowledge Base",
                "text": "Start building your knowledge pyramid",
                "action": "Promote signals to DIKW to capture learnings",
                "link": "/dikw",
                "link_text": "View DIKW"
            })
    except Exception:
        pass
    
    # 8. No recent meetings (encourage logging) - check Supabase
    try:
        recent_meetings_check = meeting_service.get_meetings_with_signals_in_range(days=7)
        if len(recent_meetings_check) == 0 and "log-meeting" not in dismissed_ids:
            highlights.append({
                "id": "log-meeting",
                "type": "idea",
                "label": "📅 Log a Meeting",
                "text": "No meetings logged in the past week",
                "action": "Capture decisions and actions from recent discussions",
                "link": "/meetings/new",
                "link_text": "Add Meeting"
            })
    except Exception:
        pass
    
    # 9. Enhanced recommendations from engine (Technical Debt)
    try:
        from ....services.coach_recommendations import get_coach_recommendations
        engine_recs = get_coach_recommendations(
            dismissed_ids=dismissed_ids,
            user_name="Rowan"  # TODO: Get from auth context
        )
        # Add engine recommendations that aren't duplicates
        existing_ids = {h['id'] for h in highlights}
        for rec in engine_recs:
            if rec['id'] not in existing_ids:
                highlights.append(rec)
    except Exception as e:
        # Silent fail - don't break highlights if engine has issues
        logger.debug(f"Coach engine error: {e}")
    
    # Prioritize: blockers > mentions > risks > actions > waiting > dikw > grooming > ideas
    priority = {
        'blocker': 0, 
        'mention': 1,
        'risk': 2, 
        'action': 3, 
        'waiting': 4, 
        'dikw': 5,
        'grooming': 6,
        'transcript': 7,
        'idea': 8, 
        'decision': 9
    }
    highlights.sort(key=lambda h: priority.get(h['type'], 99))
    
    # Return top 8 items (increased from 6 for more recommendations)
    return JSONResponse({"highlights": highlights[:8]})


__all__ = ["router"]
