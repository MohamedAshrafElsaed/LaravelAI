"""
File Scanner Service

Scans project files and collects statistics.
Categorizes files by type and purpose.
"""
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict


class FileScanner:
    """Scan project files and collect statistics."""

    EXCLUDE_DIRS = {
        "vendor",
        "node_modules",
        ".git",
        "storage",
        "bootstrap/cache",
        ".idea",
        ".vscode",
        "public/build",
        "public/hot",
        "public/storage",
        ".nuxt",
        ".next",
        ".output",
        "dist",
        "build",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "coverage",
        ".turbo",
        ".cache",
    }

    EXCLUDE_FILES = {
        ".DS_Store",
        "Thumbs.db",
        ".gitignore",
        ".env",
        ".env.local",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.lock",
        "Gemfile.lock",
    }

    # File categories for Laravel projects
    LARAVEL_CATEGORIES = {
        "php": {
            "controllers": ["app/Http/Controllers/"],
            "models": ["app/Models/"],
            "services": ["app/Services/"],
            "repositories": ["app/Repositories/"],
            "jobs": ["app/Jobs/"],
            "events": ["app/Events/"],
            "listeners": ["app/Listeners/"],
            "middleware": ["app/Http/Middleware/"],
            "requests": ["app/Http/Requests/"],
            "resources": ["app/Http/Resources/"],
            "notifications": ["app/Notifications/"],
            "policies": ["app/Policies/"],
            "providers": ["app/Providers/"],
            "commands": ["app/Console/Commands/"],
            "migrations": ["database/migrations/"],
            "seeders": ["database/seeders/"],
            "factories": ["database/factories/"],
            "tests": ["tests/"],
            "config": ["config/"],
            "routes": ["routes/"],
            "traits": ["app/Traits/"],
            "enums": ["app/Enums/"],
            "actions": ["app/Actions/"],
            "observers": ["app/Observers/"],
            "rules": ["app/Rules/"],
            "casts": ["app/Casts/"],
        },
        "vue": {
            "pages": ["resources/js/pages/", "resources/js/Pages/"],
            "components": ["resources/js/components/", "resources/js/Components/"],
            "composables": ["resources/js/composables/"],
            "layouts": ["resources/js/layouts/", "resources/js/Layouts/"],
            "stores": ["resources/js/stores/"],
        },
        "blade": {
            "views": ["resources/views/"],
            "components": ["resources/views/components/"],
            "layouts": ["resources/views/layouts/"],
            "livewire": ["resources/views/livewire/"],
        },
        "ts": {
            "types": ["resources/js/types/"],
            "utils": ["resources/js/utils/"],
            "lib": ["resources/js/lib/"],
        },
    }

    # File extension mapping
    EXT_MAP = {
        ".php": "php",
        ".vue": "vue",
        ".ts": "ts",
        ".tsx": "tsx",
        ".js": "js",
        ".jsx": "jsx",
        ".css": "css",
        ".scss": "scss",
        ".sass": "sass",
        ".less": "less",
        ".json": "json",
        ".md": "md",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".html": "html",
        ".svg": "svg",
        ".py": "python",
        ".rb": "ruby",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".kt": "kotlin",
        ".swift": "swift",
        ".sql": "sql",
        ".sh": "shell",
        ".env": "env",
    }

    def __init__(self, project_path: str):
        self.path = project_path
        self.files: List[Dict[str, Any]] = []
        self.stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "lines": 0})
        self.categories: Dict[str, int] = defaultdict(int)
        self.directories: List[str] = []

    def scan(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> Dict[str, Any]:
        """Run full scan."""
        self._scan_directory(self.path, progress_callback)

        # Calculate summary
        total_files = len(self.files)
        total_lines = sum(f["lines"] for f in self.files)

        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "by_type": dict(self.stats),
            "by_category": dict(self.categories),
            "directories": self.directories[:100],  # Top 100 directories
            "largest_files": sorted(
                self.files, key=lambda x: x.get("lines", 0), reverse=True
            )[:20],  # Top 20 largest files
        }

    def _scan_directory(
        self,
        directory: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        depth: int = 0,
    ):
        """Recursively scan directory."""
        try:
            entries = os.listdir(directory)
        except PermissionError:
            return

        # Track directories
        rel_dir = os.path.relpath(directory, self.path)
        if rel_dir != "." and depth <= 3:
            self.directories.append(rel_dir)

        for entry in entries:
            entry_path = os.path.join(directory, entry)
            rel_path = os.path.relpath(entry_path, self.path)

            # Skip excluded items
            if entry in self.EXCLUDE_DIRS or entry in self.EXCLUDE_FILES:
                continue

            # Check full path exclusions
            skip = False
            for exclude in self.EXCLUDE_DIRS:
                if exclude in rel_path.split(os.sep):
                    skip = True
                    break
            if skip:
                continue

            if os.path.isdir(entry_path):
                self._scan_directory(entry_path, progress_callback, depth + 1)
            else:
                file_info = self._analyze_file(entry_path, rel_path)
                if file_info:
                    self.files.append(file_info)

                    # Progress callback
                    if progress_callback and len(self.files) % 100 == 0:
                        progress_callback(len(self.files), f"Scanned {len(self.files)} files...")

    def _analyze_file(self, filepath: str, rel_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a single file."""
        ext = Path(filepath).suffix.lower()

        # Handle .blade.php
        if rel_path.endswith(".blade.php"):
            file_type = "blade"
        else:
            file_type = self.EXT_MAP.get(ext)

        if not file_type:
            return None

        # Count lines
        lines = 0
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = sum(1 for _ in f)
        except Exception:
            pass

        # Get file size
        try:
            size = os.path.getsize(filepath)
        except Exception:
            size = 0

        # Update stats
        self.stats[file_type]["count"] += 1
        self.stats[file_type]["lines"] += lines

        # Categorize
        category = self._categorize_file(rel_path, file_type)
        if category:
            self.categories[category] += 1

        return {
            "path": rel_path,
            "type": file_type,
            "lines": lines,
            "category": category,
            "size": size,
        }

    def _categorize_file(self, rel_path: str, file_type: str) -> Optional[str]:
        """Categorize file based on path."""
        # Normalize path separators
        normalized_path = rel_path.replace("\\", "/")

        categories = self.LARAVEL_CATEGORIES.get(file_type, {})

        for category, patterns in categories.items():
            for pattern in patterns:
                if normalized_path.startswith(pattern) or f"/{pattern}" in normalized_path:
                    return category

        return None

    def get_structure_analysis(self) -> Dict[str, Any]:
        """Analyze project structure and patterns."""
        patterns_detected = []

        # Check for common Laravel patterns
        if self.categories.get("services", 0) > 0:
            patterns_detected.append("service-layer")

        if self.categories.get("repositories", 0) > 0:
            patterns_detected.append("repository-pattern")

        if self.categories.get("actions", 0) > 0:
            patterns_detected.append("action-classes")

        if self.categories.get("observers", 0) > 0:
            patterns_detected.append("observer-pattern")

        if self.categories.get("traits", 0) > 0:
            patterns_detected.append("traits")

        if self.categories.get("enums", 0) > 0:
            patterns_detected.append("enums")

        # Check for specific architectural patterns
        if self._dir_exists("app/Domain"):
            patterns_detected.append("domain-driven-design")

        if self._dir_exists("Modules") or self._dir_exists("app/Modules"):
            patterns_detected.append("modular-architecture")

        # Key files
        key_files = []
        key_file_paths = [
            "composer.json",
            "package.json",
            "vite.config.js",
            "vite.config.ts",
            "webpack.mix.js",
            "tailwind.config.js",
            "tailwind.config.ts",
            "tsconfig.json",
            ".env.example",
            "phpunit.xml",
            "docker-compose.yml",
            "Dockerfile",
        ]

        for kf in key_file_paths:
            if self._file_exists(kf):
                key_files.append(kf)

        return {
            "directories": self.directories[:50],
            "key_files": key_files,
            "patterns_detected": patterns_detected,
            "has_tests": self.categories.get("tests", 0) > 0,
            "has_migrations": self.categories.get("migrations", 0) > 0,
            "has_seeders": self.categories.get("seeders", 0) > 0,
            "has_factories": self.categories.get("factories", 0) > 0,
        }

    def _file_exists(self, filename: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.join(self.path, filename))

    def _dir_exists(self, dirname: str) -> bool:
        """Check if a directory exists."""
        return os.path.isdir(os.path.join(self.path, dirname))
