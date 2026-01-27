from typing import Dict, Any
from datetime import datetime
import re
from .parser import parse_meeting_summary

from ..infrastructure.supabase_client import get_supabase_client
from ..chat.turn import run_turn

import json

from .extract import extract_structured_signals
from .cleaner import clean_meeting_text


# Pocket template detection patterns - supports 30+ templates
POCKET_TEMPLATE_PATTERNS = {
    "All-Hands Meeting": [r"Company Updates", r"Team Announcements", r"Q&A Session"],
    "Sprint Retrospective": [r"What Went Well", r"What Could Be Improved", r"Action Items"],
    "Sprint Planning": [r"Sprint Goals", r"User Stories", r"Story Points", r"Capacity"],
    "Project Kickoff": [r"Project Overview", r"Stakeholders", r"Timeline", r"Deliverables"],
    "1:1 Meeting": [r"Topics Discussed", r"Feedback", r"Goals Progress", r"Next Steps"],
    "Sales Call": [r"Client Information", r"Pain Points", r"Proposed Solutions", r"Next Steps"],
    "Interview": [r"Candidate", r"Technical Assessment", r"Culture Fit", r"Recommendation"],
    "Standup": [r"Yesterday", r"Today", r"Blockers"],
    "Board Meeting": [r"Financial Report", r"Strategic Updates", r"Resolutions"],
    "Product Review": [r"Demo", r"Feedback", r"Priorities", r"Roadmap"],
    "Design Review": [r"Design Overview", r"Feedback", r"Iterations"],
    "Customer Feedback": [r"User Insights", r"Feature Requests", r"Pain Points"],
    "Brainstorming": [r"Ideas Generated", r"Top Ideas", r"Next Steps"],
    "Workshop": [r"Objectives", r"Activities", r"Outcomes"],
    "Training Session": [r"Topics Covered", r"Exercises", r"Takeaways"],
    "Incident Review": [r"Incident Summary", r"Root Cause", r"Remediation"],
    "Performance Review": [r"Achievements", r"Areas for Growth", r"Goals"],
    "Strategy Session": [r"Strategic Goals", r"OKRs", r"Initiatives"],
    "Team Sync": [r"Updates", r"Dependencies", r"Action Items"],
    "Client Meeting": [r"Agenda", r"Discussion Points", r"Follow-ups"],
    "Technical Discussion": [r"Problem Statement", r"Solutions", r"Decision"],
    "Release Planning": [r"Release Scope", r"Milestones", r"Dependencies"],
    "Budget Review": [r"Current Spend", r"Forecast", r"Recommendations"],
    "Hiring Committee": [r"Candidates", r"Evaluation", r"Decision"],
    "Vendor Meeting": [r"Vendor", r"Proposal", r"Negotiation", r"Terms"],
    "Executive Summary": [r"Key Points", r"Decisions", r"Action Items"],
    "General Meeting": [r"Agenda", r"Discussion", r"Next Steps"],
}


def _detect_pocket_template(content: str) -> str:
    """
    Detect the Pocket template type from content headings.
    
    Scans for known heading patterns and returns the best matching template name.
    Falls back to "General Meeting" if no specific template is detected.
    """
    content_lower = content.lower()
    best_match = "General Meeting"
    best_score = 0
    
    for template_name, patterns in POCKET_TEMPLATE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score += 1
        
        if score > best_score:
            best_score = score
            best_match = template_name
    
    return best_match


def store_meeting_synthesis(args: Dict[str, Any]) -> Dict[str, Any]:
    # Clean the text
    cleaned_notes = clean_meeting_text(args["synthesized_notes"])
    
    # Parse and extract signals
    parsed_sections = parse_meeting_summary(cleaned_notes)
    signals = extract_structured_signals(parsed_sections)
    
    supabase = get_supabase_client()
    result = supabase.table("meetings").insert({
        "meeting_name": args["meeting_name"],
        "synthesized_notes": cleaned_notes,
        "meeting_date": args.get("meeting_date"),
        "signals": signals
    }).execute()
    meeting_id = result.data[0]["id"] if result.data else None
    
    # Generate embeddings
    from ..memory.embed import embed_text, EMBED_MODEL
    from ..memory.vector_store import upsert_embedding
    
    text_for_embedding = f"{args['meeting_name']}\n{cleaned_notes}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("meeting", meeting_id, EMBED_MODEL, vector)
    
    return {
        "status": "ok",
        "stored": "meeting",
        "meeting_id": meeting_id,
        "signals_extracted": len([item for sublist in signals.values() if isinstance(sublist, list) for item in sublist])
    }


def store_doc(args: Dict[str, Any]) -> Dict[str, Any]:
    supabase = get_supabase_client()
    result = supabase.table("documents").insert({
        "source": args["source"],
        "content": args["content"],
        "document_date": args.get("document_date")
    }).execute()
    doc_id = result.data[0]["id"] if result.data else None
    
    # Generate embeddings
    from ..memory.embed import embed_text, EMBED_MODEL
    from ..memory.vector_store import upsert_embedding
    
    text_for_embedding = f"{args['source']}\n{args['content']}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("doc", doc_id, EMBED_MODEL, vector)
    
    return {"status": "ok", "stored": "doc", "doc_id": doc_id}


def query_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    answer, sources = run_turn(
        question=args["question"],
        source_type=args.get("source_type", "both"),
    )
    return {
        "answer": answer,
        "sources": sources,
    }

def load_meeting_bundle(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load a full meeting bundle:
    - Structured summary (your canonical format)
    - Optional Pocket AI summary (creates document for signal extraction)
    - Optional transcript
    - Persist authoritative synthesis + structured signals
    - Auto-generates embeddings for meeting, transcript, and Pocket summary
    - Idempotent: skips if pocket_recording_id OR (meeting_name, meeting_date) already exists
    
    Pocket AI Summary Handling:
    - Detects Pocket template type from heading patterns
    - Creates a separate document with "Pocket Summary:" prefix
    - Supports 30+ template formats including:
      - All-Hands Meeting, Sprint Retrospective, Project Kickoff
      - 1:1 Meeting, Sales Call, Interview, Standup
      - Board Meeting, Product Review, etc.
    """

    meeting_name = args["meeting_name"]
    meeting_date = args.get("meeting_date")
    summary_text = args["summary_text"]
    transcript_text = args.get("transcript_text")
    pocket_ai_summary = args.get("pocket_ai_summary")
    pocket_mind_map = args.get("pocket_mind_map")
    pocket_recording_id = args.get("pocket_recording_id")  # Unique ID from Pocket

    # -----------------------------
    # 0. Idempotency check - prefer pocket_recording_id if available
    # -----------------------------
    
    # Check Supabase first (primary)
    from ..services import meeting_service
    
    if pocket_recording_id:
        # Check by unique Pocket recording ID first
        existing_by_pocket = meeting_service.get_meeting_by_pocket_recording_id(pocket_recording_id)
        if existing_by_pocket:
            return {
                "status": "skipped",
                "reason": "duplicate",
                "existing_meeting_id": existing_by_pocket.get("id"),
                "message": f"Meeting with Pocket recording '{pocket_recording_id}' already exists"
            }
    
    # Fallback: check by name + date (for non-Pocket imports)
    supabase = get_supabase_client()
    result = supabase.table("meetings").select("id").eq("meeting_name", meeting_name).execute()
    # Filter by date in code since NULL handling is tricky in Supabase
    existing_meetings = result.data or []
    for existing in existing_meetings:
        # Check if dates match (both None or equal)
        existing_check = supabase.table("meetings").select("id, meeting_date").eq("id", existing["id"]).execute()
        if existing_check.data:
            existing_date = existing_check.data[0].get("meeting_date")
            if existing_date == meeting_date or (existing_date is None and meeting_date is None):
                return {
                    "status": "skipped",
                    "reason": "duplicate",
                    "existing_meeting_id": existing["id"],
                    "message": f"Meeting '{meeting_name}' on {meeting_date or 'no date'} already exists"
                }

    # -----------------------------
    # 1. Clean the text
    # -----------------------------
    cleaned_summary = clean_meeting_text(summary_text)

    # -----------------------------
    # 2. Parse summary into sections
    # -----------------------------
    parsed_sections = parse_meeting_summary(cleaned_summary)

    # -----------------------------
    # 3. Extract structured signals
    # -----------------------------
    signals = extract_structured_signals(parsed_sections)

    # -----------------------------
    # 4. Determine synthesized notes
    # -----------------------------
    # Prefer the authoritative synthesized section if present
    synthesized_notes = (
        parsed_sections.get("Synthesized Signals (Authoritative)")
        or parsed_sections.get("Synthesized Signals")
        or cleaned_summary
    )

    # -----------------------------
    # 5. Persist to database (SQLite + Supabase dual-write)
    # -----------------------------
    
    # Detect Pocket template type if pocket summary provided
    pocket_template = None
    if pocket_ai_summary and pocket_ai_summary.strip():
        pocket_template = _detect_pocket_template(pocket_ai_summary)
    
    # ----- 5a. Insert into Supabase (primary) -----
    from ..services import meeting_service, document_service
    
    supabase_meeting_data = {
        "meeting_name": str(meeting_name).strip(),  # Ensure it's a string
        "synthesized_notes": str(synthesized_notes).strip() if synthesized_notes else "",  # Ensure it's a string
        "meeting_date": meeting_date,
        "signals": signals,
        "raw_text": str(transcript_text).strip() if transcript_text else "",  # Ensure it's a string
        "pocket_recording_id": pocket_recording_id,  # Unique ID for idempotency
        "pocket_ai_summary": str(pocket_ai_summary).strip() if pocket_ai_summary else None,
        "pocket_mind_map": str(pocket_mind_map).strip() if pocket_mind_map else None,
        "pocket_template_type": pocket_template,  # Detected template type
        "import_source": "pocket" if pocket_recording_id else "manual",
    }
    
    supabase_meeting = meeting_service.create_meeting(supabase_meeting_data)
    supabase_meeting_id = supabase_meeting.get("id") if supabase_meeting else None
    
    # Insert transcript document into Supabase
    supabase_transcript_id = None
    if supabase_meeting_id and transcript_text:
        transcript_doc = document_service.create_document({
            "meeting_id": supabase_meeting_id,
            "source": f"Transcript: {meeting_name}",
            "content": transcript_text,
            "document_date": meeting_date,
        })
        supabase_transcript_id = transcript_doc.get("id") if transcript_doc else None
    
    # Insert Pocket AI summary document into Supabase
    supabase_pocket_id = None
    if supabase_meeting_id and pocket_ai_summary and pocket_ai_summary.strip():
        pocket_source = f"Pocket Summary ({pocket_template}): {meeting_name}"
        pocket_doc = document_service.create_document({
            "meeting_id": supabase_meeting_id,
            "source": pocket_source,
            "content": pocket_ai_summary.strip(),
            "document_date": meeting_date,
        })
        supabase_pocket_id = pocket_doc.get("id") if pocket_doc else None
    
    # ----- 5b. Use Supabase IDs for embeddings (no SQLite dual-write) -----
    meeting_id = supabase_meeting_id
    transcript_id = supabase_transcript_id
    pocket_summary_id = supabase_pocket_id

    # -----------------------------
    # 6. Generate embeddings immediately
    # -----------------------------
    from ..memory.embed import embed_text, EMBED_MODEL
    from ..memory.vector_store import upsert_embedding
    
    # Embed meeting
    meeting_embed_text = f"{meeting_name}\n{synthesized_notes}"
    meeting_vector = embed_text(meeting_embed_text)
    upsert_embedding("meeting", meeting_id, EMBED_MODEL, meeting_vector)
    
    # Embed transcript if provided
    if transcript_id and transcript_text:
        transcript_embed_text = f"Transcript: {meeting_name}\n{transcript_text[:8000]}"
        transcript_vector = embed_text(transcript_embed_text)
        upsert_embedding("doc", transcript_id, EMBED_MODEL, transcript_vector)
    
    # Embed Pocket AI summary if provided
    if pocket_summary_id and pocket_ai_summary:
        pocket_embed_text = f"Pocket Summary: {meeting_name}\n{pocket_ai_summary[:8000]}"
        pocket_vector = embed_text(pocket_embed_text)
        upsert_embedding("doc", pocket_summary_id, EMBED_MODEL, pocket_vector)

    # -----------------------------
    # 7. Return structured response
    # -----------------------------
    return {
        "status": "ok",
        "meeting_id": supabase_meeting_id,
        "transcript_id": supabase_transcript_id,
        "pocket_summary_id": supabase_pocket_id,
        "embedded": True,
        "signals_extracted": {
            "decisions": len(signals.get("decisions", [])),
            "action_items": len(signals.get("action_items", [])),
            "blockers": len(signals.get("blockers", [])),
            "risks": len(signals.get("risks", [])),
            "ideas": len(signals.get("ideas", [])),
        },
    }


def collect_meeting_signals(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect signals of a specific type across all meetings.
    
    Args:
        signal_type: One of ["decisions", "action_items", "blockers", "risks", "ideas", "all"]
        limit: Maximum number of meetings to query (default: 50)
    """
    signal_type = args.get("signal_type", "all")
    limit = args.get("limit", 50)
    
    valid_types = ["decisions", "action_items", "blockers", "risks", "ideas", "key_signals", "all"]
    if signal_type not in valid_types:
        return {
            "error": f"Invalid signal_type. Must be one of: {', '.join(valid_types)}"
        }
    
    supabase = get_supabase_client()
    result = supabase.table("meetings").select("id, meeting_name, meeting_date, signals").neq("signals", None).order("meeting_date", desc=True).limit(limit).execute()
    meetings = result.data or []

    results = []

    for meeting in meetings:
        if not meeting.get("signals"):
            continue

        signals = meeting["signals"] if isinstance(meeting["signals"], dict) else json.loads(meeting["signals"])
        if signal_type == "all":
            # Return all signal types
            meeting_signals = {
                "meeting_id": meeting["id"],
                "meeting_name": meeting["meeting_name"],
                "meeting_date": meeting["meeting_date"],
                "signals": signals
            }
            results.append(meeting_signals)
        else:
            # Return specific signal type
            signal_items = signals.get(signal_type, [])
            if signal_items:
                # Handle both list and string types
                if isinstance(signal_items, list) and len(signal_items) > 0:
                    meeting_signals = {
                        "meeting_id": meeting["id"],
                        "meeting_name": meeting["meeting_name"],
                        "meeting_date": meeting["meeting_date"],
                        signal_type: signal_items
                    }
                    results.append(meeting_signals)
                elif isinstance(signal_items, str) and signal_items.strip():
                    meeting_signals = {
                        "meeting_id": meeting["id"],
                        "meeting_name": meeting["meeting_name"],
                        "meeting_date": meeting["meeting_date"],
                        signal_type: signal_items
                    }
                    results.append(meeting_signals)
    
    return {
        "signal_type": signal_type,
        "count": len(results),
        "meetings": results
    }


def get_meeting_signals(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get signals for a specific meeting by ID.
    
    Args:
        meeting_id: The ID of the meeting to retrieve signals for
    """
    meeting_id = args.get("meeting_id")
    
    if not meeting_id:
        return {"error": "meeting_id is required"}
    
    supabase = get_supabase_client()
    result = supabase.table("meetings").select("id, meeting_name, meeting_date, signals, synthesized_notes").eq("id", meeting_id).execute()
    meetings = result.data or []

    if not meetings:
        return {"error": f"Meeting {meeting_id} not found"}

    meeting = meetings[0]
    signals_data = meeting.get("signals")
    signals = signals_data if isinstance(signals_data, dict) else json.loads(signals_data) if signals_data else None
    return {
        "meeting_id": meeting["id"],
        "meeting_name": meeting["meeting_name"],
        "meeting_date": meeting["meeting_date"],
        "signals": signals,
        "has_signals": signals is not None
    }


def update_meeting_signals(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Re-parse and update signals for existing meetings.
    
    Args:
        meeting_id: Optional - specific meeting to update. If not provided, updates all meetings.
        force: Whether to re-parse even if signals already exist (default: False)
    """
    meeting_id = args.get("meeting_id")
    force = args.get("force", False)
    
    supabase = get_supabase_client()
    if meeting_id:
        # Update specific meeting
        result = supabase.table("meetings").select("id, synthesized_notes, signals").eq("id", meeting_id).execute()
    else:
        # Update all meetings
        if force:
            result = supabase.table("meetings").select("id, synthesized_notes, signals").execute()
        else:
            result = supabase.table("meetings").select("id, synthesized_notes, signals").or_("signals.is.null,signals.eq.{},signals.eq.").execute()
    
    meetings = result.data or []
    
    if not meetings:
        return {"status": "ok", "updated": 0, "message": "No meetings found to update"}
    
    updated_count = 0
    for meeting in meetings:
        # Clean and re-parse
        cleaned_notes = clean_meeting_text(meeting.get("synthesized_notes") or "")
        parsed_sections = parse_meeting_summary(cleaned_notes)
        signals = extract_structured_signals(parsed_sections)
        
        # Update database
        supabase.table("meetings").update({
            "signals": signals,
            "synthesized_notes": cleaned_notes
        }).eq("id", meeting["id"]).execute()
        updated_count += 1
    
    return {
        "status": "ok",
        "updated": updated_count,
        "message": f"Successfully updated {updated_count} meeting(s)"
    }


def export_meeting_signals(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Export meeting signals for a date range or all meetings.
    Useful for career agents, sprint retros, status summaries.
    
    Args:
        signal_types: List of types to include (default: all)
        start_date: Filter meetings from this date (YYYY-MM-DD)
        end_date: Filter meetings until this date (YYYY-MM-DD)
        limit: Maximum meetings to return (default: 100)
        format: "full" (all data) or "compact" (signals only)
    """
    signal_types = args.get("signal_types", ["decisions", "action_items", "blockers", "risks", "ideas"])
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    limit = args.get("limit", 100)
    output_format = args.get("format", "full")
    
    # Build query with date filters
    supabase = get_supabase_client()
    query = supabase.table("meetings").select("id, meeting_name, meeting_date, signals").neq("signals", None).neq("signals", "{}")
    
    if start_date:
        query = query.gte("meeting_date", start_date)
    if end_date:
        query = query.lte("meeting_date", end_date)
    
    result = query.order("meeting_date", desc=True).limit(limit).execute()
    meetings = result.data or []
    
    # Aggregate signals
    aggregated = {stype: [] for stype in signal_types}
    meeting_exports = []
    
    for meeting in meetings:
        if not meeting["signals"]:
            continue
        
        try:
            signals_data = meeting.get("signals")
            signals = signals_data if isinstance(signals_data, dict) else json.loads(signals_data)
        except:
            continue
        
        meeting_data = {
            "meeting_id": meeting["id"],
            "meeting_name": meeting["meeting_name"],
            "meeting_date": meeting["meeting_date"],
            "signals": {}
        }
        
        for stype in signal_types:
            items = signals.get(stype, [])
            if isinstance(items, str):
                items = [items] if items.strip() else []
            
            if items:
                meeting_data["signals"][stype] = items
                # Add to aggregated with meeting context
                for item in items:
                    aggregated[stype].append({
                        "meeting_name": meeting["meeting_name"],
                        "meeting_date": meeting["meeting_date"],
                        "text": item
                    })
        
        if meeting_data["signals"]:
            meeting_exports.append(meeting_data)
    
    # Build response
    response = {
        "export_date": datetime.now().isoformat(),
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "signal_types": signal_types,
        },
        "summary": {
            "total_meetings": len(meeting_exports),
            "signal_counts": {stype: len(items) for stype, items in aggregated.items()}
        }
    }
    
    if output_format == "full":
        response["meetings"] = meeting_exports
        response["aggregated"] = aggregated
    else:
        # Compact: just aggregated signals
        response["signals"] = aggregated
    
    return response


def draft_summary_from_transcript(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a draft meeting summary from a transcript using LLM.
    User reviews/edits before loading via load_meeting_bundle.
    
    Uses GPT-4o for best extraction quality on long transcripts.
    
    Args:
        transcript: The meeting transcript text
        meeting_name: Name of the meeting
        focus_areas: Optional list of areas to emphasize
    """
    from ..llm import ask
    
    transcript = args.get("transcript", "")
    meeting_name = args.get("meeting_name", "Meeting")
    focus_areas = args.get("focus_areas", [])
    
    if not transcript or len(transcript) < 100:
        return {"error": "Transcript too short. Provide at least 100 characters."}
    
    # GPT-4o supports 128K context - use larger chunks
    max_chars = 100000
    if len(transcript) > max_chars:
        half = max_chars // 2
        transcript = transcript[:half] + "\n\n[... middle section omitted for length ...]\n\n" + transcript[-half:]
    
    focus_instruction = ""
    if focus_areas:
        focus_instruction = f"\nPay special attention to these areas: {', '.join(focus_areas)}"
    
    prompt = f"""Analyze this meeting transcript and generate a structured summary in the exact format below.

Meeting: {meeting_name}
{focus_instruction}

Generate the summary in this EXACT format (keep all headers and structure):

📖 Summarized Notes

**Work Identified (candidates, not tasks)**
- [List specific work items, tickets, or tasks mentioned - these are candidates to track, not commitments]

### Outcomes
- [Key outcomes and agreements reached in the meeting]

## Context
- [Meeting type, purpose, participants context, and background information]

## Key Signal (Problem)
- [The core problem, challenge, or focus area being addressed]

## Notes
- [Detailed notes organized by topic or ticket number (e.g., DEV-8095, DEV-8101)]
- Include specifics: story points, assignees, technical details discussed

### Synthesized Signals (Authoritative)
**Decision:**
- [List each decision made with context]

**Action items:**
- [List who will do what - format: "Person will action"]

**Blocked:**
- [List any blockers or dependencies mentioned]

### Risks / Open Questions
- [Unresolved items, architectural questions, things needing follow-up]

### Screenshots / Photos
(empty — artifacts pasted separately)

### Notes (raw)
(empty — transcript / raw notes supplied separately)

### Commitments / Ideas
**Commitments:**
- [Explicit commitments made by specific people]

**Ideas:**
- [Ideas proposed for future consideration]

---
TRANSCRIPT:
{transcript}
"""
    
    try:
        # Use GPT-4o for best extraction quality (configured in model_routing.yaml)
        draft = ask(prompt, model="gpt-4o")
        
        return {
            "status": "draft_generated",
            "meeting_name": meeting_name,
            "draft_summary": draft,
            "model_used": "gpt-4o",
            "instructions": "Review and edit this draft, then use load_meeting_bundle to save it."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
