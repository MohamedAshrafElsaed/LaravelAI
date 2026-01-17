"""
Laravel project scanner service.
Scans Laravel project directories and returns file information.
"""
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


# Directories to exclude from scanning
EXCLUDED_DIRS = {
    "vendor",
    "node_modules",
    "storage",
    ".git",
    ".idea",
    ".vscode",
    "bootstrap/cache",
    ".next",
    "dist",
    "build",
    "public/build",
    "public/hot",
}

# File extensions to include
INCLUDED_EXTENSIONS = {
    ".php",
    ".blade.php",
    ".vue",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".env.example",
}

# Laravel type detection patterns
LARAVEL_TYPE_PATTERNS = {
    "controller": [
        "app/Http/Controllers",
        "app/Http/Controller",
    ],
    "model": [
        "app/Models",
        "app/Model",
    ],
    "migration": [
        "database/migrations",
    ],
    "seeder": [
        "database/seeders",
        "database/seeds",
    ],
    "factory": [
        "database/factories",
    ],
    "middleware": [
        "app/Http/Middleware",
    ],
    "request": [
        "app/Http/Requests",
    ],
    "resource": [
        "app/Http/Resources",
    ],
    "policy": [
        "app/Policies",
    ],
    "provider": [
        "app/Providers",
    ],
    "event": [
        "app/Events",
    ],
    "listener": [
        "app/Listeners",
    ],
    "job": [
        "app/Jobs",
    ],
    "mail": [
        "app/Mail",
    ],
    "notification": [
        "app/Notifications",
    ],
    "rule": [
        "app/Rules",
    ],
    "exception": [
        "app/Exceptions",
    ],
    "console": [
        "app/Console/Commands",
        "app/Console",
    ],
    "service": [
        "app/Services",
    ],
    "repository": [
        "app/Repositories",
    ],
    "trait": [
        "app/Traits",
    ],
    "interface": [
        "app/Contracts",
        "app/Interfaces",
    ],
    "helper": [
        "app/Helpers",
    ],
    "config": [
        "config/",
    ],
    "route": [
        "routes/",
    ],
    "view": [
        "resources/views",
    ],
    "component": [
        "resources/js/Components",
        "resources/js/components",
        "resources/vue/components",
    ],
    "livewire": [
        "app/Livewire",
        "app/Http/Livewire",
    ],
    "test": [
        "tests/",
    ],
    "lang": [
        "lang/",
        "resources/lang",
    ],
}


@dataclass
class FileInfo:
    """Information about a scanned file."""
    path: str
    type: str  # File extension type (php, vue, js, etc.)
    size: int
    laravel_type: str  # Laravel specific type (controller, model, etc.)
    hash: str  # File content hash for change detection

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanStats:
    """Statistics about the scanned project."""
    total_files: int = 0
    php_files: int = 0
    blade_files: int = 0
    vue_files: int = 0
    js_files: int = 0
    ts_files: int = 0
    json_files: int = 0
    config_files: int = 0
    controllers: int = 0
    models: int = 0
    migrations: int = 0
    views: int = 0
    routes: int = 0
    tests: int = 0
    total_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    """Result of scanning a Laravel project."""
    files: List[FileInfo]
    stats: ScanStats
    laravel_version: Optional[str] = None
    php_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": [f.to_dict() for f in self.files],
            "stats": self.stats.to_dict(),
            "laravel_version": self.laravel_version,
            "php_version": self.php_version,
        }


class ScannerError(Exception):
    """Custom exception for scanner errors."""
    pass


class LaravelScanner:
    """Scanner for Laravel projects."""

    def __init__(self, project_path: str):
        """
        Initialize the scanner.

        Args:
            project_path: Path to the Laravel project root
        """
        self.project_path = Path(project_path)

        if not self.project_path.exists():
            raise ScannerError(f"Project path does not exist: {project_path}")

        if not self.project_path.is_dir():
            raise ScannerError(f"Project path is not a directory: {project_path}")

    def _should_exclude_dir(self, dir_path: Path) -> bool:
        """Check if a directory should be excluded from scanning."""
        relative_path = str(dir_path.relative_to(self.project_path))

        # Check exact matches and path starts
        for excluded in EXCLUDED_DIRS:
            if relative_path == excluded or relative_path.startswith(excluded + "/"):
                return True
            # Check if any part of the path matches excluded dirs
            parts = relative_path.split("/")
            if any(part == excluded.rstrip("/") for part in parts):
                return True

        return False

    def _should_include_file(self, file_path: Path) -> bool:
        """Check if a file should be included in scanning."""
        name = file_path.name.lower()

        # Special case for blade templates
        if name.endswith(".blade.php"):
            return True

        # Check standard extensions
        suffix = file_path.suffix.lower()
        if suffix in INCLUDED_EXTENSIONS:
            return True

        # Special files
        if name in {".env.example", "composer.json", "package.json"}:
            return True

        return False

    def _get_file_type(self, file_path: Path) -> str:
        """Determine the file type from its extension."""
        name = file_path.name.lower()

        if name.endswith(".blade.php"):
            return "blade"

        suffix = file_path.suffix.lower()

        type_mapping = {
            ".php": "php",
            ".vue": "vue",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
        }

        return type_mapping.get(suffix, "other")

    def _get_laravel_type(self, file_path: Path) -> str:
        """Determine the Laravel-specific type from the file path."""
        relative_path = str(file_path.relative_to(self.project_path))
        normalized_path = relative_path.replace("\\", "/")

        for laravel_type, patterns in LARAVEL_TYPE_PATTERNS.items():
            for pattern in patterns:
                if normalized_path.startswith(pattern):
                    return laravel_type

        # Default based on location
        if normalized_path.startswith("app/"):
            return "class"

        return "other"

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""

    def _detect_laravel_version(self) -> Optional[str]:
        """Detect Laravel version from composer.json or composer.lock."""
        composer_json = self.project_path / "composer.json"

        if composer_json.exists():
            try:
                import json
                with open(composer_json, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check require section
                require = data.get("require", {})
                if "laravel/framework" in require:
                    version = require["laravel/framework"]
                    # Clean up version string (remove ^, ~, etc.)
                    return version.lstrip("^~>=<")

            except Exception:
                pass

        return None

    def _detect_php_version(self) -> Optional[str]:
        """Detect PHP version from composer.json."""
        composer_json = self.project_path / "composer.json"

        if composer_json.exists():
            try:
                import json
                with open(composer_json, "r", encoding="utf-8") as f:
                    data = json.load(f)

                require = data.get("require", {})
                if "php" in require:
                    version = require["php"]
                    return version.lstrip("^~>=<")

            except Exception:
                pass

        return None

    def scan(self) -> ScanResult:
        """
        Scan the Laravel project and return file information.

        Returns:
            ScanResult containing files and statistics
        """
        files: List[FileInfo] = []
        stats = ScanStats()

        for root, dirs, filenames in os.walk(self.project_path):
            current_path = Path(root)

            # Filter out excluded directories
            dirs[:] = [
                d for d in dirs
                if not self._should_exclude_dir(current_path / d)
            ]

            for filename in filenames:
                file_path = current_path / filename

                if not self._should_include_file(file_path):
                    continue

                try:
                    file_size = file_path.stat().st_size
                    file_type = self._get_file_type(file_path)
                    laravel_type = self._get_laravel_type(file_path)
                    file_hash = self._compute_file_hash(file_path)

                    relative_path = str(file_path.relative_to(self.project_path))

                    file_info = FileInfo(
                        path=relative_path,
                        type=file_type,
                        size=file_size,
                        laravel_type=laravel_type,
                        hash=file_hash,
                    )
                    files.append(file_info)

                    # Update statistics
                    stats.total_files += 1
                    stats.total_size_bytes += file_size

                    # Type-specific counts
                    if file_type == "php":
                        stats.php_files += 1
                    elif file_type == "blade":
                        stats.blade_files += 1
                    elif file_type == "vue":
                        stats.vue_files += 1
                    elif file_type == "javascript":
                        stats.js_files += 1
                    elif file_type == "typescript":
                        stats.ts_files += 1
                    elif file_type == "json":
                        stats.json_files += 1

                    # Laravel type counts
                    if laravel_type == "controller":
                        stats.controllers += 1
                    elif laravel_type == "model":
                        stats.models += 1
                    elif laravel_type == "migration":
                        stats.migrations += 1
                    elif laravel_type == "view":
                        stats.views += 1
                    elif laravel_type == "route":
                        stats.routes += 1
                    elif laravel_type == "test":
                        stats.tests += 1
                    elif laravel_type == "config":
                        stats.config_files += 1

                except Exception:
                    # Skip files that can't be read
                    continue

        # Detect versions
        laravel_version = self._detect_laravel_version()
        php_version = self._detect_php_version()

        return ScanResult(
            files=files,
            stats=stats,
            laravel_version=laravel_version,
            php_version=php_version,
        )


def scan_laravel_project(path: str) -> Dict[str, Any]:
    """
    Scan a Laravel project and return structured information.

    Args:
        path: Path to the Laravel project root

    Returns:
        Dictionary containing files list and statistics

    Raises:
        ScannerError: If scanning fails
    """
    scanner = LaravelScanner(path)
    result = scanner.scan()
    return result.to_dict()
