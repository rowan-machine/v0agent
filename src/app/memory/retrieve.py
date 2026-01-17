# src/app/memory/retrieve.py

from typing import List, Dict, Any
from ..db import connect


def _date_clause(start_date, end_date, field):
    clauses = []
    params = []

    if start_date:
        clauses.append(f"{field} >= ?")
        params.append(start_date)

    if end_date:
        clauses.append(f"{field} <= ?")
        params.append(end_date)

    return clauses, params


def retrieve(
    terms: List[str],
    source_type: str = "docs",  # docs | meetings | both
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Broad, recall-oriented retrieval.
    No formatting. No LLM. No ranking tricks.
    """

    results = {"documents": [], "meetings": []}

    if not terms:
        return results

    like_clauses = " OR ".join(["LOWER(content) LIKE ?"] * len(terms))
    like_params = [f"%{t}%" for t in terms]

    with connect() as conn:

        # -------- Documents --------
        if source_type in ("docs", "both"):
            date_clauses, date_params = _date_clause(
                start_date, end_date, "document_date"
            )
            where = [f"({like_clauses})"] + date_clauses

            rows = conn.execute(
                f"""
                SELECT id, source, content, document_date, created_at
                FROM docs
                WHERE {' AND '.join(where)}
                ORDER BY COALESCE(document_date, created_at) DESC
                LIMIT ?
                """,
                (*like_params, *date_params, limit),
            ).fetchall()

            for r in rows:
                results["documents"].append(dict(r))

        # -------- Meetings --------
        if source_type in ("meetings", "both"):
            like_meetings = " OR ".join(
                ["LOWER(synthesized_notes) LIKE ?"] * len(terms)
            )
            date_clauses, date_params = _date_clause(
                start_date, end_date, "meeting_date"
            )
            where = [f"({like_meetings})"] + date_clauses

            rows = conn.execute(
                f"""
                SELECT id, meeting_name, synthesized_notes, meeting_date, created_at
                FROM meeting_summaries
                WHERE {' AND '.join(where)}
                ORDER BY COALESCE(meeting_date, created_at) DESC
                LIMIT ?
                """,
                (*like_params, *date_params, limit),
            ).fetchall()

            for r in rows:
                results["meetings"].append(dict(r))

    return results
