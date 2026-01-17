from typing import Dict, Any
from datetime import datetime

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
