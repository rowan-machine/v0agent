from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from .db import connect

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


def date_clause(start_date, end_date, date_field="created_at"):
    clauses = []
    params = []

    if start_date:
        clauses.append(f"{date_field} >= ?")
        params.append(start_date)

    if end_date:
        clauses.append(f"{date_field} <= ?")
        params.append(end_date)

    return clauses, params


@router.get("/search")
def search(
    request: Request,
    q: str | None = Query(default=None),
    source_type: str = Query(default="docs"),  # docs | meetings | both
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = 10,
):
    results = []

    if q and len(q) >= 2:
        like = f"%{q.lower()}%"

        with connect() as conn:

            # -------- Documents --------
            if source_type in ("docs", "both"):
                date_clauses, date_params = date_clause(start_date, end_date, "document_date")
                where = ["(LOWER(content) LIKE ? OR LOWER(source) LIKE ?)"] + date_clauses

                docs = conn.execute(
                    f"""
                    SELECT id, source AS title, content, document_date, created_at
                    FROM docs
                    WHERE {' AND '.join(where)}
                    ORDER BY document_date DESC
                    LIMIT ?
                    """,
                    (like, like, *date_params, limit),
                ).fetchall()

                for d in docs:
                    results.append({
                        "type": "document",
                        "id": d["id"],
                        "title": d["title"],
                        "snippet": d["content"][:300],
                        "date": d["document_date"] or d["created_at"],
                    })

            # -------- Meetings --------
            if source_type in ("meetings", "both"):
                date_clauses, date_params = date_clause(start_date, end_date, "meeting_date")
                where = ["(LOWER(synthesized_notes) LIKE ? OR LOWER(meeting_name) LIKE ?)"] + date_clauses

                meetings = conn.execute(
                    f"""
                    SELECT id, meeting_name AS title, synthesized_notes, meeting_date, created_at
                    FROM meeting_summaries
                    WHERE {' AND '.join(where)}
                    ORDER BY meeting_date DESC
                    LIMIT ?
                    """,
                    (like, like, *date_params, limit),
                ).fetchall()

                for m in meetings:
                    results.append({
                        "type": "meeting",
                        "id": m["id"],
                        "title": m["title"],
                        "snippet": m["synthesized_notes"][:300],
                        "date": m["meeting_date"] or m["created_at"],
                    })

    results.sort(key=lambda r: r["date"], reverse=True)

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q or "",
            "results": results,
            "source_type": source_type,
            "start_date": start_date or "",
            "end_date": end_date or "",
        },
    )

