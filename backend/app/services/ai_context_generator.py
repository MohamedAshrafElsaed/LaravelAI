"""
AI Context Generator Service

Generates CLAUDE.md content and AI context for internal use.
This context helps the AI assistant understand the project better.
NOTE: This is internal - user doesn't see the raw content.
"""
import os
import json
from typing import Dict, Any, Optional, List


class AIContextGenerator:
    """Generate CLAUDE.md and AI context - INTERNAL USE ONLY."""

    def __init__(
        self,
        project_path: str,
        stack: dict,
        file_stats: dict,
        structure: dict,
    ):
        self.path = project_path
        self.stack = stack or {}
        self.file_stats = file_stats or {}
        self.structure = structure or {}

    def generate(self) -> Dict[str, Any]:
        """Generate full AI context."""
        return {
            "claude_md_content": self._generate_claude_md(),
            "key_patterns": self._extract_patterns(),
            "domain_knowledge": self._extract_domain_knowledge(),
            "conventions": self._detect_conventions(),
            "important_files": self._get_important_files_content(),
        }

    def _generate_claude_md(self) -> str:
        """Generate CLAUDE.md content for AI context."""
        backend = self.stack.get("backend", {})
        frontend = self.stack.get("frontend", {})
        by_category = self.file_stats.get("by_category", {})

        # Format packages list
        packages = backend.get("packages", {})
        packages_list = ", ".join(k for k, v in packages.items() if v) if packages else "None detected"

        content = f"""# Project Context (Auto-generated)

## Tech Stack

### Backend
- Framework: {backend.get('framework', 'unknown')} {backend.get('version', '')}
- Language: {backend.get('language', 'unknown')} {backend.get('php_version', '')}
- Database: {self.stack.get('database', 'unknown')}
- Cache: {self.stack.get('cache', 'unknown')}
- Queue: {self.stack.get('queue', 'unknown')}
- Packages: {packages_list}

### Frontend
- Framework: {frontend.get('framework', 'unknown')} {frontend.get('version', '')}
- Build Tool: {frontend.get('build_tool', 'unknown')}
- TypeScript: {'Yes' if frontend.get('typescript') else 'No'}
- UI Library: {frontend.get('ui_library') or 'None'}
- State Management: {frontend.get('state') or 'None'}
- Inertia.js: {'Yes' if frontend.get('inertia') else 'No'}

## Project Statistics
- Total Files: {self.file_stats.get('total_files', 0):,}
- Total Lines: {self.file_stats.get('total_lines', 0):,}
- Models: {by_category.get('models', 0)}
- Controllers: {by_category.get('controllers', 0)}
- Services: {by_category.get('services', 0)}
- Jobs: {by_category.get('jobs', 0)}
- Events: {by_category.get('events', 0)}
- Listeners: {by_category.get('listeners', 0)}
- Tests: {by_category.get('tests', 0)}
- Vue Components: {by_category.get('components', 0)}
- Pages/Views: {by_category.get('pages', 0) + by_category.get('views', 0)}

## Detected Architectural Patterns
{self._format_patterns()}

## Coding Conventions
{self._format_conventions()}

## Key Files
{self._format_key_files()}

## Important Rules for AI
1. NEVER rewrite entire files - show ONLY the changes needed
2. Follow existing patterns in the codebase
3. Use the same coding style (PSR-12 for PHP, existing Vue patterns)
4. {'Use TypeScript for all frontend code' if frontend.get('typescript') else 'Use JavaScript for frontend code'}
5. {'Use Composition API with <script setup>' if frontend.get('composition_api') else 'Use Options API for Vue components'}
6. {'Place business logic in Services' if by_category.get('services', 0) > 0 else 'Keep business logic organized'}
7. {'Use Form Requests for validation' if by_category.get('requests', 0) > 0 else 'Validate input appropriately'}
8. {'Use API Resources for responses' if by_category.get('resources', 0) > 0 else 'Format API responses consistently'}
9. Always handle errors gracefully
10. Write code that matches the project's existing quality standards
"""
        return content

    def _extract_patterns(self) -> List[str]:
        """Extract detected architectural patterns."""
        return self.structure.get("patterns_detected", [])

    def _format_patterns(self) -> str:
        """Format patterns for CLAUDE.md."""
        patterns = self._extract_patterns()
        if not patterns:
            return "- No specific patterns detected"

        pattern_descriptions = {
            "service-layer": "Service Layer - Business logic in dedicated service classes",
            "repository-pattern": "Repository Pattern - Data access abstraction",
            "action-classes": "Action Classes - Single-purpose action classes",
            "observer-pattern": "Observer Pattern - Model observers for side effects",
            "event-driven": "Event-Driven - Events and listeners for decoupling",
            "form-requests": "Form Requests - Dedicated request validation classes",
            "api-resources": "API Resources - Response transformation classes",
            "queue-jobs": "Queue Jobs - Background job processing",
            "policy-authorization": "Policy Authorization - Model-based authorization",
            "traits": "Traits - Shared functionality via traits",
            "enums": "PHP Enums - Type-safe enumerations",
            "domain-driven-design": "DDD - Domain-driven design structure",
            "modular-architecture": "Modular - Organized by modules/domains",
        }

        lines = []
        for pattern in patterns:
            desc = pattern_descriptions.get(pattern, pattern.replace("-", " ").title())
            lines.append(f"- {desc}")

        return "\n".join(lines)

    def _extract_domain_knowledge(self) -> Dict[str, Any]:
        """Extract domain-specific knowledge from the codebase."""
        knowledge = {
            "models": {},
            "routes": {},
            "config": {},
        }

        # Extract model information
        models_dir = os.path.join(self.path, "app/Models")
        if os.path.exists(models_dir):
            for filename in os.listdir(models_dir):
                if filename.endswith(".php") and filename != "Model.php":
                    model_name = filename.replace(".php", "")
                    model_path = os.path.join(models_dir, filename)
                    model_info = self._analyze_model(model_path)
                    if model_info:
                        knowledge["models"][model_name] = model_info

        # Extract route information
        routes_dir = os.path.join(self.path, "routes")
        if os.path.exists(routes_dir):
            for route_file in ["web.php", "api.php"]:
                route_path = os.path.join(routes_dir, route_file)
                if os.path.exists(route_path):
                    knowledge["routes"][route_file] = self._analyze_routes(route_path)

        return knowledge

    def _analyze_model(self, model_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a model file for key information."""
        try:
            with open(model_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            info = {
                "file": model_path.replace(self.path + "/", ""),
                "fillable": [],
                "relations": [],
                "traits": [],
            }

            # Extract fillable
            if "$fillable" in content:
                import re
                fillable_match = re.search(r"\$fillable\s*=\s*\[(.*?)\]", content, re.DOTALL)
                if fillable_match:
                    fields = re.findall(r"['\"](\w+)['\"]", fillable_match.group(1))
                    info["fillable"] = fields[:10]  # Limit to 10

            # Extract relation methods
            relation_methods = ["hasOne", "hasMany", "belongsTo", "belongsToMany", "morphTo", "morphMany", "morphToMany"]
            for method in relation_methods:
                if method in content:
                    info["relations"].append(method)

            # Extract traits
            if "use " in content:
                trait_matches = re.findall(r"use\s+([A-Za-z\\]+);", content)
                info["traits"] = [t.split("\\")[-1] for t in trait_matches if "Trait" in t or "Notifiable" in t][:5]

            return info if info["fillable"] or info["relations"] else None

        except Exception:
            return None

    def _analyze_routes(self, route_path: str) -> Dict[str, Any]:
        """Analyze a route file for key information."""
        try:
            with open(route_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            import re

            # Count route definitions
            route_count = len(re.findall(r"Route::(get|post|put|patch|delete|resource|apiResource)", content))

            # Find route groups/prefixes
            prefixes = re.findall(r"prefix\s*\(\s*['\"]([^'\"]+)['\"]", content)

            # Find middleware
            middleware = re.findall(r"middleware\s*\(\s*['\"]([^'\"]+)['\"]", content)

            return {
                "route_count": route_count,
                "prefixes": list(set(prefixes))[:5],
                "middleware": list(set(middleware))[:5],
            }

        except Exception:
            return {}

    def _detect_conventions(self) -> Dict[str, Any]:
        """Detect coding conventions from the codebase."""
        conventions = {
            "php": {
                "strict_types": self._check_strict_types(),
                "type_hints": True,  # Assume modern Laravel uses type hints
                "psr12": True,  # Laravel follows PSR-12
            },
            "vue": {},
            "general": {
                "uses_prettier": self._file_exists(".prettierrc") or self._file_exists(".prettierrc.json"),
                "uses_eslint": self._file_exists(".eslintrc") or self._file_exists(".eslintrc.js") or self._file_exists("eslint.config.js"),
                "uses_phpcs": self._file_exists("phpcs.xml") or self._file_exists(".phpcs.xml"),
            },
        }

        # Vue conventions
        frontend = self.stack.get("frontend", {})
        if frontend.get("framework") == "vue":
            conventions["vue"] = {
                "composition_api": frontend.get("composition_api", True),
                "script_setup": self._check_script_setup(),
                "typescript": frontend.get("typescript", False),
            }

        return conventions

    def _check_strict_types(self) -> bool:
        """Check if declare(strict_types=1) is commonly used."""
        sample_files = [
            "app/Models/User.php",
            "app/Http/Controllers/Controller.php",
            "app/Providers/AppServiceProvider.php",
        ]

        strict_count = 0
        for f in sample_files:
            content = self._read_file(f)
            if content and "declare(strict_types=1)" in content:
                strict_count += 1

        return strict_count >= 2  # At least 2 of 3 files use strict types

    def _check_script_setup(self) -> bool:
        """Check if Vue files use <script setup>."""
        vue_dirs = [
            "resources/js/pages",
            "resources/js/Pages",
            "resources/js/components",
            "resources/js/Components",
        ]

        for vue_dir in vue_dirs:
            dir_path = os.path.join(self.path, vue_dir)
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path)[:5]:  # Check first 5 files
                    if filename.endswith(".vue"):
                        content = self._read_file(os.path.join(vue_dir, filename))
                        if content and "<script setup" in content:
                            return True

        return True  # Default to true for Vue 3 projects

    def _get_important_files_content(self) -> Dict[str, str]:
        """Get content of key files for AI context (truncated)."""
        important_files = [
            "routes/web.php",
            "routes/api.php",
            "config/app.php",
            "app/Models/User.php",
            "vite.config.js",
            "vite.config.ts",
            "tsconfig.json",
            "tailwind.config.js",
            "tailwind.config.ts",
        ]

        contents = {}
        for f in important_files:
            content = self._read_file(f)
            if content:
                # Truncate to avoid huge context
                max_length = 3000
                if len(content) > max_length:
                    content = content[:max_length] + "\n... (truncated)"
                contents[f] = content

        return contents

    def _format_conventions(self) -> str:
        """Format conventions for CLAUDE.md."""
        conventions = self._detect_conventions()

        lines = []

        # PHP conventions
        php = conventions.get("php", {})
        if php.get("strict_types"):
            lines.append("- PHP: Use declare(strict_types=1)")
        lines.append("- PHP: Follow PSR-12 coding style")
        lines.append("- PHP: Use type declarations for parameters and return types")

        # Vue conventions
        vue = conventions.get("vue", {})
        if vue:
            if vue.get("composition_api"):
                lines.append("- Vue: Use Composition API")
            if vue.get("script_setup"):
                lines.append("- Vue: Use <script setup> syntax")
            if vue.get("typescript"):
                lines.append("- Vue: Use TypeScript with proper types")

        # General
        general = conventions.get("general", {})
        if general.get("uses_prettier"):
            lines.append("- Format code with Prettier")
        if general.get("uses_eslint"):
            lines.append("- Follow ESLint rules")

        return "\n".join(lines) if lines else "- Follow existing code style"

    def _format_key_files(self) -> str:
        """Format key files list for CLAUDE.md."""
        key_files = self.structure.get("key_files", [])
        if not key_files:
            return "- Standard Laravel structure"

        return "\n".join(f"- {f}" for f in key_files[:10])

    def _read_file(self, filename: str) -> Optional[str]:
        """Read a text file."""
        filepath = os.path.join(self.path, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return None
        return None

    def _file_exists(self, filename: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.join(self.path, filename))
