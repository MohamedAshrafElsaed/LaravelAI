"""
UI Designer SSE Events

Defines all Server-Sent Event types for the UI Designer agent,
enabling real-time streaming of design generation progress.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List

from app.agents.events import create_sse_event


class UIDesignEventType(str, Enum):
    """SSE event types for UI Designer agent."""

    # Design Session Events
    DESIGN_STARTED = "design_started"
    DESIGN_COMPLETED = "design_completed"
    DESIGN_ERROR = "design_error"
    DESIGN_CANCELLED = "design_cancelled"

    # Technology Detection Events
    TECH_DETECTION_STARTED = "tech_detection_started"
    TECH_DETECTED = "tech_detected"

    # Prompt Optimization Events
    PROMPT_OPTIMIZATION_STARTED = "prompt_optimization_started"
    PROMPT_OPTIMIZED = "prompt_optimized"

    # Design System Events
    DESIGN_SYSTEM_LOADED = "design_system_loaded"
    EXISTING_COMPONENTS_LOADED = "existing_components_loaded"

    # Generation Events
    GENERATION_STARTED = "generation_started"
    COMPONENT_STARTED = "component_started"
    CODE_CHUNK = "code_chunk"
    COMPONENT_COMPLETED = "component_completed"
    GENERATION_COMPLETED = "generation_completed"

    # File Events
    FILE_STARTED = "file_started"
    FILE_CHUNK = "file_chunk"
    FILE_COMPLETED = "file_completed"
    FILE_READY = "file_ready"

    # Style Events
    STYLE_GENERATED = "style_generated"

    # Agent Events
    PALETTE_THINKING = "palette_thinking"
    PALETTE_MESSAGE = "palette_message"

    # Progress Events
    PROGRESS_UPDATE = "progress_update"


# ============== Event Builder Functions ==============


def design_started(
    design_id: str,
    request: str,
    message: str = "Starting UI design generation...",
) -> str:
    """Emit when design generation starts."""
    return create_sse_event(UIDesignEventType.DESIGN_STARTED.value, {
        "design_id": design_id,
        "request": request[:200],
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def design_completed(
    design_id: str,
    files_count: int,
    components_count: int,
    message: str = "Design generation completed!",
) -> str:
    """Emit when design generation completes successfully."""
    return create_sse_event(UIDesignEventType.DESIGN_COMPLETED.value, {
        "design_id": design_id,
        "files_count": files_count,
        "components_count": components_count,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def design_error(
    design_id: str,
    error: str,
    message: str = "Design generation failed",
) -> str:
    """Emit when design generation fails."""
    return create_sse_event(UIDesignEventType.DESIGN_ERROR.value, {
        "design_id": design_id,
        "error": error,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def design_cancelled(
    design_id: str,
    message: str = "Design generation cancelled",
) -> str:
    """Emit when design generation is cancelled."""
    return create_sse_event(UIDesignEventType.DESIGN_CANCELLED.value, {
        "design_id": design_id,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def tech_detection_started(
    message: str = "Detecting frontend technology...",
) -> str:
    """Emit when technology detection starts."""
    return create_sse_event(UIDesignEventType.TECH_DETECTION_STARTED.value, {
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def tech_detected(
    framework: str,
    css_framework: str,
    ui_libraries: List[str],
    uses_typescript: bool,
    message: str = "Technology stack detected",
) -> str:
    """Emit when technology detection completes."""
    return create_sse_event(UIDesignEventType.TECH_DETECTED.value, {
        "framework": framework,
        "css_framework": css_framework,
        "ui_libraries": ui_libraries,
        "uses_typescript": uses_typescript,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def prompt_optimization_started(
    message: str = "Optimizing design prompt...",
) -> str:
    """Emit when prompt optimization starts."""
    return create_sse_event(UIDesignEventType.PROMPT_OPTIMIZATION_STARTED.value, {
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def prompt_optimized(
    enhancements: List[str],
    estimated_tokens: int,
    message: str = "Prompt optimized with best practices",
) -> str:
    """Emit when prompt optimization completes."""
    return create_sse_event(UIDesignEventType.PROMPT_OPTIMIZED.value, {
        "enhancements": enhancements,
        "estimated_tokens": estimated_tokens,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def design_system_loaded(
    colors_count: int,
    tokens_loaded: bool,
    message: str = "Design system loaded",
) -> str:
    """Emit when design system is loaded."""
    return create_sse_event(UIDesignEventType.DESIGN_SYSTEM_LOADED.value, {
        "colors_count": colors_count,
        "tokens_loaded": tokens_loaded,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def existing_components_loaded(
    components_count: int,
    component_names: List[str],
    message: str = "Existing components loaded",
) -> str:
    """Emit when existing components are loaded."""
    return create_sse_event(UIDesignEventType.EXISTING_COMPONENTS_LOADED.value, {
        "components_count": components_count,
        "component_names": component_names[:10],  # Limit to 10 names
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def generation_started(
    total_files: int,
    message: str = "Starting code generation...",
) -> str:
    """Emit when code generation starts."""
    return create_sse_event(UIDesignEventType.GENERATION_STARTED.value, {
        "total_files": total_files,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def component_started(
    component_name: str,
    component_index: int,
    total_components: int,
    file_path: str,
    message: Optional[str] = None,
) -> str:
    """Emit when a component generation starts."""
    return create_sse_event(UIDesignEventType.COMPONENT_STARTED.value, {
        "component_name": component_name,
        "component_index": component_index,
        "total_components": total_components,
        "file_path": file_path,
        "message": message or f"Generating {component_name}...",
        "agent": "palette",
        "agent_name": "Palette",
    })


def code_chunk(
    file_path: str,
    chunk: str,
    chunk_index: int,
    accumulated_length: int,
    total_length: int,
    done: bool = False,
    content: Optional[str] = None,
) -> str:
    """
    Emit a code chunk during generation for real-time streaming.

    Args:
        file_path: Path of the file being generated
        chunk: The current chunk of code
        chunk_index: Index of this chunk
        accumulated_length: Total characters accumulated so far
        total_length: Total expected length (0 if unknown)
        done: Whether this is the final chunk
        content: Full content (only sent when done=True)
    """
    progress = accumulated_length / total_length if total_length > 0 else 0

    data = {
        "file_path": file_path,
        "chunk": chunk,
        "chunk_index": chunk_index,
        "accumulated_length": accumulated_length,
        "total_length": total_length,
        "progress": progress,
        "done": done,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if done and content:
        data["content"] = content

    return create_sse_event(UIDesignEventType.CODE_CHUNK.value, data)


def component_completed(
    component_name: str,
    component_index: int,
    total_components: int,
    file_path: str,
    lines_of_code: int,
    message: Optional[str] = None,
) -> str:
    """Emit when a component generation completes."""
    return create_sse_event(UIDesignEventType.COMPONENT_COMPLETED.value, {
        "component_name": component_name,
        "component_index": component_index,
        "total_components": total_components,
        "file_path": file_path,
        "lines_of_code": lines_of_code,
        "message": message or f"{component_name} completed!",
        "agent": "palette",
        "agent_name": "Palette",
    })


def generation_completed(
    total_files: int,
    total_lines: int,
    message: str = "Code generation completed!",
) -> str:
    """Emit when all code generation completes."""
    return create_sse_event(UIDesignEventType.GENERATION_COMPLETED.value, {
        "total_files": total_files,
        "total_lines": total_lines,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def file_started(
    file_path: str,
    file_type: str,
    file_index: int,
    total_files: int,
) -> str:
    """Emit when file generation starts."""
    return create_sse_event(UIDesignEventType.FILE_STARTED.value, {
        "file_path": file_path,
        "file_type": file_type,
        "file_index": file_index,
        "total_files": total_files,
        "agent": "palette",
        "agent_name": "Palette",
    })


def file_chunk(
    file_path: str,
    chunk: str,
    accumulated: int,
    total: int,
) -> str:
    """Emit a file content chunk."""
    return create_sse_event(UIDesignEventType.FILE_CHUNK.value, {
        "file_path": file_path,
        "chunk": chunk,
        "accumulated": accumulated,
        "total": total,
        "progress": accumulated / total if total > 0 else 0,
    })


def file_completed(
    file_path: str,
    file_type: str,
    content: str,
    lines_of_code: int,
) -> str:
    """Emit when file generation completes."""
    return create_sse_event(UIDesignEventType.FILE_COMPLETED.value, {
        "file_path": file_path,
        "file_type": file_type,
        "content": content,
        "lines_of_code": lines_of_code,
        "agent": "palette",
        "agent_name": "Palette",
    })


def file_ready(
    file_path: str,
    file_type: str,
    language: str,
    preview_url: Optional[str] = None,
) -> str:
    """Emit when file is ready for preview."""
    return create_sse_event(UIDesignEventType.FILE_READY.value, {
        "file_path": file_path,
        "file_type": file_type,
        "language": language,
        "preview_url": preview_url,
        "agent": "palette",
        "agent_name": "Palette",
    })


def style_generated(
    style_type: str,
    file_path: str,
    message: str = "Styles generated",
) -> str:
    """Emit when styles are generated."""
    return create_sse_event(UIDesignEventType.STYLE_GENERATED.value, {
        "style_type": style_type,
        "file_path": file_path,
        "message": message,
        "agent": "palette",
        "agent_name": "Palette",
    })


def palette_thinking(
    thought: str,
    action_type: Optional[str] = None,
    file_path: Optional[str] = None,
    progress: float = 0.0,
) -> str:
    """Emit Palette's thinking/processing message."""
    return create_sse_event(UIDesignEventType.PALETTE_THINKING.value, {
        "thought": thought,
        "action_type": action_type,
        "file_path": file_path,
        "progress": progress,
        "agent": "palette",
        "agent_name": "Palette",
    })


def palette_message(
    message: str,
    message_type: str = "custom",  # greeting, thinking, completion, error
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Emit a message from Palette agent."""
    return create_sse_event(UIDesignEventType.PALETTE_MESSAGE.value, {
        "message": message,
        "message_type": message_type,
        "metadata": metadata or {},
        "agent": "palette",
        "agent_name": "Palette",
    })


def progress_update(
    phase: str,
    progress: float,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Emit general progress update."""
    return create_sse_event(UIDesignEventType.PROGRESS_UPDATE.value, {
        "phase": phase,
        "progress": progress,
        "message": message,
        "details": details or {},
        "agent": "palette",
        "agent_name": "Palette",
    })
