"""
Logging configuration for the application.
Supports console and file logging with structured JSON output.
"""
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ============================================================================
# JSON Formatter
# ============================================================================


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        extra_keys = [
            "request_id",
            "user_id",
            "project_id",
            "path",
            "method",
            "status_code",
            "duration_ms",
            "code",
            "details",
            "errors",
            "traceback",
        ]
        for key in extra_keys:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Color the level name
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        # Add extra context if present
        extras = []
        if hasattr(record, "request_id"):
            extras.append(f"req={record.request_id[:8]}")
        if hasattr(record, "user_id"):
            extras.append(f"user={record.user_id}")
        if hasattr(record, "project_id"):
            extras.append(f"project={record.project_id}")
        if hasattr(record, "code"):
            extras.append(f"code={record.code}")

        if extras:
            formatted += f" [{', '.join(extras)}]"

        return formatted


# ============================================================================
# Logging Setup
# ============================================================================


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    json_logs: bool = False,
    app_name: str = "laravelai",
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files. If None, only console logging is used.
        json_logs: Whether to use JSON format for logs.
        app_name: Application name for log files.

    Returns:
        Root logger instance.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_logs:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            ColoredConsoleFormatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # File handlers (if log directory specified)
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Main application log (rotated by size)
        app_log_file = log_path / f"{app_name}.log"
        file_handler = RotatingFileHandler(
            app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

        # Error log (rotated daily)
        error_log_file = log_path / f"{app_name}_error.log"
        error_handler = TimedRotatingFileHandler(
            error_log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(error_handler)

        # Access log (rotated daily)
        access_log_file = log_path / f"{app_name}_access.log"
        access_logger = logging.getLogger("access")
        access_logger.setLevel(logging.INFO)
        access_logger.propagate = False  # Don't propagate to root logger

        access_handler = TimedRotatingFileHandler(
            access_log_file,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
        access_handler.setFormatter(JSONFormatter())
        access_logger.addHandler(access_handler)

    # Set log levels for application modules
    logging.getLogger("app").setLevel(level)
    logging.getLogger("app.services").setLevel(level)
    logging.getLogger("app.api").setLevel(level)
    logging.getLogger("app.agents").setLevel(level)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return root_logger


# ============================================================================
# Request Logging Middleware
# ============================================================================


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and adding request IDs."""

    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/redoc", "/openapi.json"]
        self.access_logger = logging.getLogger("access")
        self.logger = logging.getLogger(__name__)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Skip logging for excluded paths
        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # Record start time
        start_time = datetime.utcnow()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log the request
        self.access_logger.info(
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "status_code": response.status_code,
                "duration_ms": round(duration, 2),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )

        # Log slow requests
        if duration > 1000:  # More than 1 second
            self.logger.warning(
                f"Slow request: {request.method} {request.url.path} took {duration:.2f}ms",
                extra={
                    "request_id": request_id,
                    "duration_ms": round(duration, 2),
                },
            )

        return response


# ============================================================================
# Utility Functions
# ============================================================================


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    **kwargs,
) -> None:
    """Log a message with additional context."""
    extra = {k: v for k, v in kwargs.items() if v is not None}
    if request_id:
        extra["request_id"] = request_id
    if user_id:
        extra["user_id"] = user_id
    if project_id:
        extra["project_id"] = project_id

    logger.log(level, message, extra=extra)
