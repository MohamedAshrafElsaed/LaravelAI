"""
Health Checker Service

Checks project health and production readiness.
Identifies security, performance, architecture, and code quality issues.
"""
import os
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """Represents a health check issue."""

    category: str
    severity: Severity
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggestion: Optional[str] = None
    auto_fixable: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }


class HealthChecker:
    """Check project health and production readiness."""

    def __init__(self, project_path: str, stack: dict, file_stats: dict):
        self.path = project_path
        self.stack = stack or {}
        self.file_stats = file_stats or {}
        self.issues: List[Issue] = []

    def check(self) -> Dict[str, Any]:
        """Run all health checks."""
        categories = {
            "architecture": self._check_architecture(),
            "security": self._check_security(),
            "performance": self._check_performance(),
            "code_quality": self._check_code_quality(),
            "error_handling": self._check_error_handling(),
            "logging": self._check_logging(),
            "testing": self._check_testing(),
            "documentation": self._check_documentation(),
            "ai_readiness": self._check_ai_readiness(),
        }

        # Calculate overall score
        total_score = sum(c["score"] for c in categories.values())
        overall_score = total_score / len(categories)

        # Separate issues by severity
        critical = [i for i in self.issues if i.severity == Severity.CRITICAL]
        warnings = [i for i in self.issues if i.severity == Severity.WARNING]
        info = [i for i in self.issues if i.severity == Severity.INFO]

        return {
            "score": round(overall_score, 1),
            "categories": categories,
            "critical_issues": [i.to_dict() for i in critical],
            "warnings": [i.to_dict() for i in warnings],
            "info": [i.to_dict() for i in info],
            "total_issues": len(self.issues),
            "production_ready": overall_score >= 70 and len(critical) == 0,
        }

    def get_issues(self) -> List[Issue]:
        """Get all detected issues."""
        return self.issues

    # ========== Architecture Checks ==========

    def _check_architecture(self) -> Dict[str, Any]:
        """Check architectural patterns."""
        score = 100
        category_issues = []

        by_category = self.file_stats.get("by_category", {})
        services_count = by_category.get("services", 0)
        repositories_count = by_category.get("repositories", 0)
        controllers_count = by_category.get("controllers", 0)
        models_count = by_category.get("models", 0)

        # Check for service layer
        if services_count == 0 and controllers_count > 5:
            score -= 15
            issue = Issue(
                category="architecture",
                severity=Severity.WARNING,
                title="Missing Service Layer",
                description=f"No service classes found with {controllers_count} controllers. Business logic might be in controllers.",
                suggestion="Create Service classes for business logic. Controllers should only handle HTTP requests/responses.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for fat models
        if models_count > 20 and services_count == 0 and repositories_count == 0:
            score -= 10
            issue = Issue(
                category="architecture",
                severity=Severity.INFO,
                title="Potential Fat Models",
                description=f"Found {models_count} models without service/repository layer.",
                suggestion="Consider extracting business logic to services or using repository pattern.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for proper request validation
        requests_count = by_category.get("requests", 0)
        if controllers_count > 10 and requests_count < controllers_count / 2:
            score -= 10
            issue = Issue(
                category="architecture",
                severity=Severity.WARNING,
                title="Limited Form Requests",
                description=f"Only {requests_count} Form Request classes for {controllers_count} controllers.",
                suggestion="Use Form Request classes for validation instead of inline validation in controllers.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for resource classes
        resources_count = by_category.get("resources", 0)
        if models_count > 5 and resources_count == 0:
            score -= 5
            issue = Issue(
                category="architecture",
                severity=Severity.INFO,
                title="No API Resources",
                description="No API Resource classes found for transforming model data.",
                suggestion="Use API Resources for consistent API responses and data transformation.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Security Checks ==========

    def _check_security(self) -> Dict[str, Any]:
        """Check security issues."""
        score = 100
        category_issues = []

        # Check .env is in .gitignore
        gitignore = self._read_file(".gitignore")
        if gitignore and ".env" not in gitignore:
            score -= 30
            issue = Issue(
                category="security",
                severity=Severity.CRITICAL,
                title=".env not in .gitignore",
                description="Environment file might be committed to git, exposing secrets.",
                file_path=".gitignore",
                suggestion="Add .env to .gitignore immediately.",
                auto_fixable=True,
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for exposed debug mode in .env.example
        env_example = self._read_file(".env.example")
        if env_example and "APP_DEBUG=true" in env_example:
            score -= 10
            issue = Issue(
                category="security",
                severity=Severity.WARNING,
                title="Debug mode enabled in .env.example",
                description="APP_DEBUG=true in .env.example might be copied to production.",
                file_path=".env.example",
                suggestion="Set APP_DEBUG=false in .env.example as the default.",
                auto_fixable=True,
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for CSRF protection
        backend = self.stack.get("backend", {})
        if backend.get("framework") == "laravel":
            middleware = self._read_file("app/Http/Kernel.php")
            bootstrap = self._read_file("bootstrap/app.php")

            # Laravel 11+ uses bootstrap/app.php
            csrf_found = False
            if middleware and "VerifyCsrfToken" in middleware:
                csrf_found = True
            if bootstrap and ("csrf" in bootstrap.lower() or "VerifyCsrfToken" in bootstrap):
                csrf_found = True

            # Check web middleware group
            if not csrf_found:
                score -= 15
                issue = Issue(
                    category="security",
                    severity=Severity.WARNING,
                    title="CSRF protection unclear",
                    description="Could not verify CSRF protection is properly configured.",
                    suggestion="Ensure VerifyCsrfToken middleware is in the web middleware group.",
                )
                self.issues.append(issue)
                category_issues.append(issue)

        # Check for authentication
        packages = backend.get("packages", {})
        has_auth = (
            packages.get("sanctum")
            or packages.get("passport")
            or packages.get("fortify")
            or packages.get("breeze")
            or packages.get("jetstream")
        )
        if not has_auth:
            score -= 10
            issue = Issue(
                category="security",
                severity=Severity.INFO,
                title="No authentication package detected",
                description="No standard Laravel authentication package found.",
                suggestion="Consider using Laravel Sanctum for API auth or Breeze/Jetstream for full auth scaffolding.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for rate limiting
        routes_web = self._read_file("routes/web.php")
        routes_api = self._read_file("routes/api.php")
        has_rate_limit = False

        if routes_api and ("throttle" in routes_api or "RateLimiter" in routes_api):
            has_rate_limit = True
        if bootstrap and "throttle" in str(self._read_file("bootstrap/app.php")):
            has_rate_limit = True

        if not has_rate_limit:
            score -= 10
            issue = Issue(
                category="security",
                severity=Severity.WARNING,
                title="No rate limiting detected",
                description="API routes may not have rate limiting configured.",
                file_path="routes/api.php",
                suggestion="Apply throttle middleware to API routes to prevent abuse.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Performance Checks ==========

    def _check_performance(self) -> Dict[str, Any]:
        """Check performance issues."""
        score = 100
        category_issues = []

        by_category = self.file_stats.get("by_category", {})
        models_count = by_category.get("models", 0)

        # Check for large number of models (N+1 risk)
        if models_count > 30:
            score -= 5
            issue = Issue(
                category="performance",
                severity=Severity.INFO,
                title="Large number of models",
                description=f"{models_count} models found. Watch for N+1 query issues.",
                suggestion="Use eager loading ($with property or with() method) and consider using Laravel Debugbar.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for caching setup
        cache = self.stack.get("cache", "file")
        if cache == "file":
            score -= 10
            issue = Issue(
                category="performance",
                severity=Severity.WARNING,
                title="File-based caching",
                description="Using file cache driver which is not optimal for production.",
                suggestion="Use Redis or Memcached for production caching.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for queue configuration
        queue = self.stack.get("queue", "sync")
        if queue == "sync":
            score -= 15
            issue = Issue(
                category="performance",
                severity=Severity.WARNING,
                title="Synchronous queue driver",
                description="Queue jobs run synchronously, blocking HTTP requests.",
                suggestion="Use Redis or database queue driver for production.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for Octane
        packages = self.stack.get("backend", {}).get("packages", {})
        if not packages.get("octane"):
            score -= 5
            issue = Issue(
                category="performance",
                severity=Severity.INFO,
                title="Laravel Octane not installed",
                description="Octane can significantly improve application performance.",
                suggestion="Consider installing Laravel Octane for high-performance applications.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for Horizon (if using Redis queues)
        if queue == "redis" and not packages.get("horizon"):
            score -= 5
            issue = Issue(
                category="performance",
                severity=Severity.INFO,
                title="Laravel Horizon not installed",
                description="Using Redis queue without Horizon for monitoring.",
                suggestion="Install Laravel Horizon for queue monitoring and management.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Code Quality Checks ==========

    def _check_code_quality(self) -> Dict[str, Any]:
        """Check code quality issues."""
        score = 100
        category_issues = []

        # Check for TypeScript
        frontend = self.stack.get("frontend", {})
        if frontend.get("framework") and not frontend.get("typescript"):
            score -= 10
            issue = Issue(
                category="code_quality",
                severity=Severity.INFO,
                title="No TypeScript",
                description="Frontend is using JavaScript instead of TypeScript.",
                suggestion="Consider migrating to TypeScript for better type safety and IDE support.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for Pint (code style)
        packages = self.stack.get("backend", {}).get("packages", {})
        if not packages.get("pint"):
            score -= 5
            issue = Issue(
                category="code_quality",
                severity=Severity.INFO,
                title="Laravel Pint not installed",
                description="No code style enforcement tool detected.",
                suggestion="Install Laravel Pint for consistent code formatting.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for static analysis
        composer = self._read_json("composer.json")
        if composer:
            require_dev = composer.get("require-dev", {})
            has_static_analysis = (
                "phpstan/phpstan" in require_dev
                or "larastan/larastan" in require_dev
                or "vimeo/psalm" in require_dev
                or "rector/rector" in require_dev
            )
            if not has_static_analysis:
                score -= 10
                issue = Issue(
                    category="code_quality",
                    severity=Severity.WARNING,
                    title="No static analysis",
                    description="No static analysis tool (PHPStan/Larastan/Psalm) detected.",
                    suggestion="Install Larastan for static analysis to catch bugs early.",
                )
                self.issues.append(issue)
                category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Error Handling Checks ==========

    def _check_error_handling(self) -> Dict[str, Any]:
        """Check error handling setup."""
        score = 100
        category_issues = []

        # Check for error tracking service
        composer = self._read_json("composer.json")
        if composer:
            require = {**composer.get("require", {}), **composer.get("require-dev", {})}
            has_error_tracking = (
                "sentry/sentry-laravel" in require
                or "bugsnag/bugsnag-laravel" in require
                or "rollbar/rollbar-laravel" in require
                or "facade/flare-client-php" in require
            )
            if not has_error_tracking:
                score -= 20
                issue = Issue(
                    category="error_handling",
                    severity=Severity.WARNING,
                    title="No error tracking service",
                    description="No Sentry, Bugsnag, Flare, or Rollbar detected.",
                    suggestion="Install an error tracking service for production error monitoring.",
                )
                self.issues.append(issue)
                category_issues.append(issue)

        # Check for custom exception handler
        handler_exists = self._file_exists("app/Exceptions/Handler.php")
        bootstrap = self._read_file("bootstrap/app.php")

        has_custom_handling = handler_exists
        if bootstrap and "withExceptions" in bootstrap:
            has_custom_handling = True

        if not has_custom_handling:
            score -= 10
            issue = Issue(
                category="error_handling",
                severity=Severity.INFO,
                title="Default exception handling",
                description="Using default Laravel exception handling.",
                suggestion="Customize exception handling for better error responses and logging.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Logging Checks ==========

    def _check_logging(self) -> Dict[str, Any]:
        """Check logging configuration."""
        score = 100
        category_issues = []

        # Check for monitoring
        packages = self.stack.get("backend", {}).get("packages", {})
        if not packages.get("pulse") and not packages.get("telescope"):
            score -= 10
            issue = Issue(
                category="logging",
                severity=Severity.INFO,
                title="No application monitoring",
                description="Neither Laravel Pulse nor Telescope is installed.",
                suggestion="Install Laravel Pulse for production monitoring or Telescope for development.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check logging config
        logging_config = self._read_file("config/logging.php")
        if logging_config:
            if "stack" not in logging_config or "'channels' => ['single']" in logging_config:
                score -= 5
                issue = Issue(
                    category="logging",
                    severity=Severity.INFO,
                    title="Basic logging configuration",
                    description="Using basic single-channel logging.",
                    suggestion="Consider using stacked channels for comprehensive logging.",
                )
                self.issues.append(issue)
                category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Testing Checks ==========

    def _check_testing(self) -> Dict[str, Any]:
        """Check testing setup."""
        score = 100
        category_issues = []

        by_category = self.file_stats.get("by_category", {})
        tests_count = by_category.get("tests", 0)
        total_php = self.file_stats.get("by_type", {}).get("php", {}).get("count", 0)

        # Check for test files
        if tests_count == 0:
            score -= 30
            issue = Issue(
                category="testing",
                severity=Severity.CRITICAL,
                title="No tests found",
                description="No test files detected in the project.",
                suggestion="Add PHPUnit or Pest tests for critical functionality.",
            )
            self.issues.append(issue)
            category_issues.append(issue)
        elif total_php > 0:
            # Check test to code ratio
            ratio = tests_count / total_php
            if ratio < 0.1:
                score -= 15
                issue = Issue(
                    category="testing",
                    severity=Severity.WARNING,
                    title="Low test coverage",
                    description=f"Only {tests_count} test files for {total_php} PHP files ({ratio*100:.1f}%).",
                    suggestion="Aim for at least 20-30% test coverage for critical paths.",
                )
                self.issues.append(issue)
                category_issues.append(issue)

        # Check for E2E tests
        testing = self.stack.get("testing", {})
        has_e2e = testing.get("dusk") or testing.get("cypress") or testing.get("playwright")
        if not has_e2e:
            score -= 10
            issue = Issue(
                category="testing",
                severity=Severity.INFO,
                title="No E2E tests",
                description="No Dusk, Cypress, or Playwright detected.",
                suggestion="Add E2E tests for critical user flows.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for Pest (modern testing)
        if not testing.get("pest"):
            score -= 5
            issue = Issue(
                category="testing",
                severity=Severity.INFO,
                title="Consider using Pest",
                description="Using PHPUnit instead of Pest for testing.",
                suggestion="Consider migrating to Pest for more expressive tests.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Documentation Checks ==========

    def _check_documentation(self) -> Dict[str, Any]:
        """Check documentation."""
        score = 100
        category_issues = []

        # Check for README
        has_readme = (
            self._file_exists("README.md")
            or self._file_exists("readme.md")
            or self._file_exists("README")
        )
        if not has_readme:
            score -= 20
            issue = Issue(
                category="documentation",
                severity=Severity.WARNING,
                title="No README.md",
                description="Project lacks documentation.",
                suggestion="Create a README with setup instructions, requirements, and usage guide.",
                auto_fixable=True,
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for API documentation
        api_docs_exists = (
            self._file_exists("docs/api.md")
            or self._dir_exists("docs/api")
            or self._file_exists("openapi.yaml")
            or self._file_exists("openapi.json")
            or self._file_exists("swagger.json")
            or self._file_exists("swagger.yaml")
        )

        # Check for Scribe
        composer = self._read_json("composer.json")
        has_scribe = composer and "knuckleswtf/scribe" in str(composer.get("require-dev", {}))

        if not api_docs_exists and not has_scribe:
            score -= 10
            issue = Issue(
                category="documentation",
                severity=Severity.INFO,
                title="No API documentation",
                description="No OpenAPI/Swagger documentation found.",
                suggestion="Install Scribe or document your API endpoints with OpenAPI.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for CONTRIBUTING guide
        if not self._file_exists("CONTRIBUTING.md"):
            score -= 5
            issue = Issue(
                category="documentation",
                severity=Severity.INFO,
                title="No CONTRIBUTING guide",
                description="No contribution guidelines for team members.",
                suggestion="Create CONTRIBUTING.md with coding standards and PR process.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== AI Readiness Checks ==========

    def _check_ai_readiness(self) -> Dict[str, Any]:
        """Check if project is ready for AI assistance."""
        score = 100
        category_issues = []

        total_lines = self.file_stats.get("total_lines", 0)
        by_category = self.file_stats.get("by_category", {})

        # Check codebase size
        if total_lines > 200000:
            score -= 15
            issue = Issue(
                category="ai_readiness",
                severity=Severity.WARNING,
                title="Very large codebase",
                description=f"{total_lines:,} lines of code. May need careful context management.",
                suggestion="AI will use smart context selection. Consider modular architecture.",
            )
            self.issues.append(issue)
            category_issues.append(issue)
        elif total_lines > 100000:
            score -= 5
            issue = Issue(
                category="ai_readiness",
                severity=Severity.INFO,
                title="Large codebase",
                description=f"{total_lines:,} lines of code.",
                suggestion="AI will use smart context selection for this project.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for clear service layer
        if by_category.get("services", 0) == 0:
            score -= 10
            issue = Issue(
                category="ai_readiness",
                severity=Severity.WARNING,
                title="No clear service layer",
                description="AI works better with separated concerns and clear boundaries.",
                suggestion="Create Service classes for business logic to improve AI assistance.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for TypeScript
        frontend = self.stack.get("frontend", {})
        if frontend.get("framework") and not frontend.get("typescript"):
            score -= 10
            issue = Issue(
                category="ai_readiness",
                severity=Severity.INFO,
                title="No TypeScript",
                description="TypeScript helps AI understand code better with type information.",
                suggestion="Consider migrating to TypeScript for better AI assistance.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        # Check for consistent patterns
        if by_category.get("repositories", 0) > 0 and by_category.get("services", 0) > 0:
            score += 5  # Bonus for good architecture
            score = min(100, score)

        # Check for tests (helps AI understand expected behavior)
        if by_category.get("tests", 0) == 0:
            score -= 10
            issue = Issue(
                category="ai_readiness",
                severity=Severity.WARNING,
                title="No tests for AI context",
                description="Tests help AI understand expected behavior and edge cases.",
                suggestion="Add tests to help AI understand how your code should work.",
            )
            self.issues.append(issue)
            category_issues.append(issue)

        return {
            "score": max(0, score),
            "issues": len(category_issues),
        }

    # ========== Helpers ==========

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

    def _read_json(self, filename: str) -> Optional[dict]:
        """Read and parse a JSON file."""
        filepath = os.path.join(self.path, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        return None

    def _file_exists(self, filename: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.join(self.path, filename))

    def _dir_exists(self, dirname: str) -> bool:
        """Check if a directory exists."""
        return os.path.isdir(os.path.join(self.path, dirname))
