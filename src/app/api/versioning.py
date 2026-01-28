# src/app/api/versioning.py
"""
API Versioning Middleware and Headers

Implements:
- X-API-Version response header
- API version negotiation
- Deprecation warnings
- Version-based routing support
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Optional, Dict, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# -------------------------
# Version Configuration
# -------------------------

# Current API version
API_VERSION = "1.0.0"

# Minimum supported version
MIN_SUPPORTED_VERSION = "1.0.0"

# Deprecated versions (still work but emit warnings)
DEPRECATED_VERSIONS: Set[str] = set()

# Sunset versions (no longer supported)
SUNSET_VERSIONS: Set[str] = set()

# Version changelog for documentation
VERSION_CHANGELOG: Dict[str, str] = {
    "1.0.0": "Initial stable API release",
}


# -------------------------
# Version Parsing
# -------------------------

def parse_version(version_str: str) -> tuple:
    """Parse semver string to tuple for comparison."""
    try:
        parts = version_str.split(".")
        return tuple(int(p) for p in parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.
    Returns: -1 if v1 < v2, 0 if equal, 1 if v1 > v2
    """
    t1 = parse_version(v1)
    t2 = parse_version(v2)
    
    if t1 < t2:
        return -1
    elif t1 > t2:
        return 1
    return 0


def is_version_supported(version: str) -> bool:
    """Check if a version is still supported."""
    if version in SUNSET_VERSIONS:
        return False
    return compare_versions(version, MIN_SUPPORTED_VERSION) >= 0


def is_version_deprecated(version: str) -> bool:
    """Check if a version is deprecated."""
    return version in DEPRECATED_VERSIONS


# -------------------------
# Request Headers
# -------------------------

ACCEPT_VERSION_HEADER = "Accept-Version"
REQUEST_VERSION_HEADER = "X-API-Version"


def get_requested_version(request: Request) -> Optional[str]:
    """
    Extract requested API version from request headers.
    
    Checks:
    1. Accept-Version header (preferred)
    2. X-API-Version header
    3. Default to current version
    """
    # Check Accept-Version first
    accept_version = request.headers.get(ACCEPT_VERSION_HEADER)
    if accept_version:
        return accept_version.strip()
    
    # Fall back to X-API-Version
    api_version = request.headers.get(REQUEST_VERSION_HEADER)
    if api_version:
        return api_version.strip()
    
    return None


# -------------------------
# Response Headers
# -------------------------

VERSION_HEADERS = {
    "X-API-Version": API_VERSION,
    "X-API-Min-Version": MIN_SUPPORTED_VERSION,
}


def get_version_headers(
    requested_version: Optional[str] = None
) -> Dict[str, str]:
    """
    Get version-related response headers.
    
    Includes deprecation warnings if applicable.
    """
    headers = VERSION_HEADERS.copy()
    
    # Add deprecation header if needed
    if requested_version and is_version_deprecated(requested_version):
        headers["Deprecation"] = "true"
        headers["X-API-Deprecation-Notice"] = (
            f"Version {requested_version} is deprecated. "
            f"Please upgrade to version {API_VERSION}."
        )
    
    return headers


# -------------------------
# Middleware
# -------------------------

class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API versioning.
    
    - Adds version headers to all responses
    - Logs version usage for analytics
    - Rejects unsupported versions
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip non-API routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        
        # Get requested version
        requested_version = get_requested_version(request)
        
        # Check if version is supported
        if requested_version:
            if not is_version_supported(requested_version):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": {
                            "code": "UNSUPPORTED_VERSION",
                            "message": f"API version {requested_version} is no longer supported",
                            "detail": f"Please use version {MIN_SUPPORTED_VERSION} or higher"
                        }
                    },
                    headers=get_version_headers()
                )
            
            # Log deprecated version usage
            if is_version_deprecated(requested_version):
                logger.warning(
                    f"Deprecated API version requested: {requested_version}",
                    extra={
                        "path": request.url.path,
                        "version": requested_version,
                    }
                )
        
        # Store version in request state for route handlers
        request.state.api_version = requested_version or API_VERSION
        
        # Process request
        response = await call_next(request)
        
        # Add version headers to response
        version_headers = get_version_headers(requested_version)
        for key, value in version_headers.items():
            response.headers[key] = value
        
        return response


# -------------------------
# Version Info Endpoint
# -------------------------

from fastapi import APIRouter

version_router = APIRouter(prefix="/api", tags=["version"])


@version_router.get("/version")
async def get_api_version():
    """
    Get API version information.
    
    Returns:
        Current version, minimum supported version, and changelog.
    """
    return {
        "success": True,
        "data": {
            "version": API_VERSION,
            "min_supported_version": MIN_SUPPORTED_VERSION,
            "deprecated_versions": list(DEPRECATED_VERSIONS),
            "changelog": VERSION_CHANGELOG,
        }
    }


@version_router.get("/health")
async def health_check():
    """
    Health check endpoint with version info.
    """
    return {
        "status": "healthy",
        "version": API_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }
