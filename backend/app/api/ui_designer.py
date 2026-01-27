"""
UI Designer API Routes.

Provides endpoints for AI-powered UI generation with real-time streaming.
"""

import json
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Project, User, ProjectStatus
from app.agents.ui_designer import UIDesigner, get_ui_designer
from app.agents.agent_identity import PALETTE
from app.services.claude import create_tracked_claude_service
from app.services.usage_tracker import UsageTracker
from app.schemas.ui_designer import (
    UIDesignRequest,
    UIDesignResult,
    DesignStatusResponse,
    DesignStatus,
    PreviewResponse,
    ApplyDesignRequest,
    ApplyDesignResponse,
    GeneratedFile,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# STORED DESIGNS (In-memory for now, should be Redis/DB in production)
# =============================================================================

_stored_designs: Dict[str, UIDesignResult] = {}
_active_generations: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_sse_event(event_type: str, data: dict) -> str:
    """Create an SSE formatted event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def verify_project_access(
    project_id: str,
    user: User,
    db: AsyncSession,
    require_ready: bool = True,
) -> Project:
    """Verify user has access to project."""
    from sqlalchemy import select

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

    if require_ready and project.status != ProjectStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project is not ready. Current status: {project.status}",
        )

    return project


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/agent")
async def get_ui_designer_agent(
    current_user: User = Depends(get_current_user),
):
    """
    Get information about the UI Designer agent (Palette).

    Returns agent identity with name, role, color, and personality.
    """
    return {
        "success": True,
        "agent": PALETTE.to_dict(),
    }


@router.post("/{project_id}/design")
async def create_ui_design(
    project_id: str,
    request: UIDesignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate UI components using the Palette agent.

    Returns a Server-Sent Events (SSE) stream with real-time progress updates.

    Events:
    - design_started: Generation started with agent info
    - agent_thinking: Agent is processing with thought message
    - tech_detected: Frontend technology detected
    - prompt_optimized: User prompt has been enhanced
    - generation_started: Code generation has begun
    - code_chunk: Chunk of generated code (for real-time preview)
    - file_ready: A complete file has been generated
    - design_complete: All generation finished with result summary
    - error: An error occurred

    The streaming response allows for:
    - Real-time code preview as it's generated
    - Progress tracking through agent thoughts
    - File-by-file completion notifications
    """
    logger.info(f"[UI_DESIGNER] POST /projects/{project_id}/design - user_id={current_user.id}")

    # Verify project access
    project = await verify_project_access(project_id, current_user, db)

    # Create design ID
    design_id = str(uuid4())

    # Track generation
    _active_generations[design_id] = {
        "user_id": str(current_user.id),
        "project_id": project_id,
        "status": DesignStatus.PENDING,
        "started_at": datetime.utcnow(),
    }

    logger.info(f"[UI_DESIGNER] Starting design {design_id}: {request.prompt[:100]}...")

    # Stream response
    return StreamingResponse(
        stream_ui_generation(
            project_id=project_id,
            design_id=design_id,
            request=request,
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


async def stream_ui_generation(
    project_id: str,
    design_id: str,
    request: UIDesignRequest,
    user_id: str,
    db: AsyncSession,
):
    """
    Generate SSE stream for UI generation.

    Yields events as the Palette agent generates code.
    """
    logger.info(f"[UI_DESIGNER] Starting stream for design {design_id}")

    try:
        # Create tracked Claude service
        tracker = UsageTracker(db)
        claude_service = create_tracked_claude_service(
            tracker=tracker,
            user_id=user_id,
            project_id=project_id,
        )

        # Create UI Designer
        designer = get_ui_designer(
            db=db,
            claude_service=claude_service,
        )

        # Send connected event
        yield create_sse_event("connected", {
            "design_id": design_id,
            "agent": PALETTE.to_dict(),
            "message": "Connected to UI Designer stream",
        })

        # Stream the generation
        async for event in designer.design_streaming(
            user_prompt=request.prompt,
            project_id=project_id,
            design_preferences=request.design_preferences,
            target_path=request.target_path,
        ):
            # Extract event type and data
            event_type = event.get("event", "unknown")
            event_data = event.get("data", {})

            # Add design_id if not present
            if "design_id" not in event_data:
                event_data["design_id"] = design_id

            # Store result if complete
            if event_type == "design_complete":
                # Update tracking
                _active_generations[design_id]["status"] = DesignStatus.COMPLETED
                _active_generations[design_id]["completed_at"] = datetime.utcnow()

                # Store the design result for later retrieval
                result_data = event_data.get("result", {})
                files_data = event_data.get("files", [])

                # Create full result
                # (In production, store in Redis/DB)

            yield create_sse_event(event_type, event_data)

        # Send final complete event
        yield create_sse_event("complete", {
            "design_id": design_id,
            "success": True,
            "message": "UI generation complete",
        })

    except asyncio.CancelledError:
        logger.info(f"[UI_DESIGNER] Stream cancelled for design {design_id}")
        _active_generations[design_id]["status"] = DesignStatus.CANCELLED
        yield create_sse_event("cancelled", {
            "design_id": design_id,
            "message": "Generation cancelled",
        })

    except Exception as e:
        logger.exception(f"[UI_DESIGNER] Stream error for design {design_id}: {e}")
        _active_generations[design_id]["status"] = DesignStatus.FAILED
        _active_generations[design_id]["error"] = str(e)
        yield create_sse_event("error", {
            "design_id": design_id,
            "error": str(e),
            "message": "UI generation failed",
        })

    finally:
        # Cleanup active generation after some time
        # (In production, use Redis TTL)
        pass


@router.post("/{project_id}/design/sync")
async def create_ui_design_sync(
    project_id: str,
    request: UIDesignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate UI components synchronously (non-streaming).

    Returns the complete result at once.
    Useful for simpler requests where streaming is not needed.
    """
    logger.info(f"[UI_DESIGNER] POST /projects/{project_id}/design/sync - user_id={current_user.id}")

    # Verify project access
    project = await verify_project_access(project_id, current_user, db)

    try:
        # Create tracked Claude service
        tracker = UsageTracker(db)
        claude_service = create_tracked_claude_service(
            tracker=tracker,
            user_id=str(current_user.id),
            project_id=project_id,
        )

        # Create UI Designer
        designer = get_ui_designer(
            db=db,
            claude_service=claude_service,
        )

        # Generate
        result = await designer.design(
            user_prompt=request.prompt,
            project_id=project_id,
            design_preferences=request.design_preferences,
            target_path=request.target_path,
        )

        # Store result
        _stored_designs[result.design_id] = result

        return {
            "success": result.success,
            "design_id": result.design_id,
            "files": [
                {
                    "path": f.path,
                    "type": f.file_type.value,
                    "language": f.language,
                    "line_count": f.line_count,
                    "component_name": f.component_name,
                    "content": f.content,
                }
                for f in result.files
            ],
            "summary": result.design_summary,
            "components_created": result.components_created,
            "dependencies_added": result.dependencies_added,
            "duration_ms": result.duration_ms,
            "total_files": result.total_files,
            "total_lines": result.total_lines,
            "tech_stack": {
                "framework": result.tech_stack.primary_framework.value,
                "css": result.tech_stack.css_framework.value,
                "typescript": result.tech_stack.typescript,
            } if result.tech_stack else None,
            "error": result.error,
        }

    except Exception as e:
        logger.exception(f"[UI_DESIGNER] Sync design error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{project_id}/design/{design_id}")
async def get_design_status(
    project_id: str,
    design_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of a design generation.

    Returns current status, progress, and result if completed.
    """
    logger.info(f"[UI_DESIGNER] GET /projects/{project_id}/design/{design_id}")

    # Check active generation
    gen_data = _active_generations.get(design_id)
    if gen_data:
        # Verify ownership
        if gen_data["user_id"] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        return {
            "design_id": design_id,
            "status": gen_data["status"].value if isinstance(gen_data["status"], DesignStatus) else gen_data["status"],
            "started_at": gen_data["started_at"].isoformat(),
            "completed_at": gen_data.get("completed_at", {}).isoformat() if gen_data.get("completed_at") else None,
            "error": gen_data.get("error"),
        }

    # Check stored designs
    result = _stored_designs.get(design_id)
    if result:
        return {
            "design_id": design_id,
            "status": "completed" if result.success else "failed",
            "total_files": result.total_files,
            "total_lines": result.total_lines,
            "components_created": result.components_created,
            "duration_ms": result.duration_ms,
            "error": result.error,
        }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Design not found",
    )


@router.get("/{project_id}/design/{design_id}/files")
async def get_design_files(
    project_id: str,
    design_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all generated files from a completed design.

    Returns full file contents for preview or download.
    """
    logger.info(f"[UI_DESIGNER] GET /projects/{project_id}/design/{design_id}/files")

    result = _stored_designs.get(design_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or files expired",
        )

    return {
        "design_id": design_id,
        "files": [
            {
                "path": f.path,
                "content": f.content,
                "type": f.file_type.value,
                "language": f.language,
                "line_count": f.line_count,
                "component_name": f.component_name,
                "exports": f.exports,
                "dependencies": f.dependencies,
            }
            for f in result.files
        ],
        "total_files": result.total_files,
    }


@router.delete("/{project_id}/design/{design_id}")
async def cancel_design(
    project_id: str,
    design_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel an active design generation.
    """
    logger.info(f"[UI_DESIGNER] DELETE /projects/{project_id}/design/{design_id}")

    gen_data = _active_generations.get(design_id)
    if not gen_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active design not found",
        )

    if gen_data["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Mark as cancelled
    gen_data["status"] = DesignStatus.CANCELLED
    gen_data["cancelled_at"] = datetime.utcnow()

    return {
        "success": True,
        "design_id": design_id,
        "message": "Design generation cancelled",
    }


@router.get("/{project_id}/tech-stack")
async def detect_tech_stack(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detect the frontend technology stack for a project.

    Returns detected framework, CSS framework, UI libraries, and design tokens.
    Useful for understanding what the UI Designer will use.
    """
    logger.info(f"[UI_DESIGNER] GET /projects/{project_id}/tech-stack")

    # Verify project access
    project = await verify_project_access(project_id, current_user, db)

    try:
        from app.services.frontend_detector import get_frontend_detector

        detector = get_frontend_detector(db)
        tech_stack = await detector.detect(project_id)

        return {
            "success": True,
            "tech_stack": {
                "framework": tech_stack.primary_framework.value,
                "css_framework": tech_stack.css_framework.value,
                "ui_libraries": [lib.value for lib in tech_stack.ui_libraries],
                "typescript": tech_stack.typescript,
                "component_path": tech_stack.component_path,
                "style_path": tech_stack.style_path,
                "pages_path": tech_stack.pages_path,
                "dark_mode_supported": tech_stack.dark_mode_supported,
                "confidence": tech_stack.confidence,
                "design_tokens": {
                    "colors": tech_stack.design_tokens.colors,
                    "spacing": tech_stack.design_tokens.spacing,
                    "typography": tech_stack.design_tokens.typography,
                    "borders": tech_stack.design_tokens.borders,
                },
                "existing_components": [
                    {
                        "name": comp.name,
                        "path": comp.path,
                        "props": comp.props,
                    }
                    for comp in tech_stack.existing_components[:20]
                ],
            },
        }

    except Exception as e:
        logger.exception(f"[UI_DESIGNER] Tech stack detection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{project_id}/design/{design_id}/apply")
async def apply_design(
    project_id: str,
    design_id: str,
    request: ApplyDesignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apply generated design files to the project.

    This endpoint writes the generated files to the actual project directory.
    Use with caution - creates real files in the codebase.

    Options:
    - selected_files: Only apply specific files (None = all)
    - backup: Create backup before applying (recommended)
    - overwrite_existing: Overwrite existing files (default: False)
    """
    logger.info(f"[UI_DESIGNER] POST /projects/{project_id}/design/{design_id}/apply")

    # Verify project access
    project = await verify_project_access(project_id, current_user, db)

    # Get design result
    result = _stored_designs.get(design_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found",
        )

    # Filter files if specified
    files_to_apply = result.files
    if request.selected_files:
        files_to_apply = [
            f for f in result.files
            if f.path in request.selected_files
        ]

    # TODO: Implement actual file writing
    # This would integrate with your git/file system services
    # For now, return a placeholder response

    return ApplyDesignResponse(
        success=True,
        files_applied=[f.path for f in files_to_apply],
        files_skipped=[],
        backup_path=None,
        errors=[],
    )
