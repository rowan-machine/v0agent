from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .db import init_db
from .meetings import router as meetings_router
from .documents import router as documents_router
from .search import router as search_router
from .query import router as query_router
from .chat.models import init_chat_tables
from .api.chat import router as chat_router
from .api.mcp import router as mcp_router
from .mcp.registry import TOOL_REGISTRY

app = FastAPI(title="V2.0 Memory Intake + Search")

templates = Jinja2Templates(directory="src/app/templates")


@app.on_event("startup")
def startup():
    init_db()
    init_chat_tables()

# -------------------------
# Root + Navigation Entrypoints
# -------------------------

@app.get("/")
def root():
    # Primary workflow entry
    return RedirectResponse(url="/meetings/new")


@app.get("/meetings/new")
def new_meeting(request: Request):
    return templates.TemplateResponse(
        "paste_meeting.html",
        {"request": request},
    )


@app.get("/documents/new")
def new_document(request: Request):
    return templates.TemplateResponse(
        "paste_doc.html",
        {"request": request},
    )

@app.get("/meetings/load")
def load_meeting_bundle_page(request: Request):
    return templates.TemplateResponse(
        "load_meeting_bundle.html",
        {"request": request},
    )

@app.post("/meetings/load")
def load_meeting_bundle_ui(
    meeting_name: str = Form(...),
    meeting_date: str = Form(None),
    summary_text: str = Form(...),
    transcript_text: str = Form(None),
):
    tool = TOOL_REGISTRY["load_meeting_bundle"]

    tool({
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "summary_text": summary_text,
        "transcript_text": transcript_text,
        "format": "plain",
    })

    return RedirectResponse(
        url="/meetings?success=meeting_loaded",
        status_code=303,
    )

# -------------------------
# Routers
# -------------------------

app.include_router(meetings_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(query_router)
app.include_router(chat_router)
app.include_router(mcp_router)