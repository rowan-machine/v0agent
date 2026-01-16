from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .db import init_db
from .meetings import router as meetings_router
from .documents import router as documents_router
from .search import router as search_router
from .query import router as query_router

app = FastAPI(title="V2.0 Memory Intake + Search")

templates = Jinja2Templates(directory="src/app/templates")


@app.on_event("startup")
def startup():
    init_db()


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


# -------------------------
# Routers
# -------------------------

app.include_router(meetings_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(query_router)