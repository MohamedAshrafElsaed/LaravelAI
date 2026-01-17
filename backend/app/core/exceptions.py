"""
Custom exceptions and global exception handlers for the application.
"""
import logging
import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# ============================================================================
# Error Response Models
# ============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standardized error response model."""
    success: bool = False
    error: ErrorDetail
    request_id: Optional[str] = None


# ============================================================================
# Error Codes
# ============================================================================


class ErrorCode:
    """Application error codes."""
    # Authentication errors (AUTH_xxx)
    AUTH_TOKEN_MISSING = "AUTH_001"
    AUTH_TOKEN_INVALID = "AUTH_002"
    AUTH_TOKEN_EXPIRED = "AUTH_003"
    AUTH_UNAUTHORIZED = "AUTH_004"
    AUTH_FORBIDDEN = "AUTH_005"

    # Validation errors (VAL_xxx)
    VAL_INVALID_INPUT = "VAL_001"
    VAL_MISSING_FIELD = "VAL_002"
    VAL_INVALID_FORMAT = "VAL_003"

    # Resource errors (RES_xxx)
    RES_NOT_FOUND = "RES_001"
    RES_ALREADY_EXISTS = "RES_002"
    RES_CONFLICT = "RES_003"

    # Project errors (PRJ_xxx)
    PRJ_NOT_FOUND = "PRJ_001"
    PRJ_NOT_READY = "PRJ_002"
    PRJ_CLONE_FAILED = "PRJ_003"
    PRJ_INDEX_FAILED = "PRJ_004"
    PRJ_ALREADY_EXISTS = "PRJ_005"

    # Git errors (GIT_xxx)
    GIT_OPERATION_FAILED = "GIT_001"
    GIT_BRANCH_NOT_FOUND = "GIT_002"
    GIT_COMMIT_FAILED = "GIT_003"
    GIT_PUSH_FAILED = "GIT_004"
    GIT_PR_FAILED = "GIT_005"
    GIT_ROLLBACK_FAILED = "GIT_006"

    # AI/Chat errors (AI_xxx)
    AI_PROCESSING_FAILED = "AI_001"
    AI_CONTEXT_FAILED = "AI_002"
    AI_GENERATION_FAILED = "AI_003"
    AI_VALIDATION_FAILED = "AI_004"

    # External service errors (EXT_xxx)
    EXT_GITHUB_ERROR = "EXT_001"
    EXT_CLAUDE_ERROR = "EXT_002"
    EXT_QDRANT_ERROR = "EXT_003"
    EXT_DATABASE_ERROR = "EXT_004"

    # Server errors (SRV_xxx)
    SRV_INTERNAL_ERROR = "SRV_001"
    SRV_SERVICE_UNAVAILABLE = "SRV_002"
    SRV_RATE_LIMITED = "SRV_003"


# ============================================================================
# Custom Exceptions
# ============================================================================


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: str = ErrorCode.SRV_INTERNAL_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        field: Optional[str] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        self.field = field
        super().__init__(message)


class AuthenticationError(AppException):
    """Authentication related errors."""

    def __init__(
        self,
        message: str = "Authentication required",
        code: str = ErrorCode.AUTH_TOKEN_INVALID,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationError(AppException):
    """Authorization/permission errors."""

    def __init__(
        self,
        message: str = "Permission denied",
        code: str = ErrorCode.AUTH_FORBIDDEN,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class NotFoundError(AppException):
    """Resource not found errors."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: str = ErrorCode.RES_NOT_FOUND,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details if details else None,
        )


class ConflictError(AppException):
    """Resource conflict errors."""

    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = ErrorCode.RES_CONFLICT,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationError(AppException):
    """Input validation errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        code: str = ErrorCode.VAL_INVALID_INPUT,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
            field=field,
        )


class ProjectError(AppException):
    """Project-related errors."""

    def __init__(
        self,
        message: str,
        code: str = ErrorCode.PRJ_NOT_READY,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
        )


class GitError(AppException):
    """Git operation errors."""

    def __init__(
        self,
        message: str,
        code: str = ErrorCode.GIT_OPERATION_FAILED,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class AIProcessingError(AppException):
    """AI processing errors."""

    def __init__(
        self,
        message: str,
        code: str = ErrorCode.AI_PROCESSING_FAILED,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ExternalServiceError(AppException):
    """External service errors."""

    def __init__(
        self,
        message: str,
        service: str,
        code: str = ErrorCode.EXT_GITHUB_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        _details = {"service": service}
        if details:
            _details.update(details)

        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=_details,
        )


class RateLimitError(AppException):
    """Rate limiting errors."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            code=ErrorCode.SRV_RATE_LIMITED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details if details else None,
        )


# ============================================================================
# Exception Handlers
# ============================================================================


def create_error_response(
    code: str,
    message: str,
    status_code: int,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Create a standardized error response."""
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            field=field,
            details=details,
        ),
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(exclude_none=True),
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Log the error
    logger.error(
        f"[{exc.code}] {exc.message}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "code": exc.code,
            "details": exc.details,
        },
    )

    return create_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        field=exc.field,
        details=exc.details,
        request_id=request_id,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Map HTTP status to error codes
    status_to_code = {
        400: ErrorCode.VAL_INVALID_INPUT,
        401: ErrorCode.AUTH_UNAUTHORIZED,
        403: ErrorCode.AUTH_FORBIDDEN,
        404: ErrorCode.RES_NOT_FOUND,
        409: ErrorCode.RES_CONFLICT,
        422: ErrorCode.VAL_INVALID_INPUT,
        429: ErrorCode.SRV_RATE_LIMITED,
        500: ErrorCode.SRV_INTERNAL_ERROR,
        502: ErrorCode.SRV_SERVICE_UNAVAILABLE,
        503: ErrorCode.SRV_SERVICE_UNAVAILABLE,
    }

    code = status_to_code.get(exc.status_code, ErrorCode.SRV_INTERNAL_ERROR)
    message = str(exc.detail) if exc.detail else "An error occurred"

    logger.warning(
        f"HTTP {exc.status_code}: {message}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return create_error_response(
        code=code,
        message=message,
        status_code=exc.status_code,
        request_id=request_id,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    request_id = getattr(request.state, "request_id", None)

    # Extract validation error details
    errors = exc.errors()
    first_error = errors[0] if errors else {}

    field = ".".join(str(loc) for loc in first_error.get("loc", [])[1:])  # Skip 'body'
    message = first_error.get("msg", "Validation failed")

    # Build details with all errors
    details = {
        "errors": [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])[1:]),
                "message": err.get("msg"),
                "type": err.get("type"),
            }
            for err in errors
        ]
    }

    logger.warning(
        f"Validation error: {message}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": details,
        },
    )

    return create_error_response(
        code=ErrorCode.VAL_INVALID_INPUT,
        message=f"Validation error: {message}",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        field=field if field else None,
        details=details,
        request_id=request_id,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Log the full traceback
    logger.exception(
        f"Unhandled exception: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc(),
        },
    )

    # In production, don't expose internal error details
    from app.core.config import settings

    if settings.is_production:
        message = "An internal error occurred"
        details = None
    else:
        message = str(exc)
        details = {"traceback": traceback.format_exc().split("\n")}

    return create_error_response(
        code=ErrorCode.SRV_INTERNAL_ERROR,
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=details,
        request_id=request_id,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
