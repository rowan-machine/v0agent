# src/app/query.py

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from .chat.turn import run_turn

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


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
    answer, sources = run_turn(
        question=question,
        source_type=source_type,
        start_date=start_date,
        end_date=end_date,
    )

    return templates.TemplateResponse(
        "query.html",
        {
            "request": request,
            "question": question,
            "answer": answer,
            "sources": sources,
            "source_type": source_type,
            "start_date": start_date or "",
            "end_date": end_date or "",
        },
    )
