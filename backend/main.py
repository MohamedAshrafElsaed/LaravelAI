"""
Laravel AI - FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api import auth, health, projects, chat


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - startup and shutdown events."""
    # Startup
    print(f"🚀 Starting {settings.app_name}...")
    await init_db()
    print("✅ Database initialized")

    yield

    # Shutdown
    print("🛑 Shutting down...")
    await close_db()
    print("✅ Cleanup complete")


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
    chat.router, prefix=f"{settings.api_prefix}/chat", tags=["Chat"]
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )