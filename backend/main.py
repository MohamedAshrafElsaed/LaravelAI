"""
Laravel AI - FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    github,
    projects,
    chat,
    git,
    usage,
    health,
    teams,
    github_data,
    ui_designer,
)
from app.api.github_app import router as github_app_router
from app.core.config import settings
from app.core.logging import setup_logging, RequestLoggingMiddleware

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Laravel AI Backend...")
    yield
    logger.info("Shutting down Laravel AI Backend...")


# Create FastAPI app
app = FastAPI(
    title="Laravel AI Backend",
    description="AI-powered Laravel development assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging
app.add_middleware(RequestLoggingMiddleware)

# Register routers
app.include_router(health.router, tags=["health"])

app.include_router(
    auth.router,
    prefix=f"{settings.api_prefix}/auth",
    tags=["auth"],
)

app.include_router(
    github.router,
    prefix=f"{settings.api_prefix}/github",
    tags=["github"],
)

app.include_router(
    projects.router,
    prefix=f"{settings.api_prefix}/projects",
    tags=["projects"],
)

app.include_router(
    chat.router,
    prefix=f"{settings.api_prefix}/projects",
    tags=["chat"],
)

app.include_router(
    git.router,
    prefix=f"{settings.api_prefix}/projects",
    tags=["git"],
)

app.include_router(
    github_data.router,
    prefix=f"{settings.api_prefix}/projects",
    tags=["github-data"],
)

app.include_router(
    usage.router,
    prefix=f"{settings.api_prefix}/usage",
    tags=["usage"],
)

app.include_router(
    teams.router,
    prefix=f"{settings.api_prefix}/teams",
    tags=["teams"],
)

app.include_router(github_app_router, prefix=f"{settings.api_prefix}/github-app", tags=["GitHub App"])

app.include_router(
    ui_designer.router,
    prefix=f"{settings.api_prefix}/projects",
    tags=["ui-designer"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Laravel AI Backend",
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
