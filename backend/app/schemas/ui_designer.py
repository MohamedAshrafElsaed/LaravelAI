"""
Pydantic schemas for UI Designer agent.

Defines request/response models for the UI design generation API.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class FrontendFramework(str, Enum):
    """Supported frontend frameworks."""
    REACT = "react"
    VUE = "vue"
    BLADE = "blade"
    LIVEWIRE = "livewire"
    UNKNOWN = "unknown"


class CSSFramework(str, Enum):
    """Supported CSS frameworks."""
    TAILWIND = "tailwind"
    BOOTSTRAP = "bootstrap"
    CUSTOM = "custom"
    NONE = "none"


class UILibrary(str, Enum):
    """Supported UI component libraries."""
    SHADCN = "shadcn"
    RADIX = "radix"
    HEADLESS_UI = "headless-ui"
    PRIMEVUE = "primevue"
    ALPINE = "alpine"
    LIVEWIRE_COMPONENTS = "livewire-components"
    NONE = "none"


class FileType(str, Enum):
    """Generated file types."""
    COMPONENT = "component"
    PAGE = "page"
    LAYOUT = "layout"
    STYLE = "style"
    CONFIG = "config"
    ASSET = "asset"
    HOOK = "hook"
    UTILITY = "utility"


class DesignStatus(str, Enum):
    """Design generation status."""
    PENDING = "pending"
    DETECTING = "detecting"
    OPTIMIZING = "optimizing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# REQUEST MODELS
# =============================================================================

class UIDesignRequest(BaseModel):
    """Request body for UI design generation."""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="User's design request (e.g., 'Create a dashboard with charts')"
    )

    conversation_id: Optional[str] = Field(
        None,
        description="Optional conversation ID for context continuity"
    )

    target_path: Optional[str] = Field(
        None,
        description="Optional target directory for generated files"
    )

    design_preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional design preferences (colors, style, etc.)"
    )

    include_tests: bool = Field(
        False,
        description="Whether to generate test files"
    )

    include_stories: bool = Field(
        False,
        description="Whether to generate Storybook stories"
    )


class DesignCancelRequest(BaseModel):
    """Request to cancel ongoing design generation."""

    design_id: str = Field(..., description="ID of the design to cancel")
    reason: Optional[str] = Field(None, description="Optional cancellation reason")


# =============================================================================
# RESPONSE MODELS - Design System Detection
# =============================================================================

class DesignTokens(BaseModel):
    """Design tokens extracted from the project."""

    colors: Dict[str, str] = Field(
        default_factory=dict,
        description="Color tokens (e.g., {'primary': '#EC4899'})"
    )

    spacing: Dict[str, str] = Field(
        default_factory=dict,
        description="Spacing scale (e.g., {'sm': '0.5rem'})"
    )

    typography: Dict[str, Any] = Field(
        default_factory=dict,
        description="Typography settings (fonts, sizes)"
    )

    borders: Dict[str, str] = Field(
        default_factory=dict,
        description="Border radius and styles"
    )

    shadows: Dict[str, str] = Field(
        default_factory=dict,
        description="Box shadow definitions"
    )

    breakpoints: Dict[str, str] = Field(
        default_factory=dict,
        description="Responsive breakpoints"
    )


class ExistingComponent(BaseModel):
    """Information about an existing component in the project."""

    name: str = Field(..., description="Component name")
    path: str = Field(..., description="File path")
    props: List[str] = Field(default_factory=list, description="Component props")
    description: Optional[str] = Field(None, description="Component description")


class FrontendTechStack(BaseModel):
    """Detected frontend technology stack."""

    primary_framework: FrontendFramework = Field(
        FrontendFramework.UNKNOWN,
        description="Primary frontend framework"
    )

    css_framework: CSSFramework = Field(
        CSSFramework.NONE,
        description="CSS framework in use"
    )

    ui_libraries: List[UILibrary] = Field(
        default_factory=list,
        description="UI component libraries detected"
    )

    typescript: bool = Field(
        False,
        description="Whether TypeScript is used"
    )

    component_path: str = Field(
        "",
        description="Path to components directory"
    )

    style_path: str = Field(
        "",
        description="Path to styles directory"
    )

    pages_path: str = Field(
        "",
        description="Path to pages directory"
    )

    design_tokens: DesignTokens = Field(
        default_factory=DesignTokens,
        description="Extracted design tokens"
    )

    existing_components: List[ExistingComponent] = Field(
        default_factory=list,
        description="Existing components in the project"
    )

    dark_mode_supported: bool = Field(
        False,
        description="Whether dark mode is supported"
    )

    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Detection confidence (0-1)"
    )


# =============================================================================
# RESPONSE MODELS - Prompt Optimization
# =============================================================================

class OptimizedPrompt(BaseModel):
    """Result of prompt optimization."""

    original_prompt: str = Field(..., description="Original user prompt")
    optimized_prompt: str = Field(..., description="Enhanced prompt for Claude")
    system_prompt: str = Field(..., description="System prompt for UI generation")

    enhancements_applied: List[str] = Field(
        default_factory=list,
        description="List of enhancements applied"
    )

    context_tokens_estimate: int = Field(
        0,
        description="Estimated token count for context"
    )

    detected_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Requirements extracted from prompt"
    )


# =============================================================================
# RESPONSE MODELS - Generated Files
# =============================================================================

class GeneratedFile(BaseModel):
    """A single generated file."""

    path: str = Field(..., description="Full file path")
    content: str = Field(..., description="Complete file content")
    file_type: FileType = Field(..., description="Type of file")
    language: str = Field(..., description="Programming language (tsx, vue, php, css)")

    dependencies: List[str] = Field(
        default_factory=list,
        description="Required imports/packages"
    )

    preview_url: Optional[str] = Field(
        None,
        description="URL for live preview (if available)"
    )

    line_count: int = Field(0, description="Number of lines in file")

    component_name: Optional[str] = Field(
        None,
        description="Component name (if applicable)"
    )

    exports: List[str] = Field(
        default_factory=list,
        description="Exported symbols"
    )


class UIDesignResult(BaseModel):
    """Complete result of UI design generation."""

    success: bool = Field(..., description="Whether generation succeeded")
    design_id: str = Field(..., description="Unique design ID")

    files: List[GeneratedFile] = Field(
        default_factory=list,
        description="Generated files"
    )

    design_summary: str = Field(
        "",
        description="Summary of what was created"
    )

    components_created: List[str] = Field(
        default_factory=list,
        description="Names of components created"
    )

    styles_generated: List[str] = Field(
        default_factory=list,
        description="Style files generated"
    )

    dependencies_added: List[str] = Field(
        default_factory=list,
        description="New dependencies to install"
    )

    preview_available: bool = Field(
        False,
        description="Whether preview is available"
    )

    total_tokens_used: int = Field(
        0,
        description="Total tokens consumed"
    )

    total_files: int = Field(0, description="Total files generated")
    total_lines: int = Field(0, description="Total lines of code")

    tech_stack: Optional[FrontendTechStack] = Field(
        None,
        description="Detected tech stack"
    )

    optimized_prompt: Optional[OptimizedPrompt] = Field(
        None,
        description="Prompt optimization details"
    )

    error: Optional[str] = Field(None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warnings")

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )

    duration_ms: int = Field(0, description="Total generation time in ms")


# =============================================================================
# SSE EVENT MODELS
# =============================================================================

class DesignEventData(BaseModel):
    """Base data for design SSE events."""

    design_id: str = Field(..., description="Design ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TechDetectedEvent(DesignEventData):
    """Data for tech detection event."""

    tech_stack: FrontendTechStack
    message: str = "Frontend technology detected"


class PromptOptimizedEvent(DesignEventData):
    """Data for prompt optimization event."""

    optimized_prompt: OptimizedPrompt
    message: str = "Prompt optimized"


class ComponentStartedEvent(DesignEventData):
    """Data for component generation start event."""

    component_name: str
    file_path: str
    component_index: int
    total_components: int
    message: str = "Starting component generation"


class CodeChunkEvent(DesignEventData):
    """Data for code chunk streaming event."""

    file_path: str
    chunk: str
    chunk_index: int
    accumulated_length: int
    total_length_estimate: int
    progress: float = Field(ge=0.0, le=1.0)
    done: bool = False


class FileReadyEvent(DesignEventData):
    """Data for file completion event."""

    file: GeneratedFile
    file_index: int
    total_files: int
    message: str = "File generated"


class DesignCompleteEvent(DesignEventData):
    """Data for design completion event."""

    result: UIDesignResult
    message: str = "Design generation complete"


class DesignErrorEvent(DesignEventData):
    """Data for design error event."""

    error: str
    error_type: str = "generation_error"
    recoverable: bool = False


# =============================================================================
# API RESPONSE MODELS
# =============================================================================

class DesignStatusResponse(BaseModel):
    """Response for design status check."""

    design_id: str
    status: DesignStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    current_step: str = ""
    files_generated: int = 0
    total_files_expected: int = 0
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DesignListResponse(BaseModel):
    """Response for listing designs."""

    designs: List[DesignStatusResponse]
    total: int
    page: int
    per_page: int


class PreviewResponse(BaseModel):
    """Response for file preview."""

    design_id: str
    files: List[GeneratedFile]
    preview_url: Optional[str] = None
    can_apply: bool = True
    warnings: List[str] = Field(default_factory=list)


class ApplyDesignRequest(BaseModel):
    """Request to apply generated design to project."""

    design_id: str
    selected_files: Optional[List[str]] = Field(
        None,
        description="Specific files to apply (None = all)"
    )

    backup: bool = Field(
        True,
        description="Create backup before applying"
    )

    overwrite_existing: bool = Field(
        False,
        description="Overwrite existing files"
    )


class ApplyDesignResponse(BaseModel):
    """Response after applying design."""

    success: bool
    files_applied: List[str]
    files_skipped: List[str]
    backup_path: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
