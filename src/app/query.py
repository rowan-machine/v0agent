import re
from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from .db import connect
from .llm import answer as llm_answer

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

MAX_CONTEXT = 6


def extract_terms(text: str) -> list[str]:
    return [
        w for w in re.findall(r"[a-zA-Z]+", text.lower())
        if len(w) > 2
    ]


def date_clause(start_date, end_date):
    clauses = []
    params = []

    if start_date:
        clauses.append("created_at >= ?")
        params.append(start_date)

    if end_date:
        clauses.append("created_at <= ?")
        params.append(end_date)

    return clauses, params


def retrieve(question, source_type, start_date, end_date):
    terms = extract_terms(question)
    if not terms:
        return [], []

    likes = " OR ".join(["LOWER(content) LIKE ?"] * len(terms))
    params = [f"%{t}%" for t in terms]

    blocks = []
    sources = []

    with connect() as conn:

        # -------- Documents --------
        if source_type in ("docs", "both"):
            date_clauses, date_params = date_clause(start_date, end_date)
            where = [f"({likes})"] + date_clauses

            docs = conn.execute(
                f"""
                SELECT id, source, content
                FROM docs
                WHERE {' AND '.join(where)}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, *date_params, MAX_CONTEXT),
            ).fetchall()

            for d in docs:
                idx = len(blocks) + 1
                blocks.append(f"[{idx}] (Document: {d['source']})\n{d['content']}")
                sources.append({
                    "type": "document",
                    "id": d["id"],
                    "label": d["source"],
                })

        remaining = MAX_CONTEXT - len(blocks)

        # -------- Meetings --------
        if remaining > 0 and source_type in ("meetings", "both"):
            likes = " OR ".join(["LOWER(synthesized_notes) LIKE ?"] * len(terms))
            date_clauses, date_params = date_clause(start_date, end_date)
            where = [f"({likes})"] + date_clauses

            meetings = conn.execute(
                f"""
                SELECT id, meeting_name, synthesized_notes
                FROM meeting_summaries
                WHERE {' AND '.join(where)}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, *date_params, remaining),
            ).fetchall()

            for m in meetings:
                idx = len(blocks) + 1
                blocks.append(f"[{idx}] (Meeting: {m['meeting_name']})\n{m['synthesized_notes']}")
                sources.append({
                    "type": "meeting",
                    "id": m["id"],
                    "label": m["meeting_name"],
                })

    return blocks, sources


@router.get("/query")
def query_page(request: Request):
    return templates.TemplateResponse(
        "query.html",
        {
            "request": request,
            "question": "",
            "answer": None,
            "sources": [],
            "source_type": "docs",
            "start_date": "",
            "end_date": "",
        },
    )


@router.post("/query")
def run_query(
    request: Request,
    question: str = Form(...),
    source_type: str = Form(default="docs"),
    start_date: str | None = Form(default=None),
    end_date: str | None = Form(default=None),
):
    blocks, sources = retrieve(question, source_type, start_date, end_date)

    if not blocks:
        return templates.TemplateResponse(
            "query.html",
            {
                "request": request,
                "question": question,
                "answer": "I don’t have enough information in the provided sources.",
                "sources": [],
                "source_type": source_type,
                "start_date": start_date or "",
                "end_date": end_date or "",
            },
        )

    answer_text = llm_answer(question, blocks)

    return templates.TemplateResponse(
        "query.html",
        {
            "request": request,
            "question": question,
            "answer": answer_text,
            "sources": sources,
            "source_type": source_type,
            "start_date": start_date or "",
            "end_date": end_date or "",
        },
    )
