"""
Laravel Helper Utilities.

Helper functions for working with Laravel project data from the Project model.
The Project model already contains: stack, file_stats, structure, ai_context.

This file provides utilities to extract and format that data for Nova.
"""
from typing import Dict, Any, List

# Import LARAVEL_DOMAINS from the single source of truth
from app.agents.intent_schema import LARAVEL_DOMAINS

# Re-export for backwards compatibility
__all__ = [
    "LARAVEL_DOMAINS",
    "LARAVEL_DOMAIN_KEYWORDS",
    "LARAVEL_FILE_TYPE_PATTERNS",
    "extract_laravel_info_from_stack",
    "extract_models_from_file_stats",
    "extract_controllers_from_file_stats",
    "suggest_domains_from_keywords",
    "format_stack_for_prompt",
]

# Domain keyword mappings for intent analysis
LARAVEL_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "auth": [
        "auth", "login", "logout", "register", "password", "user",
        "permission", "role", "guard", "sanctum", "passport"
    ],
    "models": [
        "model", "eloquent", "relationship", "belongsto", "hasmany",
        "scope", "cast", "accessor", "mutator"
    ],
    "controllers": [
        "controller", "request", "response", "action", "resource"
    ],
    "services": [
        "service", "business logic", "repository", "action class"
    ],
    "middleware": [
        "middleware", "guard", "gate", "before", "after"
    ],
    "validation": [
        "validation", "validate", "rules", "formrequest", "request class"
    ],
    "database": [
        "migration", "schema", "table", "column", "seeder", "factory", "database"
    ],
    "routing": [
        "route", "routes", "endpoint", "url", "path"
    ],
    "api": [
        "api", "rest", "json", "resource", "transformer"
    ],
    "queue": [
        "queue", "job", "dispatch", "worker", "horizon", "failed"
    ],
    "events": [
        "event", "listener", "subscriber", "broadcast"
    ],
    "mail": [
        "mail", "email", "notification", "mailable"
    ],
    "cache": [
        "cache", "redis", "memcached", "remember"
    ],
    "storage": [
        "storage", "file", "upload", "disk", "s3"
    ],
    "views": [
        "view", "blade", "template", "component", "livewire"
    ],
    "policies": [
        "policy", "authorize", "gate", "can"
    ],
    "providers": [
        "provider", "service provider", "boot", "register"
    ],
    "commands": [
        "command", "artisan", "console", "schedule"
    ],
    "tests": [
        "test", "testing", "phpunit", "pest", "feature test", "unit test"
    ],
}


def extract_laravel_info_from_stack(stack: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract Laravel-specific information from project.stack.

    Args:
        stack: The project.stack JSON field

    Returns:
        Dictionary with extracted Laravel info
    """
    if not stack:
        return {}

    backend = stack.get("backend", {})

    return {
        "framework": backend.get("framework", "unknown"),
        "laravel_version": backend.get("version", "unknown"),
        "php_version": backend.get("php_version", "unknown"),
        "database": stack.get("database", {}).get("type", "unknown"),
        "cache": stack.get("cache", {}).get("driver", "unknown"),
        "queue": stack.get("queue", {}).get("driver", "unknown"),
        "frontend": stack.get("frontend", {}).get("framework", "none"),
        "auth": backend.get("auth", "unknown"),
        "packages": backend.get("packages", []),
    }


def extract_models_from_file_stats(file_stats: Dict[str, Any]) -> List[str]:
    """
    Extract model names from file_stats if available.

    Args:
        file_stats: The project.file_stats JSON field

    Returns:
        List of model names
    """
    # This depends on how your scanner stores model info
    # Adjust based on your actual file_stats structure
    return file_stats.get("models", [])


def extract_controllers_from_file_stats(file_stats: Dict[str, Any]) -> List[str]:
    """
    Extract controller names from file_stats if available.

    Args:
        file_stats: The project.file_stats JSON field

    Returns:
        List of controller names
    """
    return file_stats.get("controllers", [])


def suggest_domains_from_keywords(text: str) -> List[str]:
    """
    Suggest likely Laravel domains based on keywords in text.

    Args:
        text: User input or description

    Returns:
        List of suggested domain names
    """
    text_lower = text.lower()
    domains: List[str] = []

    for domain, keywords in LARAVEL_DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                if domain not in domains:
                    domains.append(domain)
                break

    return domains


def format_stack_for_prompt(stack: Dict[str, Any]) -> str:
    """
    Format project.stack data for inclusion in Nova's prompt.

    This is a simplified version - the Orchestrator.build_project_context()
    already does this comprehensively.

    Args:
        stack: The project.stack JSON field

    Returns:
        Formatted string for prompt
    """
    if not stack:
        return "Stack: Unknown"

    parts: List[str] = []

    backend = stack.get("backend", {})
    if backend.get("framework") == "laravel":
        parts.append(f"Laravel {backend.get('version', '?')}")
        if backend.get("php_version"):
            parts.append(f"PHP {backend.get('php_version')}")

    db = stack.get("database", {})
    if db.get("type"):
        parts.append(db.get("type").upper())

    frontend = stack.get("frontend", {})
    if frontend.get("framework") and frontend.get("framework") != "none":
        parts.append(frontend.get("framework").capitalize())

    return " | ".join(parts) if parts else "Stack: Unknown"


# Standard Laravel file type detection patterns
LARAVEL_FILE_TYPE_PATTERNS: Dict[str, List[str]] = {
    "controller": ["app/Http/Controllers"],
    "model": ["app/Models"],
    "migration": ["database/migrations"],
    "seeder": ["database/seeders", "database/seeds"],
    "factory": ["database/factories"],
    "middleware": ["app/Http/Middleware"],
    "request": ["app/Http/Requests"],
    "resource": ["app/Http/Resources"],
    "policy": ["app/Policies"],
    "provider": ["app/Providers"],
    "event": ["app/Events"],
    "listener": ["app/Listeners"],
    "job": ["app/Jobs"],
    "mail": ["app/Mail"],
    "notification": ["app/Notifications"],
    "command": ["app/Console/Commands"],
    "service": ["app/Services"],
    "repository": ["app/Repositories"],
    "test": ["tests/"],
    "config": ["config/"],
    "route": ["routes/"],
    "view": ["resources/views"],
}