"""
Palette - UI Designer Agent.

A standalone agent that generates beautiful, production-ready frontend code
for Laravel applications. Supports React, Vue, Blade, and Livewire.

Inspired by Lovable and Bolt, this agent:
- Detects the project's frontend technology
- Optimizes user prompts for best results
- Generates complete, beautiful UI components
- Streams code in real-time via SSE
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent_identity import PALETTE, get_random_thinking_message
from app.schemas.ui_designer import (
    FrontendTechStack,
    UIDesignResult,
    GeneratedFile,
    FileType,
    DesignStatus,
    OptimizedPrompt,
)
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service
from app.services.frontend_detector import get_frontend_detector
from app.services.prompt_optimizer import get_prompt_optimizer

logger = logging.getLogger(__name__)


# =============================================================================
# FILE PARSER
# =============================================================================

class FileParser:
    """Parses generated files from Claude's response."""

    FILE_PATTERN = re.compile(
        r'<file\s+path=["\']([^"\']+)["\']\s*(?:type=["\']([^"\']+)["\'])?\s*>(.*?)</file>',
        re.DOTALL
    )

    @classmethod
    def parse(cls, content: str) -> List[GeneratedFile]:
        """Parse files from Claude's response."""
        files = []

        for match in cls.FILE_PATTERN.finditer(content):
            path = match.group(1).strip()
            file_type_str = match.group(2) or "component"
            file_content = match.group(3).strip()

            # Determine file type
            file_type = cls._determine_file_type(path, file_type_str)

            # Determine language
            language = cls._determine_language(path)

            # Extract component name if applicable
            component_name = cls._extract_component_name(path, file_content, language)

            # Count lines
            line_count = len(file_content.split("\n"))

            # Extract exports
            exports = cls._extract_exports(file_content, language)

            # Extract dependencies
            dependencies = cls._extract_dependencies(file_content, language)

            files.append(GeneratedFile(
                path=path,
                content=file_content,
                file_type=file_type,
                language=language,
                component_name=component_name,
                line_count=line_count,
                exports=exports,
                dependencies=dependencies,
            ))

        return files

    @classmethod
    def _determine_file_type(cls, path: str, type_hint: str) -> FileType:
        """Determine file type from path and hint."""
        type_map = {
            "component": FileType.COMPONENT,
            "page": FileType.PAGE,
            "layout": FileType.LAYOUT,
            "style": FileType.STYLE,
            "config": FileType.CONFIG,
            "asset": FileType.ASSET,
            "hook": FileType.HOOK,
            "utility": FileType.UTILITY,
        }

        if type_hint in type_map:
            return type_map[type_hint]

        # Infer from path
        path_lower = path.lower()
        if "/pages/" in path_lower or "/app/" in path_lower:
            return FileType.PAGE
        if "/layouts/" in path_lower:
            return FileType.LAYOUT
        if path.endswith((".css", ".scss", ".sass")):
            return FileType.STYLE
        if path.endswith((".json", ".js")) and "config" in path_lower:
            return FileType.CONFIG
        if "/hooks/" in path_lower or path_lower.startswith("use"):
            return FileType.HOOK

        return FileType.COMPONENT

    @classmethod
    def _determine_language(cls, path: str) -> str:
        """Determine programming language from file extension."""
        ext_map = {
            ".tsx": "tsx",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".js": "javascript",
            ".vue": "vue",
            ".blade.php": "blade",
            ".php": "php",
            ".css": "css",
            ".scss": "scss",
            ".json": "json",
        }

        for ext, lang in ext_map.items():
            if path.endswith(ext):
                return lang

        return "text"

    @classmethod
    def _extract_component_name(
            cls,
            path: str,
            content: str,
            language: str,
    ) -> Optional[str]:
        """Extract component name from file content or path."""
        # Try to extract from export
        if language in ("tsx", "jsx", "typescript", "javascript"):
            match = re.search(
                r"export\s+(?:default\s+)?(?:function|const)\s+(\w+)",
                content
            )
            if match:
                return match.group(1)

        elif language == "vue":
            match = re.search(r"name:\s*['\"](\w+)['\"]", content)
            if match:
                return match.group(1)

        # Fall back to file name
        from pathlib import Path
        stem = Path(path).stem
        if stem.endswith(".blade"):
            stem = stem[:-6]
        return stem if stem else None

    @classmethod
    def _extract_exports(cls, content: str, language: str) -> List[str]:
        """Extract exported symbols from file content."""
        exports = []

        if language in ("tsx", "jsx", "typescript", "javascript"):
            # Named exports
            for match in re.finditer(r"export\s+(?:const|function|class|interface|type)\s+(\w+)", content):
                exports.append(match.group(1))

            # Default export
            match = re.search(r"export\s+default\s+(?:function\s+)?(\w+)", content)
            if match:
                exports.append(f"default: {match.group(1)}")

        return exports

    @classmethod
    def _extract_dependencies(cls, content: str, language: str) -> List[str]:
        """Extract dependencies from imports."""
        dependencies = []

        if language in ("tsx", "jsx", "typescript", "javascript"):
            for match in re.finditer(r"from\s+['\"]([^'\"]+)['\"]", content):
                dep = match.group(1)
                # Only include package dependencies, not relative imports
                if not dep.startswith(".") and not dep.startswith("@/"):
                    dependencies.append(dep)

        elif language == "vue":
            for match in re.finditer(r"from\s+['\"]([^'\"]+)['\"]", content):
                dep = match.group(1)
                if not dep.startswith(".") and not dep.startswith("@/"):
                    dependencies.append(dep)

        return list(set(dependencies))


# =============================================================================
# STREAMING BUFFER
# =============================================================================

@dataclass
class StreamingState:
    """Tracks the state of streaming code generation."""

    design_id: str
    status: DesignStatus = DesignStatus.PENDING
    current_file: Optional[str] = None
    current_content: str = ""
    files_completed: List[GeneratedFile] = field(default_factory=list)
    total_chunks: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    def add_chunk(self, chunk: str) -> None:
        """Add a chunk of generated content."""
        self.current_content += chunk
        self.total_chunks += 1

    def get_duration_ms(self) -> int:
        """Get duration in milliseconds."""
        return int((datetime.utcnow() - self.started_at).total_seconds() * 1000)


# =============================================================================
# UI DESIGNER AGENT
# =============================================================================

class UIDesigner:
    """
    Palette - The UI Designer Agent.

    Generates beautiful, production-ready frontend code for Laravel projects.

    Features:
    - Automatic frontend technology detection
    - Prompt optimization for best results
    - Real-time streaming code generation
    - Support for React, Vue, Blade, Livewire
    """

    def __init__(
            self,
            db: AsyncSession,
            claude_service: Optional[ClaudeService] = None,
            event_callback: Optional[Callable[[str], Any]] = None,
    ):
        self.db = db
        self.claude = claude_service or get_claude_service()
        self.event_callback = event_callback
        self.identity = PALETTE

        # Services
        self.prompt_optimizer = get_prompt_optimizer()
        self.frontend_detector = get_frontend_detector(db)

        # Streaming state
        self._active_designs: Dict[str, StreamingState] = {}

        logger.info(f"[PALETTE] Initialized - {self.identity.personality}")

    # =========================================================================
    # MAIN DESIGN METHOD
    # =========================================================================

    async def design(
            self,
            user_prompt: str,
            project_id: str,
            design_preferences: Optional[Dict[str, Any]] = None,
            target_path: Optional[str] = None,
    ) -> UIDesignResult:
        """
        Generate UI components based on user request.

        Args:
            user_prompt: User's design request
            project_id: Project ID for tech stack detection
            design_preferences: Optional style preferences
            target_path: Optional target directory

        Returns:
            UIDesignResult with generated files
        """
        design_id = str(uuid.uuid4())
        state = StreamingState(design_id=design_id)
        self._active_designs[design_id] = state

        logger.info(f"[PALETTE] Starting design {design_id} for project {project_id}")
        await self._emit_greeting()

        try:
            # Phase 1: Detect technology stack
            state.status = DesignStatus.DETECTING
            await self._emit_thinking("Detecting your frontend technology...")

            tech_stack = await self.frontend_detector.detect(project_id)
            await self._emit_event("tech_detected", {
                "design_id": design_id,
                "tech_stack": {
                    "framework": tech_stack.primary_framework.value,
                    "css": tech_stack.css_framework.value,
                    "typescript": tech_stack.typescript,
                    "confidence": tech_stack.confidence,
                },
            })

            logger.info(
                f"[PALETTE] Detected: {tech_stack.primary_framework.value}, "
                f"confidence={tech_stack.confidence:.2f}"
            )

            # Phase 2: Optimize prompt
            state.status = DesignStatus.OPTIMIZING
            await self._emit_thinking("Optimizing your request for best results...")

            optimized = self.prompt_optimizer.optimize(
                user_prompt=user_prompt,
                tech_stack=tech_stack,
                design_preferences=design_preferences,
            )

            await self._emit_event("prompt_optimized", {
                "design_id": design_id,
                "enhancements": optimized.enhancements_applied,
                "estimated_tokens": optimized.context_tokens_estimate,
            })

            # Phase 3: Generate UI
            state.status = DesignStatus.GENERATING
            await self._emit_thinking("Crafting your beautiful UI...")

            files = await self._generate_ui(
                state=state,
                optimized_prompt=optimized,
                tech_stack=tech_stack,
                target_path=target_path,
            )

            # Phase 4: Build result
            state.status = DesignStatus.COMPLETED
            await self._emit_completion()

            result = self._build_result(
                design_id=design_id,
                files=files,
                tech_stack=tech_stack,
                optimized_prompt=optimized,
                state=state,
            )

            logger.info(
                f"[PALETTE] Design complete: {result.total_files} files, "
                f"{result.total_lines} lines, {result.duration_ms}ms"
            )

            return result

        except Exception as e:
            state.status = DesignStatus.FAILED
            state.error = str(e)
            logger.exception(f"[PALETTE] Design failed: {e}")

            await self._emit_error(str(e))

            return UIDesignResult(
                success=False,
                design_id=design_id,
                error=str(e),
                duration_ms=state.get_duration_ms(),
            )

        finally:
            # Cleanup
            self._active_designs.pop(design_id, None)

    # =========================================================================
    # STREAMING DESIGN METHOD
    # =========================================================================

    async def design_streaming(
            self,
            user_prompt: str,
            project_id: str,
            design_preferences: Optional[Dict[str, Any]] = None,
            target_path: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate UI with real-time streaming.

        Yields SSE events as code is generated.
        """
        design_id = str(uuid.uuid4())
        state = StreamingState(design_id=design_id)
        self._active_designs[design_id] = state

        logger.info(f"[PALETTE] Starting streaming design {design_id}")

        try:
            # Yield greeting
            yield self._create_event("design_started", {
                "design_id": design_id,
                "agent": self.identity.to_dict(),
                "message": self.identity.get_random_greeting(),
            })

            # Phase 1: Detect technology
            state.status = DesignStatus.DETECTING
            yield self._create_event("agent_thinking", {
                "design_id": design_id,
                "thought": "Detecting your frontend technology...",
            })

            tech_stack = await self.frontend_detector.detect(project_id)

            yield self._create_event("tech_detected", {
                "design_id": design_id,
                "tech_stack": {
                    "framework": tech_stack.primary_framework.value,
                    "css": tech_stack.css_framework.value,
                    "typescript": tech_stack.typescript,
                    "ui_libraries": [lib.value for lib in tech_stack.ui_libraries],
                    "component_path": tech_stack.component_path,
                    "dark_mode": tech_stack.dark_mode_supported,
                    "confidence": tech_stack.confidence,
                },
            })

            # Phase 2: Optimize prompt
            state.status = DesignStatus.OPTIMIZING
            yield self._create_event("agent_thinking", {
                "design_id": design_id,
                "thought": "Optimizing your request for best results...",
            })

            optimized = self.prompt_optimizer.optimize(
                user_prompt=user_prompt,
                tech_stack=tech_stack,
                design_preferences=design_preferences,
            )

            yield self._create_event("prompt_optimized", {
                "design_id": design_id,
                "enhancements": optimized.enhancements_applied,
                "requirements": optimized.detected_requirements,
            })

            # Phase 3: Generate UI with streaming
            state.status = DesignStatus.GENERATING
            yield self._create_event("generation_started", {
                "design_id": design_id,
                "message": "Generating your UI components...",
            })

            # Stream generation
            async for event in self._stream_generation(
                    state=state,
                    optimized_prompt=optimized,
                    tech_stack=tech_stack,
                    target_path=target_path,
            ):
                yield event

            # Phase 4: Complete
            state.status = DesignStatus.COMPLETED

            result = self._build_result(
                design_id=design_id,
                files=state.files_completed,
                tech_stack=tech_stack,
                optimized_prompt=optimized,
                state=state,
            )

            yield self._create_event("design_complete", {
                "design_id": design_id,
                "result": {
                    "success": result.success,
                    "total_files": result.total_files,
                    "total_lines": result.total_lines,
                    "components_created": result.components_created,
                    "dependencies_added": result.dependencies_added,
                    "duration_ms": result.duration_ms,
                },
                "files": [
                    {
                        "path": f.path,
                        "type": f.file_type.value,
                        "language": f.language,
                        "line_count": f.line_count,
                        "component_name": f.component_name,
                    }
                    for f in result.files
                ],
                "message": self.identity.get_random_completion(),
            })

        except Exception as e:
            state.status = DesignStatus.FAILED
            state.error = str(e)
            logger.exception(f"[PALETTE] Streaming design failed: {e}")

            yield self._create_event("error", {
                "design_id": design_id,
                "error": str(e),
                "message": self.identity.get_random_error(),
            })

        finally:
            self._active_designs.pop(design_id, None)

    # =========================================================================
    # GENERATION METHODS
    # =========================================================================

    async def _generate_ui(
            self,
            state: StreamingState,
            optimized_prompt: OptimizedPrompt,
            tech_stack: FrontendTechStack,
            target_path: Optional[str] = None,
    ) -> List[GeneratedFile]:
        """Generate UI components (non-streaming)."""
        messages = [
            {"role": "user", "content": optimized_prompt.optimized_prompt}
        ]

        # Call Claude
        response = await self.claude.chat_async(
            model=ClaudeModel.SONNET,
            messages=messages,
            system=optimized_prompt.system_prompt,
            max_tokens=8192,
            temperature=0.7,
        )

        # Parse files from response
        files = FileParser.parse(response)

        # Apply target path if specified
        if target_path and files:
            files = self._apply_target_path(files, target_path, tech_stack)

        return files

    async def _stream_generation(
            self,
            state: StreamingState,
            optimized_prompt: OptimizedPrompt,
            tech_stack: FrontendTechStack,
            target_path: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream UI generation with real-time code chunks."""
        messages = [
            {"role": "user", "content": optimized_prompt.optimized_prompt}
        ]

        accumulated_content = ""
        current_file_start = -1
        files_parsed = []

        # Stream from Claude
        async for chunk in self.claude.stream_cached(
                model=ClaudeModel.SONNET,
                messages=messages,
                system=optimized_prompt.system_prompt,
                max_tokens=8192,
                temperature=0.7,
                request_type="ui_design",
        ):
            accumulated_content += chunk
            state.add_chunk(chunk)

            # Emit code chunk
            yield self._create_event("code_chunk", {
                "design_id": state.design_id,
                "chunk": chunk,
                "chunk_index": state.total_chunks,
                "accumulated_length": len(accumulated_content),
            })

            # Try to parse completed files
            new_files = FileParser.parse(accumulated_content)
            if len(new_files) > len(files_parsed):
                # New file completed
                for i in range(len(files_parsed), len(new_files)):
                    file = new_files[i]

                    # Apply target path
                    if target_path:
                        file = self._apply_target_path_to_file(
                            file, target_path, tech_stack
                        )

                    state.files_completed.append(file)

                    yield self._create_event("file_ready", {
                        "design_id": state.design_id,
                        "file": {
                            "path": file.path,
                            "type": file.file_type.value,
                            "language": file.language,
                            "line_count": file.line_count,
                            "component_name": file.component_name,
                            "content": file.content,
                        },
                        "file_index": len(state.files_completed),
                        "message": f"Generated {file.component_name or file.path}",
                    })

                files_parsed = new_files

            # Emit periodic thinking updates
            if state.total_chunks % 20 == 0:
                yield self._create_event("agent_thinking", {
                    "design_id": state.design_id,
                    "thought": get_random_thinking_message("design"),
                    "progress": min(0.9, len(files_parsed) * 0.2),
                })

        # Parse any remaining files
        final_files = FileParser.parse(accumulated_content)
        for i in range(len(files_parsed), len(final_files)):
            file = final_files[i]
            if target_path:
                file = self._apply_target_path_to_file(file, target_path, tech_stack)
            state.files_completed.append(file)

            yield self._create_event("file_ready", {
                "design_id": state.design_id,
                "file": {
                    "path": file.path,
                    "type": file.file_type.value,
                    "language": file.language,
                    "line_count": file.line_count,
                    "component_name": file.component_name,
                    "content": file.content,
                },
                "file_index": len(state.files_completed),
            })

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _apply_target_path(
            self,
            files: List[GeneratedFile],
            target_path: str,
            tech_stack: FrontendTechStack,
    ) -> List[GeneratedFile]:
        """Apply target path prefix to generated files."""
        return [
            self._apply_target_path_to_file(f, target_path, tech_stack)
            for f in files
        ]

    def _apply_target_path_to_file(
            self,
            file: GeneratedFile,
            target_path: str,
            tech_stack: FrontendTechStack,
    ) -> GeneratedFile:
        """Apply target path to a single file."""
        # Don't modify absolute paths or paths that already match structure
        if file.path.startswith(target_path):
            return file

        # Construct new path
        from pathlib import Path
        original_path = Path(file.path)

        # Try to preserve relative structure
        if "components" in file.path.lower():
            # Keep component structure
            idx = file.path.lower().find("components")
            relative_part = file.path[idx:]
            new_path = f"{target_path.rstrip('/')}/{relative_part}"
        else:
            # Place in target directly
            new_path = f"{target_path.rstrip('/')}/{original_path.name}"

        return GeneratedFile(
            path=new_path,
            content=file.content,
            file_type=file.file_type,
            language=file.language,
            component_name=file.component_name,
            line_count=file.line_count,
            exports=file.exports,
            dependencies=file.dependencies,
        )

    def _build_result(
            self,
            design_id: str,
            files: List[GeneratedFile],
            tech_stack: FrontendTechStack,
            optimized_prompt: OptimizedPrompt,
            state: StreamingState,
    ) -> UIDesignResult:
        """Build the final design result."""
        # Extract component names
        components_created = [
            f.component_name
            for f in files
            if f.component_name and f.file_type == FileType.COMPONENT
        ]

        # Extract style files
        styles_generated = [
            f.path
            for f in files
            if f.file_type == FileType.STYLE
        ]

        # Collect all dependencies
        all_deps = set()
        for f in files:
            all_deps.update(f.dependencies)

        # Calculate totals
        total_lines = sum(f.line_count for f in files)

        return UIDesignResult(
            success=True,
            design_id=design_id,
            files=files,
            design_summary=f"Created {len(files)} files with {total_lines} lines of code",
            components_created=components_created,
            styles_generated=styles_generated,
            dependencies_added=list(all_deps),
            preview_available=False,  # TODO: Implement preview
            total_tokens_used=optimized_prompt.context_tokens_estimate,
            total_files=len(files),
            total_lines=total_lines,
            tech_stack=tech_stack,
            optimized_prompt=optimized_prompt,
            duration_ms=state.get_duration_ms(),
        )

    # =========================================================================
    # EVENT EMISSION
    # =========================================================================

    def _create_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an event dictionary."""
        return {
            "event": event_type,
            "data": {
                **data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event via callback if available."""
        if self.event_callback:
            event = self._create_event(event_type, data)
            try:
                result = self.event_callback(json.dumps(event))
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"[PALETTE] Event callback error: {e}")

    async def _emit_greeting(self) -> None:
        """Emit a greeting event."""
        await self._emit_event("agent_message", {
            "agent": self.identity.to_dict(),
            "message": self.identity.get_random_greeting(),
            "message_type": "greeting",
        })

    async def _emit_thinking(self, thought: str) -> None:
        """Emit a thinking event."""
        await self._emit_event("agent_thinking", {
            "agent": self.identity.to_dict(),
            "thought": thought,
        })

    async def _emit_completion(self) -> None:
        """Emit a completion event."""
        await self._emit_event("agent_message", {
            "agent": self.identity.to_dict(),
            "message": self.identity.get_random_completion(),
            "message_type": "completion",
        })

    async def _emit_error(self, error: str) -> None:
        """Emit an error event."""
        await self._emit_event("agent_message", {
            "agent": self.identity.to_dict(),
            "message": self.identity.get_random_error(),
            "message_type": "error",
            "error": error,
        })

    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================

    def get_design_status(self, design_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of an active design."""
        state = self._active_designs.get(design_id)
        if not state:
            return None

        return {
            "design_id": design_id,
            "status": state.status.value,
            "files_completed": len(state.files_completed),
            "chunks_processed": state.total_chunks,
            "duration_ms": state.get_duration_ms(),
            "error": state.error,
        }

    async def cancel_design(self, design_id: str) -> bool:
        """Cancel an active design generation."""
        state = self._active_designs.get(design_id)
        if not state:
            return False

        state.status = DesignStatus.CANCELLED
        state.error = "Cancelled by user"

        logger.info(f"[PALETTE] Design {design_id} cancelled")
        return True


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_ui_designer(
        db: AsyncSession,
        claude_service: Optional[ClaudeService] = None,
        event_callback: Optional[Callable[[str], Any]] = None,
) -> UIDesigner:
    """Create a UI Designer agent instance."""
    return UIDesigner(
        db=db,
        claude_service=claude_service,
        event_callback=event_callback,
    )
