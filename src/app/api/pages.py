"""
Page render routes for the SignalFlow application.

Simple template-rendering endpoints for various pages.
Extracted from main.py during Phase 2.9 refactoring.
"""
import os

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Pages"])

templates = Jinja2Templates(directory="src/app/templates")

# Expose environment variables to Jinja2 templates
templates.env.globals["env"] = os.environ


@router.get("/profile")
def profile_page(request: Request):
    """Profile router page with links to settings, career, and account."""
    user_name = os.getenv("USER_NAME", "Rowan")
    return templates.TemplateResponse("profile.html", {"request": request, "user_name": user_name})


@router.get("/settings")
def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/career")
def career_page(request: Request):
    """Career development page."""
    return templates.TemplateResponse("career.html", {"request": request})


@router.get("/notifications")
def notifications_page(request: Request):
    """Notifications inbox page."""
    return templates.TemplateResponse("notifications.html", {"request": request})


@router.get("/account")
def account_page(request: Request):
    """Account page."""
    user_name = os.getenv("USER_NAME", "Rowan")
    return templates.TemplateResponse("account.html", {"request": request, "user_name": user_name})


@router.get("/dikw")
def dikw_page(request: Request):
    """DIKW Pyramid page for knowledge management."""
    return templates.TemplateResponse("dikw.html", {"request": request})


@router.get("/knowledge-graph")
def knowledge_graph_page(request: Request):
    """Knowledge Synthesis page - AI-generated synthesis from mindmaps."""
    return templates.TemplateResponse("knowledge_synthesis.html", {"request": request})


@router.get("/reports")
async def reports_page(request: Request):
    """Render the sprint reports page."""
    return templates.TemplateResponse("reports.html", {"request": request})


@router.get("/meetings/new")
def new_meeting(request: Request):
    """New meeting form page."""
    return templates.TemplateResponse("paste_meeting.html", {"request": request})


@router.get("/documents/new")
def new_document(request: Request):
    """New document form page."""
    return templates.TemplateResponse("paste_doc.html", {"request": request})


@router.get("/meetings/load")
def load_meeting_bundle_page(request: Request):
    """Load meeting bundle form page (Pocket integration)."""
    return templates.TemplateResponse("load_meeting_bundle.html", {"request": request})
