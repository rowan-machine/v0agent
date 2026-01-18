# src/app/auth.py
"""Authentication middleware for SignalFlow."""

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import secrets
import os
from datetime import datetime, timedelta

# Session storage (in production, use Redis or database)
_sessions = {}

SESSION_DURATION_HOURS = 24 * 7  # 1 week


def get_secret_key():
    return os.environ.get("SECRET_KEY", "signalflow-default-secret")


def get_auth_password():
    return os.environ.get("AUTH_PASSWORD", "signalflow")


def hash_password(password: str) -> str:
    """Hash password with salt."""
    salt = get_secret_key()
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def create_session(user_agent: str = "") -> str:
    """Create a new session and return token."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "created": datetime.now(),
        "user_agent": user_agent,
        "last_active": datetime.now(),
    }
    return token


def validate_session(token: str) -> bool:
    """Check if session is valid."""
    if not token or token not in _sessions:
        return False
    
    session = _sessions[token]
    expiry = session["created"] + timedelta(hours=SESSION_DURATION_HOURS)
    
    if datetime.now() > expiry:
        del _sessions[token]
        return False
    
    # Update last active
    session["last_active"] = datetime.now()
    return True


def destroy_session(token: str):
    """Logout - destroy session."""
    if token in _sessions:
        del _sessions[token]


# Public routes that don't need auth
PUBLIC_ROUTES = [
    "/login",
    "/auth/login",
    "/static",
    "/favicon.ico",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to check authentication on all routes."""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Allow public routes
        for route in PUBLIC_ROUTES:
            if path.startswith(route):
                return await call_next(request)
        
        # Check if auth is disabled
        from .db import connect
        try:
            with connect() as conn:
                row = conn.execute("SELECT value FROM settings WHERE key = 'auth_enabled'").fetchone()
                if row and row["value"].lower() in ('false', '0', 'no'):
                    # Auth disabled - allow all requests
                    return await call_next(request)
        except:
            pass  # If settings table doesn't exist yet, continue with auth check
        
        # Check for bypass token in query params or header
        bypass_token = request.query_params.get("token") or request.headers.get("X-Auth-Token")
        expected_bypass = os.environ.get("BYPASS_TOKEN")
        if bypass_token and expected_bypass and bypass_token == expected_bypass:
            # Valid bypass token - create a temporary session
            request.state.session_token = "bypass"
            return await call_next(request)
        
        # Check session cookie
        session_token = request.cookies.get("signalflow_session")
        
        if not validate_session(session_token):
            # API routes return 401
            if path.startswith("/api/") or path.startswith("/mcp/"):
                return HTMLResponse(
                    content='{"error": "Unauthorized"}',
                    status_code=401,
                    media_type="application/json"
                )
            # Web routes redirect to login
            return RedirectResponse(url=f"/login?next={path}", status_code=302)
        
        # Add session info to request state
        request.state.session_token = session_token
        
        response = await call_next(request)
        return response


def get_login_page(error: str = None, next_url: str = "/"):
    """Return login page HTML."""
    error_html = f'<div class="error">{error}</div>' if error else ''
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hare Krishna - Login</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }}
        
        .login-container {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 24px;
            padding: 3rem;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }}
        
        .logo {{
            text-align: center;
            margin-bottom: 2rem;
        }}
        
        .logo-icon {{
            font-size: 3rem;
            margin-bottom: 0.5rem;
        }}
        
        .logo h1 {{
            font-size: 1.75rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .logo p {{
            color: #6b7280;
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }}
        
        .error {{
            background: #fee2e2;
            color: #dc2626;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            font-size: 0.9rem;
        }}
        
        .form-group {{
            margin-bottom: 1.5rem;
        }}
        
        label {{
            display: block;
            font-weight: 500;
            color: #374151;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
        }}
        
        input[type="password"] {{
            width: 100%;
            padding: 0.875rem 1rem;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.2s;
        }}
        
        input[type="password"]:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        
        button {{
            width: 100%;
            padding: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }}
        
        .footer {{
            text-align: center;
            margin-top: 2rem;
            color: #9ca3af;
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <div class="logo-icon">🪷</div>
            <h1>Hare Krishna</h1>
            <p>Intelligence Platform</p>
        </div>
        
        {error_html}
        
        <form method="POST" action="/auth/login">
            <input type="hidden" name="next" value="{next_url}">
            <div class="form-group">
                <label for="password">Access Code</label>
                <input type="password" id="password" name="password" 
                       placeholder="Enter your access code" required autofocus>
            </div>
            <button type="submit">Sign In</button>
        </form>
        
        <div class="footer">
            Secure access · Data encrypted at rest
        </div>
    </div>
</body>
</html>'''
