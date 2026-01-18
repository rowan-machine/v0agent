# src/app/api/settings.py

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ..db import connect

router = APIRouter()


def get_auth_enabled() -> bool:
    """Check if authentication is enabled."""
    try:
        with connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'auth_enabled'").fetchone()
            if row:
                return row["value"].lower() in ('true', '1', 'yes')
    except:
        pass
    return True  # Default: auth enabled


@router.get("/api/settings/auth")
async def get_auth_setting():
    """Get authentication enabled/disabled status."""
    return JSONResponse({"enabled": get_auth_enabled()})


@router.post("/api/settings/auth")
async def set_auth_setting(request: Request):
    """Toggle authentication on/off."""
    try:
        data = await request.json()
        enabled = data.get("enabled", True)
        
        with connect() as conn:
            conn.execute("""
                INSERT INTO settings (key, value) 
                VALUES ('auth_enabled', ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')
            """, (str(enabled), str(enabled)))
        
        return JSONResponse({"status": "ok", "enabled": enabled})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.get("/api/settings/model")
async def get_model_setting():
    """Get current AI model setting."""
    try:
        with connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'ai_model'").fetchone()
            if row:
                return JSONResponse({"model": row["value"]})
            return JSONResponse({"model": "gpt-4o-mini"})
    except Exception as e:
        return JSONResponse({"model": "gpt-4o-mini"})


@router.post("/api/settings/model")
async def set_model_setting(request: Request):
    """Set AI model setting."""
    try:
        data = await request.json()
        model = data.get("model", "gpt-4o-mini")
        
        with connect() as conn:
            conn.execute("""
                INSERT INTO settings (key, value) 
                VALUES ('ai_model', ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')
            """, (model, model))
        
        return JSONResponse({"status": "ok", "model": model})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
