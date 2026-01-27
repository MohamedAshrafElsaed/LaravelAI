"""
Frontend Technology Detection Service.

Detects the frontend technology stack used in a Laravel project:
- Framework: React, Vue, Blade, Livewire
- CSS: Tailwind, Bootstrap, custom
- UI Libraries: shadcn/ui, Radix, HeadlessUI, etc.
- Design tokens: colors, spacing, typography

Also extracts existing components for context.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Project, IndexedFile
from app.schemas.ui_designer import (
    FrontendTechStack,
    FrontendFramework,
    CSSFramework,
    UILibrary,
    DesignTokens,
    ExistingComponent,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DETECTION PATTERNS
# =============================================================================

REACT_PATTERNS = [
    r"from\s+['\"]react['\"]",
    r"import\s+.*\s+from\s+['\"]react['\"]",
    r"React\.createElement",
    r"useState|useEffect|useContext|useRef",
    r"export\s+(default\s+)?function\s+\w+\s*\(",
    r"\.jsx|\.tsx",
]

VUE_PATTERNS = [
    r"from\s+['\"]vue['\"]",
    r"<template>",
    r"<script\s+setup",
    r"defineComponent",
    r"ref\(|reactive\(|computed\(",
    r"\.vue$",
]

BLADE_PATTERNS = [
    r"@extends\s*\(",
    r"@section\s*\(",
    r"@yield\s*\(",
    r"\{\{\s*\$",
    r"@include\s*\(",
    r"@component\s*\(",
    r"<x-",
]

LIVEWIRE_PATTERNS = [
    r"wire:model",
    r"wire:click",
    r"wire:submit",
    r"@livewire",
    r"extends\s+Component",
    r"Livewire\\Component",
]

TAILWIND_PATTERNS = [
    r"tailwind\.config",
    r"@tailwind\s+",
    r"class=['\"].*?(flex|grid|p-\d|m-\d|bg-|text-|rounded)",
    r"className=['\"].*?(flex|grid|p-\d|m-\d|bg-|text-|rounded)",
]

SHADCN_PATTERNS = [
    r"@/components/ui/",
    r"from\s+['\"]@/components/ui",
    r"components\.json",
    r"shadcn",
]

RADIX_PATTERNS = [
    r"@radix-ui/",
    r"from\s+['\"]@radix-ui",
]

HEADLESS_UI_PATTERNS = [
    r"@headlessui/",
    r"from\s+['\"]@headlessui",
]

ALPINE_PATTERNS = [
    r"x-data",
    r"x-show",
    r"x-bind",
    r"x-on:",
    r"@click",
    r"Alpine\.data",
]


# =============================================================================
# COLOR EXTRACTION
# =============================================================================

TAILWIND_COLOR_REGEX = re.compile(
    r"['\"]?(\w+)['\"]?\s*:\s*['\"]?(#[0-9A-Fa-f]{3,8}|rgb\([^)]+\)|hsl\([^)]+\))['\"]?",
    re.MULTILINE
)

CSS_VAR_REGEX = re.compile(
    r"--(\w[\w-]*)\s*:\s*([^;]+);",
    re.MULTILINE
)

HSL_COLOR_REGEX = re.compile(
    r"--(\w[\w-]*)\s*:\s*([\d.]+\s+[\d.]+%\s+[\d.]+%)",
    re.MULTILINE
)


# =============================================================================
# FRONTEND DETECTOR CLASS
# =============================================================================

class FrontendDetector:
    """
    Detects frontend technology stack from project files.

    Analyzes:
    - package.json for dependencies
    - composer.json for Laravel packages
    - Configuration files (tailwind.config, vite.config)
    - CSS files for design tokens
    - Component files for patterns
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        logger.info("[FRONTEND_DETECTOR] Initialized")

    async def detect(self, project_id: str) -> FrontendTechStack:
        """
        Detect the frontend technology stack for a project.

        Args:
            project_id: Project ID to analyze

        Returns:
            FrontendTechStack with detected technologies
        """
        logger.info(f"[FRONTEND_DETECTOR] Detecting stack for project={project_id}")

        # Get project and indexed files
        project = await self._get_project(project_id)
        if not project:
            logger.warning(f"[FRONTEND_DETECTOR] Project not found: {project_id}")
            return FrontendTechStack(confidence=0.0)

        # Get relevant files for analysis
        files = await self._get_indexed_files(project_id)
        if not files:
            logger.warning(f"[FRONTEND_DETECTOR] No indexed files for project: {project_id}")
            return FrontendTechStack(confidence=0.0)

        # Create file content map
        file_map = {f.file_path: f.content for f in files if f.content}

        # Detect each aspect
        primary_framework = self._detect_framework(file_map)
        css_framework = self._detect_css_framework(file_map)
        ui_libraries = self._detect_ui_libraries(file_map)
        typescript = self._detect_typescript(file_map)
        paths = self._detect_paths(file_map, primary_framework)
        design_tokens = self._extract_design_tokens(file_map)
        existing_components = self._extract_existing_components(file_map, primary_framework)
        dark_mode = self._detect_dark_mode(file_map)

        # Calculate confidence
        confidence = self._calculate_confidence(
            primary_framework, css_framework, ui_libraries, existing_components
        )

        stack = FrontendTechStack(
            primary_framework=primary_framework,
            css_framework=css_framework,
            ui_libraries=ui_libraries,
            typescript=typescript,
            component_path=paths.get("components", ""),
            style_path=paths.get("styles", ""),
            pages_path=paths.get("pages", ""),
            design_tokens=design_tokens,
            existing_components=existing_components,
            dark_mode_supported=dark_mode,
            confidence=confidence,
        )

        logger.info(
            f"[FRONTEND_DETECTOR] Detected: {primary_framework.value}, "
            f"{css_framework.value}, confidence={confidence:.2f}"
        )

        return stack

    async def detect_from_content(
        self,
        file_contents: Dict[str, str],
    ) -> FrontendTechStack:
        """
        Detect stack from provided file contents (for testing or external use).

        Args:
            file_contents: Dict of file_path -> content

        Returns:
            FrontendTechStack
        """
        primary_framework = self._detect_framework(file_contents)
        css_framework = self._detect_css_framework(file_contents)
        ui_libraries = self._detect_ui_libraries(file_contents)
        typescript = self._detect_typescript(file_contents)
        paths = self._detect_paths(file_contents, primary_framework)
        design_tokens = self._extract_design_tokens(file_contents)
        existing_components = self._extract_existing_components(file_contents, primary_framework)
        dark_mode = self._detect_dark_mode(file_contents)
        confidence = self._calculate_confidence(
            primary_framework, css_framework, ui_libraries, existing_components
        )

        return FrontendTechStack(
            primary_framework=primary_framework,
            css_framework=css_framework,
            ui_libraries=ui_libraries,
            typescript=typescript,
            component_path=paths.get("components", ""),
            style_path=paths.get("styles", ""),
            pages_path=paths.get("pages", ""),
            design_tokens=design_tokens,
            existing_components=existing_components,
            dark_mode_supported=dark_mode,
            confidence=confidence,
        )

    # =========================================================================
    # FRAMEWORK DETECTION
    # =========================================================================

    def _detect_framework(self, files: Dict[str, str]) -> FrontendFramework:
        """Detect the primary frontend framework."""
        scores = {
            FrontendFramework.REACT: 0,
            FrontendFramework.VUE: 0,
            FrontendFramework.BLADE: 0,
            FrontendFramework.LIVEWIRE: 0,
        }

        # Check package.json
        package_json = self._find_file(files, "package.json")
        if package_json:
            try:
                pkg = json.loads(package_json)
                deps = {
                    **pkg.get("dependencies", {}),
                    **pkg.get("devDependencies", {}),
                }

                if "react" in deps or "next" in deps:
                    scores[FrontendFramework.REACT] += 10
                if "vue" in deps or "nuxt" in deps:
                    scores[FrontendFramework.VUE] += 10
                if "@inertiajs/react" in deps:
                    scores[FrontendFramework.REACT] += 5
                if "@inertiajs/vue3" in deps:
                    scores[FrontendFramework.VUE] += 5

            except json.JSONDecodeError:
                pass

        # Check composer.json
        composer_json = self._find_file(files, "composer.json")
        if composer_json:
            try:
                composer = json.loads(composer_json)
                require = {
                    **composer.get("require", {}),
                    **composer.get("require-dev", {}),
                }

                if "livewire/livewire" in require:
                    scores[FrontendFramework.LIVEWIRE] += 10
                if "inertiajs/inertia-laravel" in require:
                    # Inertia detected, will be React or Vue based on JS deps
                    pass

            except json.JSONDecodeError:
                pass

        # Check file patterns
        all_content = "\n".join(content for content in files.values() if content)

        for pattern in REACT_PATTERNS:
            if re.search(pattern, all_content):
                scores[FrontendFramework.REACT] += 1

        for pattern in VUE_PATTERNS:
            if re.search(pattern, all_content):
                scores[FrontendFramework.VUE] += 1

        for pattern in BLADE_PATTERNS:
            if re.search(pattern, all_content):
                scores[FrontendFramework.BLADE] += 1

        for pattern in LIVEWIRE_PATTERNS:
            if re.search(pattern, all_content):
                scores[FrontendFramework.LIVEWIRE] += 2

        # Check file extensions
        for path in files.keys():
            if path.endswith((".jsx", ".tsx")):
                scores[FrontendFramework.REACT] += 1
            elif path.endswith(".vue"):
                scores[FrontendFramework.VUE] += 1
            elif path.endswith(".blade.php"):
                scores[FrontendFramework.BLADE] += 1

        # Get highest scoring framework
        max_score = max(scores.values())
        if max_score == 0:
            return FrontendFramework.UNKNOWN

        for framework, score in scores.items():
            if score == max_score:
                return framework

        return FrontendFramework.UNKNOWN

    def _detect_css_framework(self, files: Dict[str, str]) -> CSSFramework:
        """Detect CSS framework."""
        all_content = "\n".join(content for content in files.values() if content)

        # Check for Tailwind
        tailwind_config = self._find_file(files, "tailwind.config")
        if tailwind_config:
            return CSSFramework.TAILWIND

        for pattern in TAILWIND_PATTERNS:
            if re.search(pattern, all_content):
                return CSSFramework.TAILWIND

        # Check package.json
        package_json = self._find_file(files, "package.json")
        if package_json:
            try:
                pkg = json.loads(package_json)
                deps = {
                    **pkg.get("dependencies", {}),
                    **pkg.get("devDependencies", {}),
                }

                if "tailwindcss" in deps:
                    return CSSFramework.TAILWIND
                if "bootstrap" in deps:
                    return CSSFramework.BOOTSTRAP

            except json.JSONDecodeError:
                pass

        # Check for Bootstrap
        if "bootstrap" in all_content.lower():
            return CSSFramework.BOOTSTRAP

        return CSSFramework.CUSTOM

    def _detect_ui_libraries(self, files: Dict[str, str]) -> List[UILibrary]:
        """Detect UI component libraries."""
        libraries = []
        all_content = "\n".join(content for content in files.values() if content)

        # Check package.json
        package_json = self._find_file(files, "package.json")
        if package_json:
            try:
                pkg = json.loads(package_json)
                deps = {
                    **pkg.get("dependencies", {}),
                    **pkg.get("devDependencies", {}),
                }

                if any(k.startswith("@radix-ui") for k in deps):
                    libraries.append(UILibrary.RADIX)
                if any(k.startswith("@headlessui") for k in deps):
                    libraries.append(UILibrary.HEADLESS_UI)
                if "primevue" in deps:
                    libraries.append(UILibrary.PRIMEVUE)

            except json.JSONDecodeError:
                pass

        # Check for shadcn/ui (components.json or usage patterns)
        components_json = self._find_file(files, "components.json")
        if components_json:
            libraries.append(UILibrary.SHADCN)
        elif any(re.search(p, all_content) for p in SHADCN_PATTERNS):
            libraries.append(UILibrary.SHADCN)

        # Check for Alpine.js
        if any(re.search(p, all_content) for p in ALPINE_PATTERNS):
            libraries.append(UILibrary.ALPINE)

        return libraries if libraries else [UILibrary.NONE]

    def _detect_typescript(self, files: Dict[str, str]) -> bool:
        """Detect if TypeScript is used."""
        # Check for tsconfig
        if self._find_file(files, "tsconfig.json"):
            return True

        # Check for .ts/.tsx files
        return any(
            path.endswith((".ts", ".tsx"))
            for path in files.keys()
        )

    def _detect_dark_mode(self, files: Dict[str, str]) -> bool:
        """Detect if dark mode is supported."""
        all_content = "\n".join(content for content in files.values() if content)

        dark_patterns = [
            r"darkMode",
            r"dark:",
            r"\.dark\s+",
            r"theme.*dark",
            r"data-theme",
            r"color-scheme",
        ]

        return any(re.search(p, all_content, re.IGNORECASE) for p in dark_patterns)

    # =========================================================================
    # PATH DETECTION
    # =========================================================================

    def _detect_paths(
        self,
        files: Dict[str, str],
        framework: FrontendFramework,
    ) -> Dict[str, str]:
        """Detect component, style, and page paths."""
        paths = {
            "components": "",
            "styles": "",
            "pages": "",
        }

        file_paths = list(files.keys())

        # Framework-specific defaults
        if framework == FrontendFramework.REACT:
            # Next.js or React patterns
            for path in file_paths:
                if "/components/" in path and not paths["components"]:
                    paths["components"] = path.split("/components/")[0] + "/components"
                if "/app/" in path and not paths["pages"]:
                    paths["pages"] = path.split("/app/")[0] + "/app"
                elif "/pages/" in path and not paths["pages"]:
                    paths["pages"] = path.split("/pages/")[0] + "/pages"
                if any(x in path for x in ["/styles/", "/css/"]) and not paths["styles"]:
                    parts = path.split("/")
                    for i, part in enumerate(parts):
                        if part in ("styles", "css"):
                            paths["styles"] = "/".join(parts[:i+1])
                            break

            # Defaults for React
            if not paths["components"]:
                paths["components"] = "resources/js/Components"
            if not paths["styles"]:
                paths["styles"] = "resources/css"
            if not paths["pages"]:
                paths["pages"] = "resources/js/Pages"

        elif framework == FrontendFramework.VUE:
            for path in file_paths:
                if "/components/" in path.lower() and not paths["components"]:
                    paths["components"] = path.split("/components/")[0] + "/components"
                if "/pages/" in path.lower() and not paths["pages"]:
                    paths["pages"] = path.split("/pages/")[0] + "/pages"

            if not paths["components"]:
                paths["components"] = "resources/js/Components"
            if not paths["pages"]:
                paths["pages"] = "resources/js/Pages"

        elif framework in (FrontendFramework.BLADE, FrontendFramework.LIVEWIRE):
            paths["components"] = "resources/views/components"
            paths["pages"] = "resources/views"
            paths["styles"] = "resources/css"

        return paths

    # =========================================================================
    # DESIGN TOKEN EXTRACTION
    # =========================================================================

    def _extract_design_tokens(self, files: Dict[str, str]) -> DesignTokens:
        """Extract design tokens from configuration files."""
        tokens = DesignTokens()

        # Try to extract from tailwind.config
        tailwind_config = self._find_file(files, "tailwind.config")
        if tailwind_config:
            tokens = self._extract_tailwind_tokens(tailwind_config)

        # Try to extract from CSS files
        for path, content in files.items():
            if content and path.endswith((".css", ".scss")):
                css_tokens = self._extract_css_tokens(content)
                # Merge tokens
                tokens.colors.update(css_tokens.colors)
                if not tokens.typography:
                    tokens.typography = css_tokens.typography

        return tokens

    def _extract_tailwind_tokens(self, config_content: str) -> DesignTokens:
        """Extract tokens from Tailwind config."""
        tokens = DesignTokens()

        try:
            # Extract colors using regex (handles JS object notation)
            color_section = re.search(
                r"colors?\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}",
                config_content,
                re.DOTALL
            )

            if color_section:
                color_str = color_section.group(1)
                # Find color definitions
                for match in TAILWIND_COLOR_REGEX.finditer(color_str):
                    name, value = match.groups()
                    if name and value:
                        tokens.colors[name] = value

            # Extract spacing
            spacing_section = re.search(
                r"spacing\s*:\s*\{([^}]+)\}",
                config_content,
                re.DOTALL
            )

            if spacing_section:
                spacing_str = spacing_section.group(1)
                for match in re.finditer(r"['\"]?(\w+)['\"]?\s*:\s*['\"]?([^,'\"\n]+)", spacing_str):
                    name, value = match.groups()
                    tokens.spacing[name.strip()] = value.strip()

            # Extract border radius
            radius_section = re.search(
                r"borderRadius\s*:\s*\{([^}]+)\}",
                config_content,
                re.DOTALL
            )

            if radius_section:
                radius_str = radius_section.group(1)
                for match in re.finditer(r"['\"]?(\w+)['\"]?\s*:\s*['\"]?([^,'\"\n]+)", radius_str):
                    name, value = match.groups()
                    tokens.borders[name.strip()] = value.strip()

        except Exception as e:
            logger.warning(f"[FRONTEND_DETECTOR] Error parsing Tailwind config: {e}")

        return tokens

    def _extract_css_tokens(self, css_content: str) -> DesignTokens:
        """Extract tokens from CSS variables."""
        tokens = DesignTokens()

        # Extract CSS custom properties
        for match in CSS_VAR_REGEX.finditer(css_content):
            name, value = match.groups()
            name = name.strip()
            value = value.strip()

            # Categorize by name
            if any(x in name.lower() for x in ["color", "bg", "text", "border"]):
                tokens.colors[name] = value
            elif any(x in name.lower() for x in ["font", "text"]):
                tokens.typography[name] = value
            elif any(x in name.lower() for x in ["space", "gap", "margin", "padding"]):
                tokens.spacing[name] = value
            elif any(x in name.lower() for x in ["radius", "rounded"]):
                tokens.borders[name] = value
            elif "shadow" in name.lower():
                tokens.shadows[name] = value

        # Also try HSL format common in shadcn/ui
        for match in HSL_COLOR_REGEX.finditer(css_content):
            name, value = match.groups()
            tokens.colors[name.strip()] = f"hsl({value.strip()})"

        return tokens

    # =========================================================================
    # COMPONENT EXTRACTION
    # =========================================================================

    def _extract_existing_components(
        self,
        files: Dict[str, str],
        framework: FrontendFramework,
    ) -> List[ExistingComponent]:
        """Extract information about existing components."""
        components = []

        for path, content in files.items():
            if not content:
                continue

            # Skip non-component files
            if not self._is_component_file(path, framework):
                continue

            # Extract component info based on framework
            if framework == FrontendFramework.REACT:
                comp = self._extract_react_component(path, content)
            elif framework == FrontendFramework.VUE:
                comp = self._extract_vue_component(path, content)
            elif framework in (FrontendFramework.BLADE, FrontendFramework.LIVEWIRE):
                comp = self._extract_blade_component(path, content)
            else:
                continue

            if comp:
                components.append(comp)

        return components[:50]  # Limit to 50 components

    def _is_component_file(self, path: str, framework: FrontendFramework) -> bool:
        """Check if file is likely a component."""
        path_lower = path.lower()

        # Skip common non-component paths
        skip_patterns = [
            "node_modules",
            "vendor",
            ".git",
            "test",
            "spec",
            "__pycache__",
        ]

        if any(p in path_lower for p in skip_patterns):
            return False

        if framework == FrontendFramework.REACT:
            return path.endswith((".tsx", ".jsx")) and "/components/" in path_lower
        elif framework == FrontendFramework.VUE:
            return path.endswith(".vue") and "/components/" in path_lower
        elif framework in (FrontendFramework.BLADE, FrontendFramework.LIVEWIRE):
            return path.endswith(".blade.php") and "/components/" in path_lower

        return False

    def _extract_react_component(
        self,
        path: str,
        content: str,
    ) -> Optional[ExistingComponent]:
        """Extract React component info."""
        # Find component name from export
        export_match = re.search(
            r"export\s+(?:default\s+)?(?:function|const)\s+(\w+)",
            content
        )

        if not export_match:
            return None

        name = export_match.group(1)

        # Find props interface
        props = []
        props_match = re.search(
            r"interface\s+\w*Props\s*\{([^}]+)\}",
            content
        )

        if props_match:
            props_content = props_match.group(1)
            props = re.findall(r"(\w+)\s*[?]?\s*:", props_content)

        return ExistingComponent(
            name=name,
            path=path,
            props=props[:10],  # Limit to 10 props
        )

    def _extract_vue_component(
        self,
        path: str,
        content: str,
    ) -> Optional[ExistingComponent]:
        """Extract Vue component info."""
        # Get name from file path
        name = Path(path).stem

        # Find props
        props = []
        props_match = re.search(
            r"defineProps\s*<?\s*\{([^}]+)\}",
            content
        )

        if props_match:
            props_content = props_match.group(1)
            props = re.findall(r"(\w+)\s*[?]?\s*:", props_content)

        return ExistingComponent(
            name=name,
            path=path,
            props=props[:10],
        )

    def _extract_blade_component(
        self,
        path: str,
        content: str,
    ) -> Optional[ExistingComponent]:
        """Extract Blade component info."""
        # Get name from file path
        name = Path(path).stem

        # Find @props directive
        props = []
        props_match = re.search(
            r"@props\s*\(\s*\[([^\]]+)\]",
            content
        )

        if props_match:
            props_content = props_match.group(1)
            # Extract prop names
            props = re.findall(r"['\"](\w+)['\"]", props_content)

        return ExistingComponent(
            name=name,
            path=path,
            props=props[:10],
        )

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _find_file(
        self,
        files: Dict[str, str],
        filename: str,
    ) -> Optional[str]:
        """Find file content by filename (partial match)."""
        for path, content in files.items():
            if filename in path:
                return content
        return None

    def _calculate_confidence(
        self,
        framework: FrontendFramework,
        css: CSSFramework,
        libraries: List[UILibrary],
        components: List[ExistingComponent],
    ) -> float:
        """Calculate detection confidence score."""
        score = 0.0

        # Framework detection
        if framework != FrontendFramework.UNKNOWN:
            score += 0.4

        # CSS framework detection
        if css != CSSFramework.NONE:
            score += 0.2

        # UI libraries detection
        if libraries and libraries != [UILibrary.NONE]:
            score += 0.2

        # Existing components found
        if components:
            score += min(len(components) / 20, 0.2)  # Up to 0.2 for 20+ components

        return min(score, 1.0)

    async def _get_project(self, project_id: str) -> Optional[Project]:
        """Get project from database."""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_indexed_files(
        self,
        project_id: str,
        limit: int = 500,
    ) -> List[IndexedFile]:
        """Get indexed files for analysis."""
        # Prioritize config and component files
        stmt = (
            select(IndexedFile)
            .where(IndexedFile.project_id == project_id)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_frontend_detector(db: AsyncSession) -> FrontendDetector:
    """Create a frontend detector instance."""
    return FrontendDetector(db)
