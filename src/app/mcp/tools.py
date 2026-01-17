from typing import Dict, Any
from datetime import datetime
from .parser import parse_meeting_summary

from ..db import connect
from ..chat.turn import run_turn


def store_meeting_synthesis(args: Dict[str, Any]) -> Dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meeting_summaries (meeting_name, synthesized_notes, meeting_date)
            VALUES (?, ?, ?)
            """,
            (
                args["meeting_name"],
                args["synthesized_notes"],
                args.get("meeting_date"),
            ),
        )
    return {"status": "ok", "stored": "meeting"}


def store_doc(args: Dict[str, Any]) -> Dict[str, Any]:
    with connect() as conn:
        conn.execute(
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
    return {"status": "ok", "stored": "doc"}


def query_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    answer, sources = run_turn(
        question=args["question"],
        source_type=args.get("source_type", "both"),
    )
    return {
        "answer": answer,
        "sources": sources,
    }

def load_meeting_bundle(args):
    parsed = parse_meeting_summary(args["summary_text"])

    meeting_name = args["meeting_name"]
    meeting_date = args.get("meeting_date")

    # --- Store authoritative synthesis ---
    synthesized = parsed.get("Synthesized Signals", args["summary_text"])

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meeting_summaries (meeting_name, synthesized_notes, meeting_date)
            VALUES (?, ?, ?)
            """,
            (meeting_name, synthesized, meeting_date),
        )

        # --- Store full transcript as document ---
        if args.get("transcript_text"):
            conn.execute(
                """
                INSERT INTO docs (source, content, document_date)
                VALUES (?, ?, ?)
                """,
                (
                    f"Transcript: {meeting_name}",
                    args["transcript_text"],
                    meeting_date,
                ),
            )

    return {
        "status": "ok",
        "stored": {
            "meeting": meeting_name,
            "sections": list(parsed.keys()),
            "transcript": bool(args.get("transcript_text")),
        },
    }