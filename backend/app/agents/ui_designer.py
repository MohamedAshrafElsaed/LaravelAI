"""
UI Designer Agent (Palette)

Main agent for generating beautiful, production-ready UI code.
Works like Lovable/Bolt - taking user requests and generating stunning
UI components with real-time streaming preview.

Features:
- Detects Laravel project's frontend technology
- Optimizes prompts using Claude best practices
- Generates complete, production-ready UI code
- Streams code generation in real-time with SSE
- Returns all generated files for preview
"""

import asyncio
import logging
import re
import time
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any, List, Dict
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.ui_designer_identity import (
    PALETTE,
    get_ui_thinking_messages,
    get_random_ui_thinking_message,
)
from app.agents.ui_designer_events import (
    design_started,
    design_completed,
    design_error,
    tech_detection_started,
    tech_detected,
    prompt_optimization_started,
    prompt_optimized,
    design_system_loaded,
    existing_components_loaded,
    generation_started,
    component_started,
    code_chunk,
    component_completed,
    generation_completed,
    file_ready,
    palette_thinking,
    palette_message,
    progress_update,
)
from app.services.frontend_detector import (
    FrontendDetector,
    FrontendDetectionResult,
    FrontendFramework,
)
from app.services.prompt_optimizer import PromptOptimizer, OptimizedPrompt
from app.services.claude import ClaudeService, get_claude_service, ClaudeModel
from app.schemas.ui_designer import (
    UIDesignResult,
    GeneratedFile,
    DesignSummary,
    TechStackInfo,
    DesignStatus,
    FileType,
)

logger = logging.getLogger(__name__)


@dataclass
class UIDesignSession:
    """Tracks the state of a UI design session."""
    design_id: str
    project_id: str
    user_request: str
    status: DesignStatus = DesignStatus.PENDING
    detection_result: Optional[FrontendDetectionResult] = None
    optimized_prompt: Optional[OptimizedPrompt] = None
    files: List[GeneratedFile] = field(default_factory=list)
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    tokens_used: int = 0
    cancelled: bool = False


class UIDesignerAgent:
    """
    Palette - The UI Designer Agent.

    Generates beautiful, production-ready frontend code for Laravel applications.
    Supports React, Vue, Blade, and Livewire with real-time streaming.
    """

    def __init__(
        self,
        db: AsyncSession,
        event_callback: Optional[Callable[[str], Any]] = None,
        claude_service: Optional[ClaudeService] = None,
    ):
        """
        Initialize the UI Designer agent.

        Args:
            db: Database session for accessing indexed files
            event_callback: Callback for SSE events (receives formatted event strings)
            claude_service: Optional ClaudeService instance for AI generation
        """
        self.db = db
        self.event_callback = event_callback
        self.claude = claude_service or get_claude_service()
        self.frontend_detector = FrontendDetector(db)
        self.prompt_optimizer = PromptOptimizer()

        # Active sessions for cancellation support
        self._active_sessions: Dict[str, UIDesignSession] = {}

        logger.info("[UI_DESIGNER] Palette agent initialized")

    async def _emit_event(self, event_str: str) -> None:
        """Emit an SSE event string."""
        if self.event_callback:
            try:
                result = self.event_callback(event_str)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"[UI_DESIGNER] Event callback error: {e}")

    async def _emit_thinking_sequence(
        self,
        action_type: str,
        count: int = 3,
        delay: float = 0.6,
        file_path: Optional[str] = None,
    ) -> None:
        """Emit a sequence of thinking messages."""
        messages = get_ui_thinking_messages(action_type)
        if not messages:
            messages = PALETTE.thinking_phrases

        selected = random.sample(messages, min(count, len(messages)))

        for i, thought in enumerate(selected):
            progress = (i + 1) / count
            await self._emit_event(palette_thinking(
                thought=thought,
                action_type=action_type,
                file_path=file_path,
                progress=progress,
            ))
            await asyncio.sleep(delay)

    async def design(
        self,
        project_id: str,
        user_request: str,
        stream: bool = True,
    ) -> UIDesignResult:
        """
        Main design method - generates UI code based on user request.

        Args:
            project_id: The project UUID
            user_request: User's design request
            stream: Whether to stream generation progress

        Returns:
            UIDesignResult with all generated files
        """
        design_id = f"design_{uuid4().hex[:12]}"
        start_time = time.time()

        logger.info(f"[UI_DESIGNER] Starting design: {design_id} for project={project_id}")
        logger.info(f"[UI_DESIGNER] Request: {user_request[:200]}...")

        # Create session
        session = UIDesignSession(
            design_id=design_id,
            project_id=project_id,
            user_request=user_request,
        )
        self._active_sessions[design_id] = session

        try:
            # ============== PHASE 1: GREETING ==============
            await self._emit_event(palette_message(
                message=PALETTE.get_random_greeting(),
                message_type="greeting",
            ))
            await asyncio.sleep(0.3)

            await self._emit_event(design_started(
                design_id=design_id,
                request=user_request,
            ))

            # ============== PHASE 2: DETECT TECHNOLOGY ==============
            session.status = DesignStatus.DETECTING

            await self._emit_event(tech_detection_started())
            await self._emit_thinking_sequence("detecting", count=2)

            if session.cancelled:
                return self._cancelled_result(session)

            detection_result = await self.frontend_detector.detect(project_id)
            session.detection_result = detection_result

            await self._emit_event(tech_detected(
                framework=detection_result.primary_framework.value,
                css_framework=detection_result.css_framework.value,
                ui_libraries=detection_result.ui_libraries,
                uses_typescript=detection_result.uses_typescript,
            ))

            # Emit design system info
            colors_count = len(detection_result.design_tokens.colors)
            await self._emit_event(design_system_loaded(
                colors_count=colors_count,
                tokens_loaded=bool(colors_count > 0 or detection_result.design_tokens.css_variables),
            ))

            # Emit existing components info
            component_names = [c.name for c in detection_result.existing_components[:10]]
            await self._emit_event(existing_components_loaded(
                components_count=len(detection_result.existing_components),
                component_names=component_names,
            ))

            if session.cancelled:
                return self._cancelled_result(session)

            # ============== PHASE 3: OPTIMIZE PROMPT ==============
            session.status = DesignStatus.OPTIMIZING

            await self._emit_event(prompt_optimization_started())
            await self._emit_thinking_sequence("analyzing", count=2)

            optimized = self.prompt_optimizer.optimize(user_request, detection_result)
            session.optimized_prompt = optimized

            await self._emit_event(prompt_optimized(
                enhancements=optimized.enhancements_applied,
                estimated_tokens=optimized.estimated_tokens,
            ))

            await self._emit_event(progress_update(
                phase="preparation",
                progress=0.2,
                message="Ready to generate UI code...",
            ))

            if session.cancelled:
                return self._cancelled_result(session)

            # ============== PHASE 4: GENERATE CODE ==============
            session.status = DesignStatus.GENERATING

            await self._emit_event(palette_message(
                message="Starting to craft your beautiful UI...",
                message_type="thinking",
            ))

            await self._emit_thinking_sequence("planning", count=2)

            # Generate UI code with streaming
            files = await self._generate_ui_code(
                session=session,
                detection_result=detection_result,
                optimized_prompt=optimized,
                stream=stream,
            )

            session.files = files

            if session.cancelled:
                return self._cancelled_result(session)

            # ============== PHASE 5: COMPLETE ==============
            session.status = DesignStatus.COMPLETED
            session.completed_at = datetime.utcnow()

            # Calculate stats
            total_lines = sum(f.lines_of_code for f in files)
            generation_time_ms = int((time.time() - start_time) * 1000)

            # Build summary
            summary = DesignSummary(
                total_files=len(files),
                total_lines=total_lines,
                components_created=[f.path.split("/")[-1].replace(".tsx", "").replace(".vue", "").replace(".blade.php", "") for f in files if f.file_type == FileType.COMPONENT],
                styles_generated=[f.path for f in files if f.file_type == FileType.STYLE],
                dependencies_added=list(set(dep for f in files for dep in f.dependencies)),
            )

            # Build tech stack info
            tech_stack = TechStackInfo(
                primary_framework=detection_result.primary_framework.value,
                css_framework=detection_result.css_framework.value,
                ui_libraries=detection_result.ui_libraries,
                uses_typescript=detection_result.uses_typescript,
                uses_inertia=detection_result.uses_inertia,
                component_path=detection_result.component_path,
                page_path=detection_result.page_path,
            )

            await self._emit_event(design_completed(
                design_id=design_id,
                files_count=len(files),
                components_count=len(summary.components_created),
            ))

            await self._emit_event(palette_message(
                message=PALETTE.get_random_completion(),
                message_type="completion",
            ))

            # Cleanup session
            del self._active_sessions[design_id]

            return UIDesignResult(
                success=True,
                design_id=design_id,
                status=DesignStatus.COMPLETED,
                files=files,
                summary=summary,
                tech_stack=tech_stack,
                tokens_used=session.tokens_used,
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.exception(f"[UI_DESIGNER] Design failed: {e}")
            session.status = DesignStatus.FAILED
            session.error = str(e)

            await self._emit_event(design_error(
                design_id=design_id,
                error=str(e),
            ))

            await self._emit_event(palette_message(
                message=PALETTE.get_random_error(),
                message_type="error",
            ))

            # Cleanup session
            if design_id in self._active_sessions:
                del self._active_sessions[design_id]

            return UIDesignResult(
                success=False,
                design_id=design_id,
                status=DesignStatus.FAILED,
                files=[],
                summary=DesignSummary(),
                error=str(e),
                generation_time_ms=int((time.time() - start_time) * 1000),
            )

    async def _generate_ui_code(
        self,
        session: UIDesignSession,
        detection_result: FrontendDetectionResult,
        optimized_prompt: OptimizedPrompt,
        stream: bool = True,
    ) -> List[GeneratedFile]:
        """
        Generate UI code using Claude.

        Args:
            session: Current design session
            detection_result: Frontend technology detection
            optimized_prompt: Optimized prompt for generation
            stream: Whether to stream generation

        Returns:
            List of generated files
        """
        logger.info(f"[UI_DESIGNER] Generating code for {session.design_id}")

        # Prepare messages for Claude
        messages = [
            {"role": "user", "content": optimized_prompt.optimized_prompt}
        ]

        # Generate with Claude
        session.status = DesignStatus.STREAMING if stream else DesignStatus.GENERATING

        await self._emit_event(generation_started(total_files=0))

        # Collect full response
        full_response = ""

        if stream:
            # Stream the response
            async for chunk in self.claude.stream_cached(
                model=ClaudeModel.SONNET,
                messages=messages,
                system=optimized_prompt.system_prompt,
                temperature=0.3,
                max_tokens=16000,
                request_type="ui_design",
            ):
                full_response += chunk

                # Stream progress updates periodically
                if len(full_response) % 500 == 0:
                    await self._emit_event(progress_update(
                        phase="generating",
                        progress=0.3 + (0.5 * min(len(full_response) / 10000, 1.0)),
                        message="Generating code...",
                        details={"chars_generated": len(full_response)},
                    ))
        else:
            # Non-streaming generation
            full_response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=messages,
                system=optimized_prompt.system_prompt,
                temperature=0.3,
                max_tokens=16000,
                request_type="ui_design",
            )

        if session.cancelled:
            return []

        # Parse generated files from response
        files = self._parse_generated_files(full_response, detection_result)

        # Emit events for each file
        total_files = len(files)
        for i, file in enumerate(files):
            if session.cancelled:
                return files[:i]

            # Emit file events
            component_name = file.path.split("/")[-1]
            await self._emit_event(component_started(
                component_name=component_name,
                component_index=i,
                total_components=total_files,
                file_path=file.path,
            ))

            # Stream file content in chunks
            if stream:
                await self._stream_file_content(
                    file_path=file.path,
                    content=file.content,
                    chunk_size=200,
                    delay=0.02,
                )

            await self._emit_event(component_completed(
                component_name=component_name,
                component_index=i,
                total_components=total_files,
                file_path=file.path,
                lines_of_code=file.lines_of_code,
            ))

            await self._emit_event(file_ready(
                file_path=file.path,
                file_type=file.file_type.value,
                language=file.language,
            ))

        # Emit generation completed
        total_lines = sum(f.lines_of_code for f in files)
        await self._emit_event(generation_completed(
            total_files=len(files),
            total_lines=total_lines,
        ))

        return files

    async def _stream_file_content(
        self,
        file_path: str,
        content: str,
        chunk_size: int = 200,
        delay: float = 0.02,
    ) -> None:
        """Stream file content in chunks for real-time display."""
        if not content:
            return

        total_length = len(content)
        accumulated = ""
        chunk_index = 0

        for i in range(0, total_length, chunk_size):
            chunk_text = content[i:i + chunk_size]
            accumulated += chunk_text
            chunk_index += 1

            await self._emit_event(code_chunk(
                file_path=file_path,
                chunk=chunk_text,
                chunk_index=chunk_index,
                accumulated_length=len(accumulated),
                total_length=total_length,
                done=False,
            ))

            await asyncio.sleep(delay)

        # Emit final done event
        await self._emit_event(code_chunk(
            file_path=file_path,
            chunk="",
            chunk_index=chunk_index + 1,
            accumulated_length=total_length,
            total_length=total_length,
            done=True,
            content=content,
        ))

    def _parse_generated_files(
        self,
        response: str,
        detection_result: FrontendDetectionResult,
    ) -> List[GeneratedFile]:
        """
        Parse generated files from Claude's response.

        Expects format:
        <file path="path/to/file.tsx" type="component">
        content here
        </file>
        """
        files = []

        # Pattern to match file blocks
        file_pattern = re.compile(
            r'<file\s+path=["\']([^"\']+)["\']\s*(?:type=["\']([^"\']+)["\'])?\s*>(.*?)</file>',
            re.DOTALL
        )

        matches = file_pattern.findall(response)

        for match in matches:
            file_path = match[0].strip()
            file_type_str = match[1].strip() if match[1] else "component"
            content = match[2].strip()

            # Determine file type
            file_type = FileType.COMPONENT
            if file_type_str:
                try:
                    file_type = FileType(file_type_str.lower())
                except ValueError:
                    pass

            # Also detect from path
            if "style" in file_path.lower() or file_path.endswith(".css"):
                file_type = FileType.STYLE
            elif "layout" in file_path.lower():
                file_type = FileType.LAYOUT
            elif "page" in file_path.lower():
                file_type = FileType.PAGE
            elif "hook" in file_path.lower() or file_path.startswith("use"):
                file_type = FileType.HOOK
            elif "type" in file_path.lower() or "interface" in file_path.lower():
                file_type = FileType.TYPE

            # Determine language
            language = self._get_language_from_path(file_path, detection_result)

            # Count lines
            lines_of_code = len(content.splitlines())

            # Extract dependencies
            dependencies = self._extract_dependencies(content, detection_result)

            files.append(GeneratedFile(
                path=file_path,
                content=content,
                file_type=file_type,
                language=language,
                lines_of_code=lines_of_code,
                dependencies=dependencies,
            ))

        # If no files found with <file> tags, try to extract from code blocks
        if not files:
            files = self._parse_from_code_blocks(response, detection_result)

        return files

    def _parse_from_code_blocks(
        self,
        response: str,
        detection_result: FrontendDetectionResult,
    ) -> List[GeneratedFile]:
        """Parse files from markdown code blocks as fallback."""
        files = []

        # Pattern for code blocks with file path comments
        code_block_pattern = re.compile(
            r'```(\w+)?\s*(?://|{/\*|<!--)?\s*(?:file:?\s*)?([^\s\n*/>]+(?:\.[a-z]+))\s*(?:\*/}|-->)?\n(.*?)```',
            re.DOTALL | re.IGNORECASE
        )

        matches = code_block_pattern.findall(response)

        for match in matches:
            lang = match[0] or "tsx"
            file_path = match[1].strip()
            content = match[2].strip()

            if not file_path or not content:
                continue

            # Ensure file path has component path prefix if needed
            if not file_path.startswith("resources/") and not file_path.startswith("/"):
                file_path = f"{detection_result.component_path}/{file_path}"

            language = self._get_language_from_path(file_path, detection_result)
            lines_of_code = len(content.splitlines())
            dependencies = self._extract_dependencies(content, detection_result)

            files.append(GeneratedFile(
                path=file_path,
                content=content,
                file_type=FileType.COMPONENT,
                language=language,
                lines_of_code=lines_of_code,
                dependencies=dependencies,
            ))

        return files

    def _get_language_from_path(
        self,
        file_path: str,
        detection_result: FrontendDetectionResult,
    ) -> str:
        """Determine language from file path."""
        if file_path.endswith(".tsx"):
            return "tsx"
        elif file_path.endswith(".jsx"):
            return "jsx"
        elif file_path.endswith(".ts"):
            return "typescript"
        elif file_path.endswith(".js"):
            return "javascript"
        elif file_path.endswith(".vue"):
            return "vue"
        elif file_path.endswith(".blade.php"):
            return "blade"
        elif file_path.endswith(".php"):
            return "php"
        elif file_path.endswith(".css"):
            return "css"
        elif file_path.endswith(".scss"):
            return "scss"

        # Default based on framework
        if detection_result.primary_framework == FrontendFramework.REACT:
            return "tsx" if detection_result.uses_typescript else "jsx"
        elif detection_result.primary_framework == FrontendFramework.VUE:
            return "vue"
        else:
            return "blade"

    def _extract_dependencies(
        self,
        content: str,
        detection_result: FrontendDetectionResult,
    ) -> List[str]:
        """Extract dependencies from file content."""
        dependencies = []

        # Extract npm packages from imports
        import_pattern = re.compile(r'import\s+.*?from\s+["\']([^"\'./][^"\']*)["\']')
        imports = import_pattern.findall(content)

        for imp in imports:
            # Get the package name (first part before /)
            package = imp.split("/")[0]
            if package.startswith("@"):
                package = "/".join(imp.split("/")[:2])

            if package not in dependencies:
                dependencies.append(package)

        return dependencies[:10]  # Limit to 10 dependencies

    def _cancelled_result(self, session: UIDesignSession) -> UIDesignResult:
        """Return a cancelled result."""
        return UIDesignResult(
            success=False,
            design_id=session.design_id,
            status=DesignStatus.CANCELLED,
            files=session.files,
            summary=DesignSummary(total_files=len(session.files)),
            error="Design generation was cancelled",
        )

    async def cancel(self, design_id: str) -> bool:
        """
        Cancel an ongoing design generation.

        Args:
            design_id: ID of the design to cancel

        Returns:
            True if cancelled successfully
        """
        if design_id in self._active_sessions:
            self._active_sessions[design_id].cancelled = True
            logger.info(f"[UI_DESIGNER] Cancelling design: {design_id}")
            return True
        return False

    def get_session_status(self, design_id: str) -> Optional[UIDesignSession]:
        """Get the status of a design session."""
        return self._active_sessions.get(design_id)


async def create_ui_designer(
    db: AsyncSession,
    event_callback: Optional[Callable[[str], Any]] = None,
    claude_service: Optional[ClaudeService] = None,
) -> UIDesignerAgent:
    """
    Factory function to create a UI Designer agent.

    Args:
        db: Database session
        event_callback: Optional SSE event callback
        claude_service: Optional Claude service instance

    Returns:
        Configured UIDesignerAgent instance
    """
    return UIDesignerAgent(
        db=db,
        event_callback=event_callback,
        claude_service=claude_service,
    )
