"""
Authentication routes for the SignalFlow application.

Handles login, logout, and session management.
Extracted from main.py during Phase 2.9 refactoring.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse

from ..auth import (
    get_login_page,
    create_session,
    destroy_session,
    get_auth_password,
    hash_password,
)

router = APIRouter(tags=["Authentication"])


@router.get("/login")
def login_page(request: Request, error: str = None, next: str = "/"):
    """Show login page."""
    return HTMLResponse(get_login_page(error=error, next_url=next))


@router.post("/auth/login")
async def do_login(request: Request, password: str = Form(...), next: str = Form("/")):
    """Process login form submission."""
    expected_hash = hash_password(get_auth_password())
    provided_hash = hash_password(password)

    if provided_hash != expected_hash:
        return HTMLResponse(get_login_page(error="Invalid access code", next_url=next))

    # Create session
    user_agent = request.headers.get("user-agent", "")
    token = create_session(user_agent)

    response = RedirectResponse(url=next, status_code=302)
    response.set_cookie(
        key="signalflow_session",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 1 week
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout(request: Request):
    """Logout and destroy session."""
    token = request.cookies.get("signalflow_session")
    if token:
        destroy_session(token)

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("signalflow_session")
    return response
