from fastapi import APIRouter, Form, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from zoneinfo import ZoneInfo

from .db import connect
from .memory.embed import embed_text, EMBED_MODEL
from .memory.vector_store import upsert_embedding

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")


@router.post("/documents/store")
def store_doc(
    source: str = Form(...),
    content: str = Form(...),
    document_date: str = Form(...)
):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO docs (source, content, document_date) VALUES (?, ?, ?)",
            (source, content, document_date),
        )
        doc_id = cur.lastrowid

    # ---- VX.2b: embedding on ingest ----
    text_for_embedding = f"{source}\n{content}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("doc", doc_id, EMBED_MODEL, vector)

    return RedirectResponse(url="/documents?success=document_created", status_code=303)


@router.get("/documents")
def list_documents(request: Request, success: str = Query(default=None)):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, source, document_date, created_at
            FROM docs
            ORDER BY COALESCE(document_date, created_at) DESC
            """
        ).fetchall()

    formatted_docs = []
    for row in rows:
        doc = dict(row)
        date_str = doc["document_date"] or doc["created_at"]
        if date_str:
            try:
                if " " in date_str:
                    dt = datetime.strptime(date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    dt_utc = dt.replace(tzinfo=ZoneInfo("UTC"))
                    dt_central = dt_utc.astimezone(ZoneInfo("America/Chicago"))
                    doc["display_date"] = dt_central.strftime("%Y-%m-%d %I:%M %p %Z")
                else:
                    doc["display_date"] = date_str
            except Exception:
                doc["display_date"] = date_str
        else:
            doc["display_date"] = ""

        formatted_docs.append(doc)

    return templates.TemplateResponse(
        "list_docs.html",
        {"request": request, "docs": formatted_docs, "success": success},
    )


@router.get("/documents/{doc_id}/edit")
def edit_document(doc_id: int, request: Request):
    with connect() as conn:
        doc = conn.execute(
            "SELECT * FROM docs WHERE id = ?",
            (doc_id,),
        ).fetchone()

    return templates.TemplateResponse(
        "edit_doc.html",
        {"request": request, "doc": doc},
    )


@router.post("/documents/{doc_id}/edit")
def update_document(
    doc_id: int,
    source: str = Form(...),
    content: str = Form(...),
    document_date: str = Form(...)
):
    with connect() as conn:
        conn.execute(
            """
            UPDATE docs
            SET source = ?, content = ?, document_date = ?
            WHERE id = ?
            """,
            (source, content, document_date, doc_id),
        )

    # ---- VX.2b: embedding on update ----
    text_for_embedding = f"{source}\n{content}"
    vector = embed_text(text_for_embedding)
    upsert_embedding("doc", doc_id, EMBED_MODEL, vector)

    return RedirectResponse(url="/documents?success=document_updated", status_code=303)


@router.post("/documents/{doc_id}/delete")
def delete_document(doc_id: int):
    with connect() as conn:
        conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
        conn.execute(
            "DELETE FROM embeddings WHERE ref_type = 'doc' AND ref_id = ?",
            (doc_id,),
        )

    return RedirectResponse(url="/documents?success=document_deleted", status_code=303)
