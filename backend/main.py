"""
Laravel AI - FastAPI Application Entry Point
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api import auth, health, projects, chat, github, git, git_changes


# Configure logging
def setup_logging():
    """Configure logging for the application."""
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set log levels for our modules
    logging.getLogger("app").setLevel(log_level)
    logging.getLogger("app.services").setLevel(log_level)
    logging.getLogger("app.api").setLevel(log_level)
    logging.getLogger("app.agents").setLevel(log_level)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)

    return logging.getLogger(__name__)


# Initialize logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Frontend URL: {settings.frontend_url}")
    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered Laravel code modification assistant",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix=f"{settings.api_prefix}/auth", tags=["Auth"])
app.include_router(
    projects.router, prefix=f"{settings.api_prefix}/projects", tags=["Projects"]
)
app.include_router(
    github.router, prefix=f"{settings.api_prefix}/github", tags=["GitHub"]
)
# Chat routes under /projects/{id}/chat
app.include_router(
    chat.router, prefix=f"{settings.api_prefix}/projects", tags=["Chat"]
)
# Git routes under /projects/{id}/...
app.include_router(
    git.router, prefix=f"{settings.api_prefix}/projects", tags=["Git"]
)
# Git changes tracking routes under /projects/{id}/changes
app.include_router(
    git_changes.router, prefix=f"{settings.api_prefix}/projects", tags=["Git Changes"]
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )