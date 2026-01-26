"""
Frontend Technology Detector Service

Detects Laravel project's frontend technology stack by analyzing:
- package.json for React/Vue dependencies
- composer.json for Livewire/Inertia
- Project files and directory structure
- CSS framework (Tailwind, Bootstrap, etc.)
- UI component libraries (shadcn, Headless UI, etc.)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import IndexedFile

logger = logging.getLogger(__name__)


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
    VANILLA = "vanilla"
    UNKNOWN = "unknown"


@dataclass
class DesignTokens:
    """Extracted design tokens from the project."""
    colors: Dict[str, Any] = field(default_factory=dict)
    spacing: Dict[str, str] = field(default_factory=dict)
    typography: Dict[str, Any] = field(default_factory=dict)
    border_radius: Dict[str, str] = field(default_factory=dict)
    shadows: Dict[str, str] = field(default_factory=dict)
    breakpoints: Dict[str, str] = field(default_factory=dict)
    css_variables: Dict[str, str] = field(default_factory=dict)

    def to_prompt_string(self) -> str:
        """Convert design tokens to prompt-friendly format."""
        parts = []

        if self.colors:
            parts.append("<colors>")
            for name, value in self.colors.items():
                if isinstance(value, dict):
                    for shade, hex_val in value.items():
                        parts.append(f"  {name}-{shade}: {hex_val}")
                else:
                    parts.append(f"  {name}: {value}")
            parts.append("</colors>")

        if self.spacing:
            parts.append("<spacing>")
            for name, value in list(self.spacing.items())[:10]:
                parts.append(f"  {name}: {value}")
            parts.append("</spacing>")

        if self.typography:
            parts.append("<typography>")
            for name, value in self.typography.items():
                parts.append(f"  {name}: {value}")
            parts.append("</typography>")

        if self.css_variables:
            parts.append("<css_variables>")
            for name, value in list(self.css_variables.items())[:20]:
                parts.append(f"  {name}: {value}")
            parts.append("</css_variables>")

        return "\n".join(parts) if parts else "<no_design_tokens_found/>"


@dataclass
class ExistingComponent:
    """Represents an existing component in the project."""
    name: str
    file_path: str
    component_type: str  # page, component, layout, etc.
    props: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)


@dataclass
class FrontendDetectionResult:
    """Result of frontend technology detection."""
    primary_framework: FrontendFramework
    css_framework: CSSFramework
    ui_libraries: List[str] = field(default_factory=list)
    component_path: str = "resources/js/Components"
    page_path: str = "resources/js/Pages"
    style_path: str = "resources/css"
    uses_typescript: bool = False
    uses_inertia: bool = False
    uses_ssr: bool = False
    design_tokens: DesignTokens = field(default_factory=DesignTokens)
    existing_components: List[ExistingComponent] = field(default_factory=list)
    package_json: Dict[str, Any] = field(default_factory=dict)
    tailwind_config: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "primary_framework": self.primary_framework.value,
            "css_framework": self.css_framework.value,
            "ui_libraries": self.ui_libraries,
            "component_path": self.component_path,
            "page_path": self.page_path,
            "style_path": self.style_path,
            "uses_typescript": self.uses_typescript,
            "uses_inertia": self.uses_inertia,
            "uses_ssr": self.uses_ssr,
            "design_tokens": {
                "colors": self.design_tokens.colors,
                "spacing": self.design_tokens.spacing,
                "typography": self.design_tokens.typography,
                "css_variables": self.design_tokens.css_variables,
            },
            "existing_components_count": len(self.existing_components),
        }


class FrontendDetector:
    """
    Detects frontend technology stack in Laravel projects.

    Analyzes indexed files to determine:
    - Primary frontend framework (React, Vue, Blade, Livewire)
    - CSS framework (Tailwind, Bootstrap, etc.)
    - UI component libraries
    - Design tokens and patterns
    - Existing component structure
    """

    def __init__(self, db: AsyncSession):
        """Initialize the detector with database session."""
        self.db = db

    async def detect(self, project_id: str) -> FrontendDetectionResult:
        """
        Detect frontend technology for a project.

        Args:
            project_id: The project UUID

        Returns:
            FrontendDetectionResult with all detected information
        """
        logger.info(f"[FRONTEND_DETECTOR] Starting detection for project={project_id}")

        result = FrontendDetectionResult(
            primary_framework=FrontendFramework.UNKNOWN,
            css_framework=CSSFramework.UNKNOWN,
        )

        # Load key configuration files
        package_json = await self._get_file_content(project_id, "package.json")
        composer_json = await self._get_file_content(project_id, "composer.json")
        tailwind_config = await self._get_tailwind_config(project_id)
        app_css = await self._get_file_content(project_id, "resources/css/app.css")

        # Parse package.json
        if package_json:
            try:
                result.package_json = json.loads(package_json)
            except json.JSONDecodeError:
                logger.warning("[FRONTEND_DETECTOR] Failed to parse package.json")

        # Detect primary framework
        result.primary_framework = await self._detect_framework(
            project_id, result.package_json, composer_json
        )

        # Detect CSS framework
        result.css_framework = self._detect_css_framework(
            result.package_json, tailwind_config
        )

        # Detect UI libraries
        result.ui_libraries = self._detect_ui_libraries(result.package_json)

        # Detect TypeScript usage
        result.uses_typescript = self._detect_typescript(project_id, result.package_json)

        # Detect Inertia.js usage
        result.uses_inertia = self._detect_inertia(result.package_json, composer_json)

        # Set component paths based on framework
        result.component_path, result.page_path = self._get_component_paths(
            result.primary_framework, result.uses_inertia
        )

        # Extract design tokens
        if tailwind_config:
            result.tailwind_config = tailwind_config
            result.design_tokens = self._extract_design_tokens(tailwind_config, app_css)

        # Find existing components
        result.existing_components = await self._find_existing_components(
            project_id, result.primary_framework, result.component_path
        )

        logger.info(
            f"[FRONTEND_DETECTOR] Detection complete: "
            f"framework={result.primary_framework.value}, "
            f"css={result.css_framework.value}, "
            f"libraries={result.ui_libraries}, "
            f"typescript={result.uses_typescript}, "
            f"components={len(result.existing_components)}"
        )

        return result

    async def _get_file_content(
        self, project_id: str, file_path: str
    ) -> Optional[str]:
        """Get file content from indexed files."""
        # Try exact path first
        stmt = select(IndexedFile).where(
            IndexedFile.project_id == project_id,
            IndexedFile.file_path == file_path,
        )
        result = await self.db.execute(stmt)
        indexed_file = result.scalar_one_or_none()

        if indexed_file and indexed_file.content:
            return indexed_file.content

        # Try with leading slash variations
        for path_variant in [f"/{file_path}", file_path.lstrip("/")]:
            stmt = select(IndexedFile).where(
                IndexedFile.project_id == project_id,
                IndexedFile.file_path.like(f"%{path_variant}"),
            )
            result = await self.db.execute(stmt)
            indexed_file = result.scalar_one_or_none()
            if indexed_file and indexed_file.content:
                return indexed_file.content

        return None

    async def _get_tailwind_config(self, project_id: str) -> Optional[str]:
        """Get Tailwind config file content."""
        # Try different possible names
        config_names = [
            "tailwind.config.js",
            "tailwind.config.ts",
            "tailwind.config.cjs",
            "tailwind.config.mjs",
        ]

        for name in config_names:
            content = await self._get_file_content(project_id, name)
            if content:
                return content

        return None

    async def _detect_framework(
        self,
        project_id: str,
        package_json: Dict[str, Any],
        composer_json: Optional[str],
    ) -> FrontendFramework:
        """Detect the primary frontend framework."""
        deps = {}
        if package_json:
            deps = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {}),
            }

        # Check for React
        if "react" in deps or "@types/react" in deps:
            logger.info("[FRONTEND_DETECTOR] Detected React")
            return FrontendFramework.REACT

        # Check for Vue
        if "vue" in deps or "@vue/compiler-sfc" in deps:
            logger.info("[FRONTEND_DETECTOR] Detected Vue")
            return FrontendFramework.VUE

        # Check for Livewire in composer.json
        if composer_json:
            try:
                composer_data = json.loads(composer_json)
                require = {
                    **composer_data.get("require", {}),
                    **composer_data.get("require-dev", {}),
                }
                if "livewire/livewire" in require:
                    logger.info("[FRONTEND_DETECTOR] Detected Livewire")
                    return FrontendFramework.LIVEWIRE
            except json.JSONDecodeError:
                pass

        # Check for Blade files
        stmt = select(IndexedFile).where(
            IndexedFile.project_id == project_id,
            IndexedFile.file_path.like("%.blade.php"),
        ).limit(1)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            logger.info("[FRONTEND_DETECTOR] Detected Blade")
            return FrontendFramework.BLADE

        return FrontendFramework.UNKNOWN

    def _detect_css_framework(
        self,
        package_json: Dict[str, Any],
        tailwind_config: Optional[str],
    ) -> CSSFramework:
        """Detect the CSS framework."""
        deps = {}
        if package_json:
            deps = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {}),
            }

        # Check for Tailwind
        if "tailwindcss" in deps or tailwind_config:
            return CSSFramework.TAILWIND

        # Check for Bootstrap
        if "bootstrap" in deps or "react-bootstrap" in deps or "bootstrap-vue" in deps:
            return CSSFramework.BOOTSTRAP

        return CSSFramework.VANILLA

    def _detect_ui_libraries(self, package_json: Dict[str, Any]) -> List[str]:
        """Detect UI component libraries."""
        libraries = []

        if not package_json:
            return libraries

        deps = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }

        # React UI libraries
        ui_lib_patterns = {
            "@radix-ui": "Radix UI",
            "class-variance-authority": "shadcn/ui",
            "@headlessui/react": "Headless UI",
            "@heroicons/react": "Heroicons",
            "lucide-react": "Lucide Icons",
            "@chakra-ui": "Chakra UI",
            "@mui/material": "Material UI",
            "antd": "Ant Design",
            # Vue UI libraries
            "@headlessui/vue": "Headless UI",
            "primevue": "PrimeVue",
            "vuetify": "Vuetify",
            "element-plus": "Element Plus",
            "naive-ui": "Naive UI",
            # General
            "framer-motion": "Framer Motion",
            "react-icons": "React Icons",
            "@tanstack/react-table": "TanStack Table",
            "recharts": "Recharts",
            "chart.js": "Chart.js",
            "react-chartjs-2": "React Chart.js",
        }

        for dep_pattern, lib_name in ui_lib_patterns.items():
            for dep in deps:
                if dep.startswith(dep_pattern) or dep == dep_pattern:
                    if lib_name not in libraries:
                        libraries.append(lib_name)

        return libraries

    def _detect_typescript(
        self, project_id: str, package_json: Dict[str, Any]
    ) -> bool:
        """Detect if project uses TypeScript."""
        if not package_json:
            return False

        deps = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }

        return "typescript" in deps or "@types/react" in deps or "@types/node" in deps

    def _detect_inertia(
        self, package_json: Dict[str, Any], composer_json: Optional[str]
    ) -> bool:
        """Detect if project uses Inertia.js."""
        # Check package.json
        if package_json:
            deps = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {}),
            }
            if "@inertiajs/react" in deps or "@inertiajs/vue3" in deps or "@inertiajs/inertia" in deps:
                return True

        # Check composer.json
        if composer_json:
            try:
                composer_data = json.loads(composer_json)
                require = {
                    **composer_data.get("require", {}),
                    **composer_data.get("require-dev", {}),
                }
                if "inertiajs/inertia-laravel" in require:
                    return True
            except json.JSONDecodeError:
                pass

        return False

    def _get_component_paths(
        self, framework: FrontendFramework, uses_inertia: bool
    ) -> tuple[str, str]:
        """Get component and page paths based on framework."""
        if framework == FrontendFramework.REACT:
            if uses_inertia:
                return "resources/js/Components", "resources/js/Pages"
            return "resources/js/components", "resources/js/pages"

        elif framework == FrontendFramework.VUE:
            if uses_inertia:
                return "resources/js/Components", "resources/js/Pages"
            return "resources/js/components", "resources/js/pages"

        elif framework == FrontendFramework.BLADE:
            return "resources/views/components", "resources/views"

        elif framework == FrontendFramework.LIVEWIRE:
            return "resources/views/livewire", "resources/views"

        return "resources/js/components", "resources/js/pages"

    def _extract_design_tokens(
        self, tailwind_config: str, app_css: Optional[str]
    ) -> DesignTokens:
        """Extract design tokens from Tailwind config and CSS."""
        tokens = DesignTokens()

        # Extract colors from Tailwind config
        colors_match = re.search(
            r'colors\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
            tailwind_config,
            re.DOTALL
        )
        if colors_match:
            colors_str = colors_match.group(1)
            # Parse simple color definitions
            color_patterns = re.findall(
                r"['\"]?(\w+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
                colors_str
            )
            for name, value in color_patterns:
                tokens.colors[name] = value

        # Extract theme extensions
        extend_match = re.search(
            r'extend\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
            tailwind_config,
            re.DOTALL
        )
        if extend_match:
            extend_str = extend_match.group(1)
            # Look for colors in extend
            extend_colors = re.findall(
                r"['\"]?(\w+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
                extend_str
            )
            for name, value in extend_colors:
                if name not in tokens.colors:
                    tokens.colors[name] = value

        # Extract CSS variables from app.css
        if app_css:
            css_var_pattern = re.findall(
                r'--([a-zA-Z0-9-]+)\s*:\s*([^;]+);',
                app_css
            )
            for name, value in css_var_pattern:
                tokens.css_variables[f"--{name}"] = value.strip()

        return tokens

    async def _find_existing_components(
        self,
        project_id: str,
        framework: FrontendFramework,
        component_path: str,
    ) -> List[ExistingComponent]:
        """Find existing components in the project."""
        components = []

        # Determine file extensions based on framework
        if framework == FrontendFramework.REACT:
            pattern = f"{component_path}%"
            extensions = [".tsx", ".jsx", ".ts", ".js"]
        elif framework == FrontendFramework.VUE:
            pattern = f"{component_path}%"
            extensions = [".vue"]
        elif framework in [FrontendFramework.BLADE, FrontendFramework.LIVEWIRE]:
            pattern = f"{component_path}%"
            extensions = [".blade.php"]
        else:
            return components

        # Query for component files
        stmt = select(IndexedFile).where(
            IndexedFile.project_id == project_id,
            IndexedFile.file_path.like(pattern),
        ).limit(50)

        result = await self.db.execute(stmt)
        files = result.scalars().all()

        for file in files:
            # Check if file has valid extension
            has_valid_ext = any(file.file_path.endswith(ext) for ext in extensions)
            if not has_valid_ext:
                continue

            # Extract component name from path
            name = file.file_path.split("/")[-1]
            for ext in extensions:
                name = name.replace(ext, "")

            # Determine component type
            component_type = "component"
            if "pages" in file.file_path.lower() or "page" in file.file_path.lower():
                component_type = "page"
            elif "layout" in file.file_path.lower():
                component_type = "layout"
            elif "ui" in file.file_path.lower():
                component_type = "ui"

            component = ExistingComponent(
                name=name,
                file_path=file.file_path,
                component_type=component_type,
            )

            # Try to extract props and exports from content
            if file.content:
                component.props = self._extract_props(file.content, framework)
                component.exports = self._extract_exports(file.content, framework)

            components.append(component)

        return components

    def _extract_props(self, content: str, framework: FrontendFramework) -> List[str]:
        """Extract component props from file content."""
        props = []

        if framework == FrontendFramework.REACT:
            # Look for interface/type Props
            props_match = re.search(
                r'(?:interface|type)\s+\w*Props\w*\s*(?:=\s*)?\{([^}]+)\}',
                content
            )
            if props_match:
                props_str = props_match.group(1)
                prop_names = re.findall(r'(\w+)\s*[?]?\s*:', props_str)
                props.extend(prop_names)

        elif framework == FrontendFramework.VUE:
            # Look for defineProps
            props_match = re.search(
                r'defineProps\s*<\s*\{([^}]+)\}',
                content
            )
            if props_match:
                props_str = props_match.group(1)
                prop_names = re.findall(r'(\w+)\s*[?]?\s*:', props_str)
                props.extend(prop_names)

        elif framework == FrontendFramework.BLADE:
            # Look for @props directive
            props_match = re.search(
                r'@props\s*\(\s*\[([^\]]+)\]',
                content
            )
            if props_match:
                props_str = props_match.group(1)
                prop_names = re.findall(r"['\"](\w+)['\"]", props_str)
                props.extend(prop_names)

        return props[:10]  # Limit to 10 props

    def _extract_exports(self, content: str, framework: FrontendFramework) -> List[str]:
        """Extract exported names from file content."""
        exports = []

        if framework in [FrontendFramework.REACT, FrontendFramework.VUE]:
            # Named exports
            named_exports = re.findall(
                r'export\s+(?:const|function|class)\s+(\w+)',
                content
            )
            exports.extend(named_exports)

            # Default export
            default_match = re.search(
                r'export\s+default\s+(?:function\s+)?(\w+)',
                content
            )
            if default_match:
                exports.append(f"default:{default_match.group(1)}")

        return exports[:5]  # Limit to 5 exports


async def detect_frontend_technology(
    db: AsyncSession, project_id: str
) -> FrontendDetectionResult:
    """
    Convenience function to detect frontend technology.

    Args:
        db: Database session
        project_id: The project UUID

    Returns:
        FrontendDetectionResult with all detected information
    """
    detector = FrontendDetector(db)
    return await detector.detect(project_id)
