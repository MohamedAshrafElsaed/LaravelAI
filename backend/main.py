"""
Laravel AI - FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.logging import setup_logging, RequestLoggingMiddleware
from app.core.exceptions import register_exception_handlers
from app.api import auth, health, projects, chat, github, git, git_changes


# Initialize logging with configuration
setup_logging(
    log_level="DEBUG" if settings.debug else settings.log_level,
    log_dir=settings.log_dir if settings.log_dir else None,
    json_logs=settings.log_json,
    app_name="laravelai",
)

logger = logging.getLogger(__name__)


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

# Register global exception handlers
register_exception_handlers(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

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