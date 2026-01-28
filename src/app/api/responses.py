# src/app/api/responses.py
"""
Standardized API Response Models

Provides consistent response envelopes for all API endpoints:
- Standard success/error structure
- Pagination metadata
- Error code standards
- Response helpers for common patterns

All API endpoints should use these models for consistency.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, TypeVar, Generic
from datetime import datetime
from enum import Enum


# -------------------------
# Error Codes
# -------------------------

class ErrorCode(str, Enum):
    """
    Standardized error codes for API responses.
    Format: {CATEGORY}_{SPECIFIC_ERROR}
    """
    # Validation errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    
    # Authentication/Authorization (401/403)
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    
    # Resource errors (404/409)
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"
    GONE = "GONE"
    
    # Rate limiting (429)
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    
    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    AI_SERVICE_ERROR = "AI_SERVICE_ERROR"
    
    # Domain-specific errors
    MEETING_PROCESSING_ERROR = "MEETING_PROCESSING_ERROR"
    SIGNAL_EXTRACTION_FAILED = "SIGNAL_EXTRACTION_FAILED"
    EMBEDDING_GENERATION_FAILED = "EMBEDDING_GENERATION_FAILED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"


# -------------------------
# HTTP Status Mappings
# -------------------------

ERROR_CODE_TO_HTTP_STATUS: Dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.INVALID_INPUT: 400,
    ErrorCode.MISSING_REQUIRED_FIELD: 400,
    ErrorCode.INVALID_FORMAT: 400,
    
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.AUTH_INVALID: 401,
    ErrorCode.AUTH_EXPIRED: 401,
    ErrorCode.PERMISSION_DENIED: 403,
    
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ALREADY_EXISTS: 409,
    ErrorCode.CONFLICT: 409,
    ErrorCode.GONE: 410,
    
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.QUOTA_EXCEEDED: 429,
    
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.EXTERNAL_SERVICE_ERROR: 502,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.AI_SERVICE_ERROR: 500,
    
    ErrorCode.MEETING_PROCESSING_ERROR: 422,
    ErrorCode.SIGNAL_EXTRACTION_FAILED: 422,
    ErrorCode.EMBEDDING_GENERATION_FAILED: 500,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_FORMAT: 415,
}


def get_http_status(error_code: ErrorCode) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_CODE_TO_HTTP_STATUS.get(error_code, 500)


# -------------------------
# Response Metadata
# -------------------------

class ResponseMeta(BaseModel):
    """Metadata included in all API responses."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    version: str = "1.0"


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool = False
    has_prev: bool = False
    
    @classmethod
    def from_offset(
        cls, 
        total: int, 
        skip: int = 0, 
        limit: int = 20
    ) -> "PaginationMeta":
        """Create pagination meta from offset-based params."""
        page = (skip // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        return cls(
            page=page,
            page_size=limit,
            total_items=total,
            total_pages=total_pages,
            has_next=skip + limit < total,
            has_prev=skip > 0,
        )


# -------------------------
# Error Details
# -------------------------

class FieldError(BaseModel):
    """Error for a specific field in validation."""
    field: str
    message: str
    code: str = "invalid"


class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: ErrorCode
    message: str
    detail: Optional[str] = None
    field_errors: List[FieldError] = []
    trace_id: Optional[str] = None  # For server errors


# -------------------------
# Generic Response Models
# -------------------------

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.
    
    All successful responses use this structure:
    {
        "success": true,
        "data": { ... },
        "meta": { "timestamp": "...", "version": "1.0" }
    }
    """
    success: bool = True
    data: Optional[T] = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class APIListResponse(BaseModel, Generic[T]):
    """
    Standard list response with pagination.
    
    {
        "success": true,
        "data": [ ... ],
        "pagination": { "page": 1, "total_items": 100, ... },
        "meta": { "timestamp": "...", "version": "1.0" }
    }
    """
    success: bool = True
    data: List[T] = []
    pagination: Optional[PaginationMeta] = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class APIErrorResponse(BaseModel):
    """
    Standard error response envelope.
    
    {
        "success": false,
        "error": {
            "code": "NOT_FOUND",
            "message": "Meeting not found",
            "detail": "No meeting with id=123"
        },
        "meta": { "timestamp": "...", "version": "1.0" }
    }
    """
    success: bool = False
    error: ErrorDetail
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


# -------------------------
# Response Helpers
# -------------------------

def success_response(
    data: Any = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a standard success response dict."""
    return APIResponse(
        data=data,
        meta=ResponseMeta(request_id=request_id)
    ).model_dump(mode="json")


def list_response(
    items: List[Any],
    total: int,
    skip: int = 0,
    limit: int = 20,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a standard paginated list response dict."""
    return APIListResponse(
        data=items,
        pagination=PaginationMeta.from_offset(total, skip, limit),
        meta=ResponseMeta(request_id=request_id)
    ).model_dump(mode="json")


def error_response(
    code: ErrorCode,
    message: str,
    detail: Optional[str] = None,
    field_errors: Optional[List[Dict[str, str]]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a standard error response dict."""
    errors = []
    if field_errors:
        errors = [FieldError(**e) for e in field_errors]
    
    return APIErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            detail=detail,
            field_errors=errors,
            trace_id=trace_id
        )
    ).model_dump(mode="json")


def not_found_response(
    resource: str,
    identifier: Any,
    detail: Optional[str] = None
) -> Dict[str, Any]:
    """Create a NOT_FOUND error response."""
    return error_response(
        code=ErrorCode.NOT_FOUND,
        message=f"{resource} not found",
        detail=detail or f"No {resource.lower()} with identifier: {identifier}"
    )


def validation_error_response(
    message: str = "Validation failed",
    field_errors: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Create a validation error response."""
    return error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message=message,
        field_errors=field_errors
    )


# -------------------------
# FastAPI Exception Classes
# -------------------------

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class APIException(HTTPException):
    """
    Custom API exception with structured error response.
    
    Usage:
        raise APIException(
            error_code=ErrorCode.NOT_FOUND,
            message="Meeting not found",
            detail="No meeting with id=123"
        )
    """
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        detail: Optional[str] = None,
        field_errors: Optional[List[Dict[str, str]]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.error_detail = detail
        self.field_errors = field_errors
        
        status_code = get_http_status(error_code)
        super().__init__(status_code=status_code, detail=message, headers=headers)
    
    def to_response(self) -> JSONResponse:
        """Convert to JSONResponse for exception handlers."""
        return JSONResponse(
            status_code=self.status_code,
            content=error_response(
                code=self.error_code,
                message=self.message,
                detail=self.error_detail,
                field_errors=self.field_errors
            )
        )


# Convenience exception factory functions
def raise_not_found(resource: str, identifier: Any, detail: Optional[str] = None):
    """Raise a NOT_FOUND exception."""
    raise APIException(
        error_code=ErrorCode.NOT_FOUND,
        message=f"{resource} not found",
        detail=detail or f"No {resource.lower()} with identifier: {identifier}"
    )


def raise_validation_error(
    message: str = "Validation failed",
    field_errors: Optional[List[Dict[str, str]]] = None
):
    """Raise a validation error exception."""
    raise APIException(
        error_code=ErrorCode.VALIDATION_ERROR,
        message=message,
        field_errors=field_errors
    )


def raise_permission_denied(message: str = "Permission denied"):
    """Raise a permission denied exception."""
    raise APIException(
        error_code=ErrorCode.PERMISSION_DENIED,
        message=message
    )
