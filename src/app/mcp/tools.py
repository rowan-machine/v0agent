from typing import Dict, Any
from datetime import datetime
from .parser import parse_meeting_summary

from ..db import connect
from ..chat.turn import run_turn

import json

from .extract import extract_structured_signals
from .cleaner import clean_meeting_text


def store_meeting_synthesis(args: Dict[str, Any]) -> Dict[str, Any]:
    # Clean the text
    cleaned_notes = clean_meeting_text(args["synthesized_notes"])
    
    # Parse and extract signals
    parsed_sections = parse_meeting_summary(cleaned_notes)
    signals = extract_structured_signals(parsed_sections)
    
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO meeting_summaries (meeting_name, synthesized_notes, meeting_date, signals_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                args["meeting_name"],
                cleaned_notes,
                args.get("meeting_date"),
                json.dumps(signals),
            ),
        )
        meeting_id = cur.lastrowid
    
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
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO docs (source, content, document_date)
            VALUES (?, ?, ?)
            """,
            (
                args["source"],
                args["content"],
                args.get("document_date"),
            ),
        )
        doc_id = cur.lastrowid
    
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
    - Optional transcript
    - Persist authoritative synthesis + structured signals    """

    meeting_name = args["meeting_name"]
    meeting_date = args.get("meeting_date")
    summary_text = args["summary_text"]
    transcript_text = args.get("transcript_text")

    # -----------------------------
    # 0. Clean the text
    # -----------------------------
    cleaned_summary = clean_meeting_text(summary_text)

    # -----------------------------
    # 1. Parse summary into sections
    # -----------------------------
    parsed_sections = parse_meeting_summary(cleaned_summary)

    # -----------------------------
    # 2. Extract structured signals
    # -----------------------------
    signals = extract_structured_signals(parsed_sections)

    # -----------------------------
    # 3. Determine synthesized notes
    # -----------------------------
    # Prefer the authoritative synthesized section if present
    synthesized_notes = (
        parsed_sections.get("Synthesized Signals (Authoritative)")
        or parsed_sections.get("Synthesized Signals")
        or cleaned_summary
    )

    # -----------------------------
    # 4. Persist to database
    # -----------------------------
    with connect() as conn:

        # ---- Insert meeting synthesis + signals
        cur = conn.execute(
            """
            INSERT INTO meeting_summaries
                (meeting_name, synthesized_notes, meeting_date, signals_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                meeting_name,
                synthesized_notes,
                meeting_date,
                json.dumps(signals),
            ),
        )

        meeting_id = cur.lastrowid

        # ---- Insert transcript as document (if provided)
        transcript_id = None
        if transcript_text:
            cur = conn.execute(
                """
                INSERT INTO docs
                    (source, content, document_date)
                VALUES (?, ?, ?)
                """,
                (
                    f"Transcript: {meeting_name}",
                    transcript_text,
                    meeting_date,
                ),
            )
            transcript_id = cur.lastrowid

    # -----------------------------
    # 5. Return structured response
    # -----------------------------
    return {
        "status": "ok",
        "meeting_id": meeting_id,
        "transcript_id": transcript_id,
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
    
    with connect() as conn:
        meetings = conn.execute(
            """
            SELECT id, meeting_name, meeting_date, signals_json
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL
            ORDER BY COALESCE(meeting_date, created_at) DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
    
    results = []
    
    for meeting in meetings:
        if not meeting["signals_json"]:
            continue
            
        signals = json.loads(meeting["signals_json"])
        
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
    
    with connect() as conn:
        meeting = conn.execute(
            """
            SELECT id, meeting_name, meeting_date, signals_json, synthesized_notes
            FROM meeting_summaries
            WHERE id = ?
            """,
            (meeting_id,)
        ).fetchone()
    
    if not meeting:
        return {"error": f"Meeting {meeting_id} not found"}
    
    signals = json.loads(meeting["signals_json"]) if meeting["signals_json"] else None
    
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
    
    with connect() as conn:
        if meeting_id:
            # Update specific meeting
            query = "SELECT id, synthesized_notes, signals_json FROM meeting_summaries WHERE id = ?"
            params = (meeting_id,)
        else:
            # Update all meetings
            if force:
                query = "SELECT id, synthesized_notes, signals_json FROM meeting_summaries"
            else:
                query = "SELECT id, synthesized_notes, signals_json FROM meeting_summaries WHERE signals_json IS NULL OR signals_json = '{}' OR signals_json = ''"
            params = ()
        
        meetings = conn.execute(query, params).fetchall()
        
        if not meetings:
            return {"status": "ok", "updated": 0, "message": "No meetings found to update"}
        
        updated_count = 0
        for meeting in meetings:
            # Clean and re-parse
            cleaned_notes = clean_meeting_text(meeting["synthesized_notes"])
            parsed_sections = parse_meeting_summary(cleaned_notes)
            signals = extract_structured_signals(parsed_sections)
            
            # Update database
            conn.execute(
                "UPDATE meeting_summaries SET signals_json = ?, synthesized_notes = ? WHERE id = ?",
                (json.dumps(signals), cleaned_notes, meeting["id"])
            )
            updated_count += 1
        
        return {
            "status": "ok",
            "updated": updated_count,
            "message": f"Successfully updated {updated_count} meeting(s)"
        }
