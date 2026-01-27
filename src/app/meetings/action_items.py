# src/app/meetings/action_items.py
"""
Action items management module.

Handles:
- Action items listing page
- Action item toggle (complete/incomplete)
- Action item priority updates
- Action item creation
- Ticket creation from action items
"""

from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
import json
import logging
from datetime import datetime
import uuid

from ..infrastructure.supabase_client import get_supabase_client
from ..services import meeting_service
from ..services.meeting_service import (
    get_meeting_signals, 
    update_meeting_signals,
    get_or_create_personal_meeting,
    get_meetings_for_action_items,
)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

# Keywords that suggest an action item should be a ticket
TICKET_KEYWORDS = [
    'implement', 'create', 'build', 'fix', 'refactor', 'deploy', 'migrate', 
    'update', 'add', 'remove', 'investigate', 'research', 'design', 'test'
]


def _extract_action_items_from_content(content: str, meeting_id: str, meeting_name: str, meeting_date: str):
    """Extract action items from document content using patterns."""
    import re
    
    items = []
    if not content:
        return items
    
    # Patterns that indicate action items
    action_patterns = [
        r'(?:action item|todo|to-do|task):\s*(.+?)(?:\n|$)',
        r'(?:- |\* )(?:action|todo|task):\s*(.+?)(?:\n|$)',
        r'(?:we need to|should|must|will)\s+(.+?)(?:\.|$)',
    ]
    
    for pattern in action_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for idx, match in enumerate(matches):
            if 10 < len(match) < 500:  # Reasonable length
                items.append({
                    'meeting_id': meeting_id,
                    'meeting_name': meeting_name,
                    'meeting_date': meeting_date,
                    'item_index': idx,
                    'text': match.strip(),
                    'completed': False,
                    'priority': 'medium',
                    'assignee': None,
                    'due_date': None,
                    'source': 'extracted_content'
                })
    return items


@router.get("/action-items")
def list_action_items(
    request: Request,
    filter_status: str = Query(default="all"),
    filter_priority: str = Query(default="all"),
    sort_by: str = Query(default="date_desc"),
    group_by: str = Query(default="none")
):
    """Display all action items across all meetings from Supabase."""
    
    all_action_items = []
    all_meetings = []
    supabase_client = get_supabase_client()
    
    # First try Supabase 'meetings' table
    try:
        # Get meetings with signals from Supabase
        supabase_meetings = supabase_client.table('meetings').select('id, meeting_name, meeting_date, signals').execute()
        
        for meeting in supabase_meetings.data:
            signals = meeting.get('signals') or {}
            if isinstance(signals, str):
                try:
                    signals = json.loads(signals)
                except:
                    signals = {}
            
            raw_items = signals.get('action_items', [])
            meeting_date = meeting.get('meeting_date', '')
            if meeting_date and 'T' in str(meeting_date):
                meeting_date = str(meeting_date).split('T')[0]
            
            for idx, item in enumerate(raw_items):
                action_item = {
                    'meeting_id': meeting['id'],
                    'meeting_name': meeting['meeting_name'],
                    'meeting_date': meeting_date,
                    'item_index': idx,
                    'completed': False,
                    'priority': 'medium',
                    'assignee': None,
                    'due_date': None,
                    'source': 'supabase'
                }
                
                if isinstance(item, dict):
                    action_item['text'] = item.get('description') or item.get('text') or str(item)
                    action_item['assignee'] = item.get('assignee')
                    action_item['priority'] = item.get('priority', 'medium')
                    action_item['due_date'] = item.get('dueDate') or item.get('due_date')
                    action_item['completed'] = item.get('completed', False)
                else:
                    action_item['text'] = str(item)
                
                # Check ticket suggestion
                text_lower = action_item['text'].lower()
                action_item['suggest_ticket'] = (
                    not action_item['completed'] and
                    action_item['priority'].lower() in ['high', 'medium'] and
                    any(kw in text_lower for kw in TICKET_KEYWORDS)
                )
                
                all_action_items.append(action_item)
        
        # Get all meetings for dropdown
        meetings_list = supabase_client.table('meetings').select('id, meeting_name').order('meeting_date', desc=True).limit(50).execute()
        all_meetings = [{'id': m['id'], 'meeting_name': m['meeting_name']} for m in meetings_list.data]
        
    except Exception as e:
        logger.warning(f"Could not load from Supabase meetings table: {e}")
    
    # Also load from Supabase meeting_summaries as fallback/supplement
    try:
        # Get meetings for dropdown
        meetings_result = supabase_client.table("meeting_summaries").select("id, meeting_name").order("meeting_date", desc=True).limit(50).execute()
        
        # Merge with Supabase meetings (avoiding duplicates)
        existing_names = {m['meeting_name'] for m in all_meetings}
        for m in meetings_result.data or []:
            if m['meeting_name'] not in existing_names:
                all_meetings.append(m)
        
        meetings_with_signals = supabase_client.table("meeting_summaries").select(
            "id, meeting_name, meeting_date, signals_json"
        ).neq("signals_json", None).neq("signals_json", "{}").order("meeting_date", desc=True).execute()
        
        # Track existing action item texts to avoid duplicates
        existing_texts = {item['text'] for item in all_action_items}
        
        for meeting in meetings_with_signals.data or []:
            try:
                signals = json.loads(meeting['signals_json'] or '{}') if isinstance(meeting['signals_json'], str) else (meeting['signals_json'] or {})
                raw_items = signals.get('action_items', [])
                
                for idx, item in enumerate(raw_items):
                    action_item = {
                        'meeting_id': meeting['id'],
                        'meeting_name': meeting['meeting_name'],
                        'meeting_date': meeting['meeting_date'],
                        'item_index': idx,
                        'completed': False,
                        'priority': 'medium',
                        'assignee': None,
                        'due_date': None,
                    }
                    
                    if isinstance(item, dict):
                        action_item['text'] = item.get('description') or item.get('text') or str(item)
                        action_item['assignee'] = item.get('assignee')
                        action_item['priority'] = item.get('priority', 'medium')
                        action_item['due_date'] = item.get('dueDate') or item.get('due_date')
                        action_item['completed'] = item.get('completed', False)
                        action_item['source'] = item.get('source', 'supabase')
                    else:
                        action_item['text'] = str(item)
                        action_item['source'] = 'supabase'
                    
                    # Skip if duplicate
                    if action_item['text'] in existing_texts:
                        continue
                    
                    # Check if item should suggest ticket creation
                    text_lower = action_item['text'].lower()
                    action_item['suggest_ticket'] = (
                        not action_item['completed'] and
                        action_item['priority'].lower() in ['high', 'medium'] and
                        any(kw in text_lower for kw in TICKET_KEYWORDS)
                    )
                    
                    all_action_items.append(action_item)
            except (json.JSONDecodeError, TypeError):
                continue
    except Exception as e:
        logger.warning(f"Could not load from meeting_summaries: {e}")
    
    # Apply filters
    if filter_status == 'completed':
        all_action_items = [i for i in all_action_items if i['completed']]
    elif filter_status == 'pending':
        all_action_items = [i for i in all_action_items if not i['completed']]
    if filter_priority != 'all':
        all_action_items = [i for i in all_action_items if i['priority'].lower() == filter_priority.lower()]
    
    # Sort items
    if sort_by == 'date_desc':
        all_action_items.sort(key=lambda x: x['meeting_date'] or '', reverse=True)
    elif sort_by == 'date_asc':
        all_action_items.sort(key=lambda x: x['meeting_date'] or '')
    elif sort_by == 'priority':
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        all_action_items.sort(key=lambda x: priority_order.get(x['priority'].lower(), 1))
    elif sort_by == 'meeting':
        all_action_items.sort(key=lambda x: x['meeting_name'])
    
    # Group items if requested
    grouped_items = None
    if group_by == 'meeting':
        grouped_items = {}
        for item in all_action_items:
            meeting_name = item['meeting_name']
            if meeting_name not in grouped_items:
                grouped_items[meeting_name] = []
            grouped_items[meeting_name].append(item)
    elif group_by == 'priority':
        grouped_items = {'High': [], 'Medium': [], 'Low': []}
        for item in all_action_items:
            priority = item['priority'].capitalize()
            if priority not in grouped_items:
                grouped_items[priority] = []
            grouped_items[priority].append(item)
    
    # Calculate stats
    stats = {
        'total': len(all_action_items),
        'completed': sum(1 for i in all_action_items if i['completed']),
        'pending': sum(1 for i in all_action_items if not i['completed']),
        'high_priority': sum(1 for i in all_action_items if i['priority'].lower() == 'high'),
        'from_supabase': sum(1 for i in all_action_items if i.get('source') == 'supabase'),
        'from_sqlite': sum(1 for i in all_action_items if i.get('source') == 'sqlite'),
    }
    
    return templates.TemplateResponse(
        "action_items.html",
        {
            "request": request,
            "action_items": all_action_items,
            "grouped_items": grouped_items,
            "all_meetings": [dict(m) for m in all_meetings],
            "stats": stats,
            "filter_status": filter_status,
            "filter_priority": filter_priority,
            "sort_by": sort_by,
            "group_by": group_by
        },
    )


@router.post("/api/action-items/{meeting_id}/{item_index}/toggle")
def toggle_action_item(meeting_id: int, item_index: int):
    """Toggle completion status of an action item."""
    # Get meeting signals using service
    meeting = meeting_service.get_meeting_by_id(str(meeting_id))
    if not meeting or not meeting.get('signals'):
        return {"success": False, "error": "Meeting not found"}

    try:
        signals = meeting['signals'] if isinstance(meeting['signals'], dict) else json.loads(meeting['signals'])
        action_items = signals.get('action_items', [])
        
        if item_index < 0 or item_index >= len(action_items):
            return {"success": False, "error": "Invalid item index"}
        
        item = action_items[item_index]
        
        # Toggle completion
        if isinstance(item, dict):
            item['completed'] = not item.get('completed', False)
        else:
            # Convert string to dict
            action_items[item_index] = {
                'text': item,
                'description': item,
                'completed': True
            }
        
        signals['action_items'] = action_items
        
        # Update using service
        update_meeting_signals(str(meeting_id), signals)
        
        return {"success": True, "completed": action_items[item_index].get('completed', True) if isinstance(action_items[item_index], dict) else True}
    except (json.JSONDecodeError, TypeError) as e:
        return {"success": False, "error": str(e)}


@router.post("/api/action-items/{meeting_id}/{item_index}/priority")
async def update_action_item_priority(meeting_id: int, item_index: int, request: Request):
    """Update the priority of an action item."""
    data = await request.json()
    new_priority = data.get('priority', 'medium')
    
    # Validate priority
    if new_priority not in ['low', 'medium', 'high']:
        return {"success": False, "error": "Invalid priority. Must be low, medium, or high"}
    
    # Get meeting using service
    meeting = meeting_service.get_meeting_by_id(str(meeting_id))
    if not meeting or not meeting.get('signals'):
        return {"success": False, "error": "Meeting not found"}

    try:
        signals = meeting['signals'] if isinstance(meeting['signals'], dict) else json.loads(meeting['signals'])
        action_items = signals.get('action_items', [])
        
        if item_index < 0 or item_index >= len(action_items):
            return {"success": False, "error": "Invalid item index"}
        
        item = action_items[item_index]
        
        # Update priority
        if isinstance(item, dict):
            item['priority'] = new_priority
        else:
            # Convert string to dict
            action_items[item_index] = {
                'text': item,
                'description': item,
                'priority': new_priority
            }
        
        signals['action_items'] = action_items

        # Update using service
        update_meeting_signals(str(meeting_id), signals)

        return {"success": True, "priority": new_priority}
    except (json.JSONDecodeError, TypeError) as e:
        return {"success": False, "error": str(e)}


@router.post("/api/action-items/add")
async def add_action_item(request: Request):
    """Add a custom action item."""
    data = await request.json()
    
    text = data.get('text')
    meeting_id = data.get('meeting_id')
    priority = data.get('priority', 'medium')
    assignee = data.get('assignee')
    due_date = data.get('due_date')
    
    if not text:
        return {"success": False, "error": "Text is required"}
    
    new_item = {
        'text': text,
        'description': text,
        'priority': priority,
        'assignee': assignee,
        'dueDate': due_date,
        'completed': False,
        'source': 'manual'
    }
    
    supabase = get_supabase_client()
    if meeting_id:
        # Add to existing meeting using service
        meeting = meeting_service.get_meeting_by_id(str(meeting_id))
        if not meeting:
            return {"success": False, "error": "Meeting not found"}

        try:
            signals = meeting.get('signals') or {}
            if isinstance(signals, str):
                signals = json.loads(signals)
        except:
            signals = {}
        
        if 'action_items' not in signals:
            signals['action_items'] = []
        
        signals['action_items'].append(new_item)

        update_meeting_signals(str(meeting_id), signals)
    else:
        # Create a "Personal Tasks" meeting if it doesn't exist using service
        personal_meeting = get_or_create_personal_meeting()
        
        if personal_meeting:
            try:
                signals = personal_meeting.get('signals') or {}
                if isinstance(signals, str):
                    signals = json.loads(signals)
            except:
                signals = {}

            if 'action_items' not in signals:
                signals['action_items'] = []

            signals['action_items'].append(new_item)

            update_meeting_signals(personal_meeting['id'], signals)
        else:
            return {"success": False, "error": "Could not create personal meeting"}
    
    return {"success": True}


@router.post("/api/action-items/create-ticket")
async def create_ticket_from_action_item(request: Request):
    """Create a ticket from an action item with context from meeting transcript."""
    data = await request.json()
    
    meeting_id = data.get('meeting_id')
    item_index = data.get('item_index')
    text = data.get('text')
    
    if not text:
        return {"success": False, "error": "Text is required"}
    
    supabase = get_supabase_client()
    
    # Generate unique ticket_id
    ticket_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
    
    # Map priority
    priority_map = {'high': 1, 'medium': 2, 'low': 3}
    
    # Get action item details and meeting context
    priority = 2  # Default medium
    description_parts = []
    meeting_name = None
    meeting_date = None
    assignee = None
    
    if meeting_id is not None:
        # Use meeting service to get meeting data
        meeting = meeting_service.get_meeting_by_id(str(meeting_id))

        if meeting:
            meeting_name = meeting.get('meeting_name')
            meeting_date = meeting.get('meeting_date')

            try:
                signals = meeting.get('signals') or {}
                if isinstance(signals, str):
                    signals = json.loads(signals)
                items = signals.get('action_items', [])
                if item_index is not None and 0 <= item_index < len(items):
                    item = items[item_index]
                    if isinstance(item, dict):
                        priority = priority_map.get(item.get('priority', 'medium').lower(), 2)
                        assignee = item.get('owner') or item.get('assignee')
            except:
                pass
            
            # Build rich description from meeting context
            description_parts.append(f"## Source\n")
            description_parts.append(f"**Meeting:** {meeting_name or f'Meeting #{meeting_id}'}")
            if meeting_date:
                description_parts.append(f"**Date:** {meeting_date}")
            if assignee:
                description_parts.append(f"**Assignee:** {assignee}")
            description_parts.append("")
            
            # Add relevant decisions if available
            try:
                signals = json.loads(meeting['signals_json'] or '{}') if isinstance(meeting.get('signals_json'), str) else (meeting.get('signals_json') or {})
                decisions = signals.get('decisions', [])
                if decisions:
                    description_parts.append("## Related Decisions")
                    for d in decisions[:3]:  # Limit to 3 most relevant
                        if isinstance(d, dict):
                            description_parts.append(f"- {d.get('text', d.get('description', str(d)))}")
                        else:
                            description_parts.append(f"- {d}")
                    description_parts.append("")
            except:
                pass
            
            # Add context from synthesized notes or AI summary
            if meeting.get('synthesized_notes'):
                # Extract a relevant section (first 500 chars)
                notes = meeting['synthesized_notes'][:500]
                if len(meeting['synthesized_notes']) > 500:
                    notes += "..."
                description_parts.append("## Meeting Context")
                description_parts.append(notes)
                description_parts.append("")
            elif meeting.get('ai_summary'):
                summary = meeting['ai_summary'][:500]
                if len(meeting['ai_summary']) > 500:
                    summary += "..."
                description_parts.append("## Meeting Summary")
                description_parts.append(summary)
                description_parts.append("")
            
            # Extract relevant transcript snippet if the action item text appears
            if meeting.get('raw_transcript'):
                transcript = meeting['raw_transcript']
                # Find where the action item text or keywords appear in transcript
                keywords = text.lower().split()[:5]  # First 5 words
                for keyword in keywords:
                    if len(keyword) > 4 and keyword in transcript.lower():
                        # Find the position and extract surrounding context
                        pos = transcript.lower().find(keyword)
                        start = max(0, pos - 200)
                        end = min(len(transcript), pos + 300)
                        snippet = transcript[start:end]
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(transcript):
                            snippet = snippet + "..."
                        description_parts.append("## Transcript Excerpt")
                        description_parts.append(f"```\n{snippet}\n```")
                        break
    
    # Fallback if no context was gathered
    if not description_parts:
        description_parts.append(f"Created from action item in meeting #{meeting_id}")
    
    description = "\n".join(description_parts)
    
    # Create ticket with rich description
    ticket_result = supabase.table("tickets").insert({
        "ticket_id": ticket_id,
        "title": text,
        "description": description,
        "priority": priority,
        "status": "todo",
        "created_at": datetime.now().isoformat()
    }).execute()
    
    row_id = ticket_result.data[0].get("id") if ticket_result.data else None
    
    # Mark action item as converted to ticket AND completed
    if meeting_id is not None and item_index is not None:
        try:
            meeting = meeting_service.get_meeting_by_id(str(meeting_id))
            
            if meeting:
                signals = meeting.get('signals') or {}
                if isinstance(signals, str):
                    signals = json.loads(signals)
                items = signals.get('action_items', [])
                if 0 <= item_index < len(items):
                    item = items[item_index]
                    if isinstance(item, dict):
                        item['converted_to_ticket'] = ticket_id
                        item['completed'] = True  # Auto-check the action item
                    else:
                        items[item_index] = {
                            'text': item,
                            'description': item,
                            'converted_to_ticket': ticket_id,
                            'completed': True  # Auto-check the action item
                        }
                    signals['action_items'] = items
                    update_meeting_signals(str(meeting_id), signals)
        except Exception:
            pass  # Non-critical
    
    return {"success": True, "ticket_id": ticket_id, "row_id": row_id}
