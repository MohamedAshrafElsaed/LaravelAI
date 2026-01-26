"""
UI Designer API Endpoints

Provides REST and SSE endpoints for the Palette UI Designer agent.
Enables real-time UI code generation with streaming support.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Project, User, ProjectStatus
from app.agents.ui_designer import UIDesignerAgent, create_ui_designer
from app.agents.ui_designer_events import (
    UIDesignEventType,
    palette_message,
)
from app.agents.events import create_sse_event
from app.services.frontend_detector import FrontendDetector
from app.services.claude import get_claude_service, create_tracked_claude_service
from app.services.usage_tracker import UsageTracker
from app.schemas.ui_designer import (
    UIDesignRequest,
    UIDesignResponse,
    UIDesignResult,
    TechDetectionResponse,
    TechStackInfo,
    DesignStatusResponse,
    DesignStatus,
    CancelDesignRequest,
    CancelDesignResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active UI design sessions for status checks and cancellation
_active_designers: dict = {}


# ============== Helper Functions ==============


async def verify_project_access(
    project_id: str,
    user: User,
    db: AsyncSession,
) -> Project:
    """Verify user has access to project and it's ready."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status != ProjectStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project is not ready. Current status: {project.status}",
        )

    return project


# ============== Streaming Generator ==============


async def stream_ui_design(
    project_id: str,
    user_request: str,
    user_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for UI design generation.

    Yields SSE events as the Palette agent generates UI code.
    """
    logger.info(f"[UI_DESIGNER_API] Starting stream for project={project_id}")

    design_id = f"design_{uuid4().hex[:12]}"

    # Event queue for the designer callback
    event_queue: asyncio.Queue = asyncio.Queue()

    async def event_callback(event_str: str) -> None:
        """Callback to receive SSE event strings."""
        await event_queue.put(event_str)

    # Send connected event
    yield create_sse_event("connected", {
        "design_id": design_id,
        "message": "Connected to UI design stream",
        "agent": "palette",
        "agent_name": "Palette",
    })

    try:
        # Create tracked Claude service
        tracker = UsageTracker(db)
        claude_service = create_tracked_claude_service(
            tracker=tracker,
            user_id=user_id,
            project_id=project_id,
        )

        # Create UI Designer agent
        designer = await create_ui_designer(
            db=db,
            event_callback=event_callback,
            claude_service=claude_service,
        )

        # Store for cancellation
        _active_designers[design_id] = designer

        # Start design in background
        design_task = asyncio.create_task(
            designer.design(
                project_id=project_id,
                user_request=user_request,
                stream=True,
            )
        )

        # Stream events as they come
        while not design_task.done():
            try:
                event_str = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event_str
            except asyncio.TimeoutError:
                continue

        # Get final result
        result = await design_task

        # Drain remaining events
        while not event_queue.empty():
            event_str = await event_queue.get()
            yield event_str

        # Remove from active designers
        _active_designers.pop(design_id, None)

        # Send complete event with full result
        yield create_sse_event("complete", {
            "success": result.success,
            "design_id": result.design_id,
            "status": result.status.value,
            "files": [
                {
                    "path": f.path,
                    "content": f.content,
                    "file_type": f.file_type.value,
                    "language": f.language,
                    "lines_of_code": f.lines_of_code,
                    "dependencies": f.dependencies,
                }
                for f in result.files
            ],
            "summary": {
                "total_files": result.summary.total_files,
                "total_lines": result.summary.total_lines,
                "components_created": result.summary.components_created,
                "styles_generated": result.summary.styles_generated,
                "dependencies_added": result.summary.dependencies_added,
            },
            "tech_stack": result.tech_stack.model_dump() if result.tech_stack else None,
            "tokens_used": result.tokens_used,
            "generation_time_ms": result.generation_time_ms,
            "error": result.error,
        })

    except Exception as e:
        logger.exception(f"[UI_DESIGNER_API] Stream error: {e}")
        _active_designers.pop(design_id, None)

        yield create_sse_event("error", {
            "design_id": design_id,
            "error": str(e),
            "message": "UI design generation failed",
        })


# ============== API Endpoints ==============


@router.post("/{project_id}/ui/design")
async def design_ui(
    project_id: str,
    request: UIDesignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate UI code based on user request.

    Returns Server-Sent Events (SSE) stream with real-time generation progress
    when `stream=true` (default), or a complete response when `stream=false`.

    The Palette agent will:
    1. Detect the project's frontend technology (React, Vue, Blade, Livewire)
    2. Load existing design system and components
    3. Optimize the prompt using Claude best practices
    4. Generate beautiful, production-ready UI code
    5. Stream code chunks in real-time

    Events (streaming mode):
    - connected: Connection established
    - design_started: Generation started
    - tech_detected: Frontend technology detected
    - prompt_optimized: Prompt enhanced with best practices
    - generation_started: Code generation started
    - component_started: Component generation started
    - code_chunk: Real-time code streaming
    - component_completed: Component finished
    - file_ready: File ready for preview
    - design_completed: All generation complete
    - complete: Full result with all files
    - error: An error occurred
    """
    logger.info(f"[UI_DESIGNER_API] POST /{project_id}/ui/design - user_id={current_user.id}")
    logger.info(f"[UI_DESIGNER_API] Request: {request.request[:100]}...")

    # Verify project access
    await verify_project_access(project_id, current_user, db)

    if request.stream:
        # Return streaming response
        return StreamingResponse(
            stream_ui_design(
                project_id=project_id,
                user_request=request.request,
                user_id=str(current_user.id),
                db=db,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    else:
        # Non-streaming response
        try:
            # Create tracked Claude service
            tracker = UsageTracker(db)
            claude_service = create_tracked_claude_service(
                tracker=tracker,
                user_id=str(current_user.id),
                project_id=project_id,
            )

            # Create designer and generate
            designer = await create_ui_designer(
                db=db,
                claude_service=claude_service,
            )

            result = await designer.design(
                project_id=project_id,
                user_request=request.request,
                stream=False,
            )

            return UIDesignResponse(
                success=result.success,
                design_id=result.design_id,
                message="UI design generated successfully" if result.success else f"Design failed: {result.error}",
                result=result,
            )

        except Exception as e:
            logger.exception(f"[UI_DESIGNER_API] Design error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )


@router.get("/{project_id}/ui/detect-tech", response_model=TechDetectionResponse)
async def detect_technology(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detect the frontend technology stack of a project.

    Returns information about:
    - Primary framework (React, Vue, Blade, Livewire)
    - CSS framework (Tailwind, Bootstrap, etc.)
    - UI libraries (shadcn, Headless UI, etc.)
    - TypeScript usage
    - Design tokens found
    - Existing components count
    """
    logger.info(f"[UI_DESIGNER_API] GET /{project_id}/ui/detect-tech - user_id={current_user.id}")

    # Verify project access
    await verify_project_access(project_id, current_user, db)

    try:
        detector = FrontendDetector(db)
        detection = await detector.detect(project_id)

        tech_stack = TechStackInfo(
            primary_framework=detection.primary_framework.value,
            css_framework=detection.css_framework.value,
            ui_libraries=detection.ui_libraries,
            uses_typescript=detection.uses_typescript,
            uses_inertia=detection.uses_inertia,
            component_path=detection.component_path,
            page_path=detection.page_path,
        )

        return TechDetectionResponse(
            success=True,
            tech_stack=tech_stack,
            design_tokens_found=bool(
                detection.design_tokens.colors or
                detection.design_tokens.css_variables
            ),
            existing_components_count=len(detection.existing_components),
            message=f"Detected {detection.primary_framework.value} with {detection.css_framework.value}",
        )

    except Exception as e:
        logger.exception(f"[UI_DESIGNER_API] Tech detection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{project_id}/ui/design/{design_id}/status", response_model=DesignStatusResponse)
async def get_design_status(
    project_id: str,
    design_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of an ongoing UI design generation.

    Returns current status, progress, and file counts.
    """
    logger.info(f"[UI_DESIGNER_API] GET /{project_id}/ui/design/{design_id}/status")

    # Verify project access
    await verify_project_access(project_id, current_user, db)

    # Check if design is active
    designer = _active_designers.get(design_id)

    if not designer:
        # Design not found or completed
        return DesignStatusResponse(
            design_id=design_id,
            status=DesignStatus.COMPLETED,
            progress=1.0,
            current_phase="completed",
            files_completed=0,
            total_files=0,
            error=None,
        )

    # Get session status
    session = designer.get_session_status(design_id)

    if not session:
        return DesignStatusResponse(
            design_id=design_id,
            status=DesignStatus.PENDING,
            progress=0.0,
            current_phase="unknown",
        )

    # Calculate progress based on status
    progress_map = {
        DesignStatus.PENDING: 0.0,
        DesignStatus.DETECTING: 0.1,
        DesignStatus.OPTIMIZING: 0.2,
        DesignStatus.GENERATING: 0.4,
        DesignStatus.STREAMING: 0.6,
        DesignStatus.COMPLETED: 1.0,
        DesignStatus.FAILED: 0.0,
        DesignStatus.CANCELLED: 0.0,
    }

    return DesignStatusResponse(
        design_id=design_id,
        status=session.status,
        progress=progress_map.get(session.status, 0.0),
        current_phase=session.status.value,
        files_completed=len(session.files),
        total_files=len(session.files),  # Unknown until complete
        error=session.error,
    )


@router.post("/{project_id}/ui/design/{design_id}/cancel", response_model=CancelDesignResponse)
async def cancel_design(
    project_id: str,
    design_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel an ongoing UI design generation.

    Returns success if the design was cancelled, or error if not found.
    """
    logger.info(f"[UI_DESIGNER_API] POST /{project_id}/ui/design/{design_id}/cancel")

    # Verify project access
    await verify_project_access(project_id, current_user, db)

    # Check if design is active
    designer = _active_designers.get(design_id)

    if not designer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or already completed",
        )

    # Cancel the design
    cancelled = await designer.cancel(design_id)

    if cancelled:
        _active_designers.pop(design_id, None)
        return CancelDesignResponse(
            success=True,
            design_id=design_id,
            message="Design generation cancelled",
        )
    else:
        return CancelDesignResponse(
            success=False,
            design_id=design_id,
            message="Could not cancel design",
        )


@router.get("/{project_id}/ui/components")
async def list_existing_components(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List existing components in the project.

    Returns component names, paths, and types for reference
    when designing new UI.
    """
    logger.info(f"[UI_DESIGNER_API] GET /{project_id}/ui/components")

    # Verify project access
    await verify_project_access(project_id, current_user, db)

    try:
        detector = FrontendDetector(db)
        detection = await detector.detect(project_id)

        components = [
            {
                "name": c.name,
                "path": c.file_path,
                "type": c.component_type,
                "props": c.props,
                "exports": c.exports,
            }
            for c in detection.existing_components[:limit]
        ]

        return {
            "success": True,
            "framework": detection.primary_framework.value,
            "component_path": detection.component_path,
            "components_count": len(detection.existing_components),
            "components": components,
        }

    except Exception as e:
        logger.exception(f"[UI_DESIGNER_API] List components error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{project_id}/ui/design-system")
async def get_design_system(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the project's design system information.

    Returns:
    - Color tokens
    - Spacing scale
    - Typography settings
    - CSS variables
    - Tailwind config (if available)
    """
    logger.info(f"[UI_DESIGNER_API] GET /{project_id}/ui/design-system")

    # Verify project access
    await verify_project_access(project_id, current_user, db)

    try:
        detector = FrontendDetector(db)
        detection = await detector.detect(project_id)

        return {
            "success": True,
            "css_framework": detection.css_framework.value,
            "design_tokens": {
                "colors": detection.design_tokens.colors,
                "spacing": detection.design_tokens.spacing,
                "typography": detection.design_tokens.typography,
                "border_radius": detection.design_tokens.border_radius,
                "shadows": detection.design_tokens.shadows,
                "breakpoints": detection.design_tokens.breakpoints,
            },
            "css_variables": detection.design_tokens.css_variables,
            "tailwind_config_found": bool(detection.tailwind_config),
        }

    except Exception as e:
        logger.exception(f"[UI_DESIGNER_API] Get design system error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{project_id}/ui/agent")
async def get_palette_agent_info(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get information about the Palette UI Designer agent.

    Returns agent identity including name, role, color, and capabilities.
    """
    from app.agents.ui_designer_identity import PALETTE

    return {
        "success": True,
        "agent": {
            "name": PALETTE.name,
            "role": PALETTE.role,
            "color": PALETTE.color,
            "icon": PALETTE.icon,
            "avatar_emoji": PALETTE.avatar_emoji,
            "personality": PALETTE.personality,
            "capabilities": [
                "Generate React components with TypeScript",
                "Generate Vue components with Composition API",
                "Generate Blade templates with Alpine.js",
                "Generate Livewire components",
                "Detect and follow existing design systems",
                "Create responsive, accessible UI",
                "Support dark mode",
                "Real-time code streaming",
            ],
            "supported_frameworks": ["React", "Vue", "Blade", "Livewire"],
            "css_frameworks": ["Tailwind CSS", "Bootstrap"],
        },
    }
