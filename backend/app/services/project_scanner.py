# ============================================================================
# FILE: backend/app/services/project_scanner.py
# ============================================================================
"""
Comprehensive project scanner service.

Scans all project files and directories for:
- Code structure analysis
- File statistics
- Security vulnerabilities
- Code quality issues
- Dependency analysis
- Architecture patterns
"""
import logging
import os
import re
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Project, ProjectIssue, IndexedFile
from app.services.stack_detector import StackDetector
from app.services.file_scanner import FileScanner
from app.services.health_checker import HealthChecker

logger = logging.getLogger(__name__)


class ScanPhase(str, Enum):
    """Scan phases."""
    INITIALIZING = "initializing"
    SCANNING_FILES = "scanning_files"
    ANALYZING_STRUCTURE = "analyzing_structure"
    DETECTING_STACK = "detecting_stack"
    CHECKING_SECURITY = "checking_security"
    CHECKING_QUALITY = "checking_quality"
    ANALYZING_DEPENDENCIES = "analyzing_dependencies"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"


class IssueSeverity(str, Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IssueCategory(str, Enum):
    """Issue categories."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"


@dataclass
class ScanProgress:
    """Scan progress tracking."""
    phase: ScanPhase = ScanPhase.INITIALIZING
    progress: float = 0.0
    message: str = "Starting scan..."
    files_scanned: int = 0
    total_files: int = 0
    issues_found: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class FileInfo:
    """Information about a scanned file."""
    path: str
    relative_path: str
    size: int
    lines: int
    language: str
    category: str
    last_modified: datetime
    has_issues: bool = False
    issues: List[Dict] = field(default_factory=list)


@dataclass
class ScanResult:
    """Complete scan result."""
    project_id: str
    scan_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # File statistics
    total_files: int = 0
    total_lines: int = 0
    total_size_bytes: int = 0
    files_by_language: Dict[str, int] = field(default_factory=dict)
    files_by_category: Dict[str, int] = field(default_factory=dict)

    # Stack detection
    stack: Dict[str, Any] = field(default_factory=dict)

    # Health score
    health_score: float = 0.0
    health_details: Dict[str, Any] = field(default_factory=dict)

    # Issues
    issues: List[Dict] = field(default_factory=list)
    issues_by_severity: Dict[str, int] = field(default_factory=dict)
    issues_by_category: Dict[str, int] = field(default_factory=dict)

    # Structure
    structure: Dict[str, Any] = field(default_factory=dict)

    # Dependencies
    dependencies: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


class ProjectScanner:
    """
    Comprehensive project scanner.

    Performs deep analysis of project files including:
    - File enumeration and statistics
    - Language and framework detection
    - Security vulnerability scanning
    - Code quality analysis
    - Dependency analysis
    - Architecture pattern detection
    """

    # File extensions to scan
    SCANNABLE_EXTENSIONS = {
        '.php', '.js', '.ts', '.jsx', '.tsx', '.vue', '.blade.php',
        '.css', '.scss', '.less', '.json', '.yaml', '.yml', '.xml',
        '.env', '.env.example', '.sql', '.md', '.txt', '.sh',
        '.py', '.rb', '.go', '.rs', '.java', '.kt', '.swift',
    }

    # Directories to skip
    SKIP_DIRECTORIES = {
        'node_modules', 'vendor', '.git', '.svn', '.hg',
        'storage', 'cache', '.cache', 'dist', 'build',
        '__pycache__', '.pytest_cache', '.mypy_cache',
        'coverage', '.coverage', 'logs', 'tmp', 'temp',
    }

    # Security patterns to check
    SECURITY_PATTERNS = {
        'hardcoded_secret': [
            (r'(?:password|secret|api_key|apikey|token|auth)\s*[=:]\s*["\'][^"\']{8,}["\']',
             'Potential hardcoded secret'),
            (r'(?:AWS|AZURE|GCP)_(?:ACCESS|SECRET|API)_KEY\s*=\s*["\'][^"\']+["\']', 'Cloud credential in code'),
        ],
        'sql_injection': [
            (r'->whereRaw\s*\([^)]*\$', 'Potential SQL injection in whereRaw'),
            (r'DB::raw\s*\([^)]*\$', 'Potential SQL injection in DB::raw'),
            (r'->selectRaw\s*\([^)]*\$', 'Potential SQL injection in selectRaw'),
        ],
        'xss': [
            (r'\{\!\!\s*\$[^}]+\!\!\}', 'Unescaped output in Blade template'),
            (r'echo\s+\$_(?:GET|POST|REQUEST)', 'Direct echo of user input'),
        ],
        'file_inclusion': [
            (r'include\s*\(\s*\$', 'Dynamic file inclusion'),
            (r'require\s*\(\s*\$', 'Dynamic file require'),
        ],
        'command_injection': [
            (r'(?:exec|shell_exec|system|passthru)\s*\([^)]*\$', 'Potential command injection'),
            (r'`[^`]*\$[^`]*`', 'Potential command injection in backticks'),
        ],
        'insecure_config': [
            (r'APP_DEBUG\s*=\s*true', 'Debug mode enabled'),
            (r'APP_ENV\s*=\s*(?:local|development)', 'Non-production environment'),
        ],
    }

    # Code quality patterns
    QUALITY_PATTERNS = {
        'long_method': (r'(?:function|public function|private function|protected function)\s+\w+[^}]+\{', 50),
        # > 50 lines
        'god_class': (r'class\s+\w+', 500),  # > 500 lines
        'magic_numbers': r'(?<!\w)(?:0x[0-9a-f]+|\d{3,})(?!\w)',
        'todo_fixme': r'(?:TODO|FIXME|HACK|XXX|BUG)[\s:]+',
        'empty_catch': r'catch\s*\([^)]+\)\s*\{\s*\}',
        'var_dump': r'(?:var_dump|print_r|dd)\s*\(',
        'console_log': r'console\.(?:log|debug|info)\s*\(',
    }

    def __init__(self, db: AsyncSession, project: Project):
        self.db = db
        self.project = project
        self.progress = ScanProgress()
        self.result: Optional[ScanResult] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """Set callback for progress updates."""
        self._progress_callback = callback

    async def _update_progress(
            self,
            phase: ScanPhase,
            progress: float,
            message: str,
            files_scanned: int = None,
    ):
        """Update scan progress."""
        self.progress.phase = phase
        self.progress.progress = progress
        self.progress.message = message
        if files_scanned is not None:
            self.progress.files_scanned = files_scanned

        # Update project in database
        self.project.scan_progress = int(progress * 100)
        self.project.scan_message = message
        await self.db.commit()

        # Call callback if set
        if self._progress_callback:
            await self._progress_callback(self.progress)

        logger.info(f"[SCANNER] {phase.value}: {message} ({progress * 100:.0f}%)")

    async def scan(self) -> ScanResult:
        """
        Perform comprehensive project scan.

        Returns:
            ScanResult with all scan data
        """
        logger.info(f"[SCANNER] Starting scan for project: {self.project.name}")

        self.progress.started_at = datetime.utcnow()
        scan_id = f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        self.result = ScanResult(
            project_id=str(self.project.id),
            scan_id=scan_id,
            started_at=self.progress.started_at,
        )

        try:
            clone_path = self.project.clone_path
            if not clone_path or not os.path.exists(clone_path):
                raise ValueError("Project clone path not found")

            # Phase 1: Scan files
            await self._update_progress(ScanPhase.SCANNING_FILES, 0.1, "Enumerating files...")
            files = await self._scan_files(clone_path)

            # Phase 2: Analyze structure
            await self._update_progress(ScanPhase.ANALYZING_STRUCTURE, 0.25, "Analyzing project structure...")
            await self._analyze_structure(clone_path, files)

            # Phase 3: Detect stack
            await self._update_progress(ScanPhase.DETECTING_STACK, 0.4, "Detecting technology stack...")
            await self._detect_stack(clone_path)

            # Phase 4: Security check
            await self._update_progress(ScanPhase.CHECKING_SECURITY, 0.55, "Checking for security issues...")
            await self._check_security(clone_path, files)

            # Phase 5: Quality check
            await self._update_progress(ScanPhase.CHECKING_QUALITY, 0.7, "Analyzing code quality...")
            await self._check_quality(clone_path, files)

            # Phase 6: Dependency analysis
            await self._update_progress(ScanPhase.ANALYZING_DEPENDENCIES, 0.85, "Analyzing dependencies...")
            await self._analyze_dependencies(clone_path)

            # Phase 7: Generate report
            await self._update_progress(ScanPhase.GENERATING_REPORT, 0.95, "Generating report...")
            await self._generate_report()

            # Complete
            self.result.completed_at = datetime.utcnow()
            self.result.duration_seconds = (
                    self.result.completed_at - self.result.started_at
            ).total_seconds()

            # Update project
            self.project.health_score = self.result.health_score
            self.project.stack = self.result.stack
            self.project.file_stats = {
                "total_files": self.result.total_files,
                "total_lines": self.result.total_lines,
                "by_language": self.result.files_by_language,
                "by_category": self.result.files_by_category,
            }
            self.project.scanned_at = datetime.utcnow()
            await self.db.commit()

            await self._update_progress(ScanPhase.COMPLETED, 1.0, "Scan completed")

            logger.info(f"[SCANNER] Scan completed: {self.result.total_files} files, "
                        f"{len(self.result.issues)} issues, score: {self.result.health_score}")

            return self.result

        except Exception as e:
            logger.error(f"[SCANNER] Scan failed: {e}")
            await self._update_progress(ScanPhase.FAILED, 0, f"Scan failed: {str(e)}")
            raise

    async def _scan_files(self, base_path: str) -> List[FileInfo]:
        """Scan all files in the project."""
        files = []
        total_lines = 0
        total_size = 0

        for root, dirs, filenames in os.walk(base_path):
            # Skip directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRECTORIES]

            for filename in filenames:
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, base_path)

                # Check extension
                ext = os.path.splitext(filename)[1].lower()
                if ext not in self.SCANNABLE_EXTENSIONS:
                    continue

                try:
                    stat = os.stat(file_path)
                    size = stat.st_size
                    modified = datetime.fromtimestamp(stat.st_mtime)

                    # Count lines
                    lines = 0
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = sum(1 for _ in f)
                    except:
                        pass

                    # Determine language and category
                    language = self._get_language(filename, ext)
                    category = self._get_category(relative_path, language)

                    file_info = FileInfo(
                        path=file_path,
                        relative_path=relative_path,
                        size=size,
                        lines=lines,
                        language=language,
                        category=category,
                        last_modified=modified,
                    )
                    files.append(file_info)

                    total_lines += lines
                    total_size += size

                    # Update language stats
                    self.result.files_by_language[language] = \
                        self.result.files_by_language.get(language, 0) + 1

                    # Update category stats
                    self.result.files_by_category[category] = \
                        self.result.files_by_category.get(category, 0) + 1

                except Exception as e:
                    logger.warning(f"[SCANNER] Failed to scan {file_path}: {e}")
                    continue

            # Update progress
            self.progress.files_scanned = len(files)

        self.result.total_files = len(files)
        self.result.total_lines = total_lines
        self.result.total_size_bytes = total_size
        self.progress.total_files = len(files)

        return files

    def _get_language(self, filename: str, ext: str) -> str:
        """Determine file language."""
        language_map = {
            '.php': 'php',
            '.blade.php': 'blade',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.vue': 'vue',
            '.css': 'css',
            '.scss': 'scss',
            '.less': 'less',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.sql': 'sql',
            '.md': 'markdown',
            '.sh': 'shell',
            '.py': 'python',
            '.env': 'env',
        }

        if filename.endswith('.blade.php'):
            return 'blade'

        return language_map.get(ext, 'other')

    def _get_category(self, relative_path: str, language: str) -> str:
        """Determine file category based on path."""
        path_lower = relative_path.lower()

        # Laravel-specific categories
        if 'app/models' in path_lower or 'app/model' in path_lower:
            return 'models'
        if 'app/http/controllers' in path_lower:
            return 'controllers'
        if 'app/services' in path_lower:
            return 'services'
        if 'app/repositories' in path_lower:
            return 'repositories'
        if 'app/http/requests' in path_lower:
            return 'requests'
        if 'app/http/resources' in path_lower:
            return 'resources'
        if 'app/http/middleware' in path_lower:
            return 'middleware'
        if 'app/events' in path_lower:
            return 'events'
        if 'app/listeners' in path_lower:
            return 'listeners'
        if 'app/jobs' in path_lower:
            return 'jobs'
        if 'app/mail' in path_lower:
            return 'mail'
        if 'app/notifications' in path_lower:
            return 'notifications'
        if 'app/policies' in path_lower:
            return 'policies'
        if 'app/providers' in path_lower:
            return 'providers'
        if 'database/migrations' in path_lower:
            return 'migrations'
        if 'database/seeders' in path_lower or 'database/seeds' in path_lower:
            return 'seeders'
        if 'database/factories' in path_lower:
            return 'factories'
        if 'routes/' in path_lower:
            return 'routes'
        if 'config/' in path_lower:
            return 'config'
        if 'resources/views' in path_lower:
            return 'views'
        if 'resources/js' in path_lower or 'resources/ts' in path_lower:
            return 'frontend'
        if 'resources/css' in path_lower:
            return 'styles'
        if 'tests/' in path_lower:
            return 'tests'
        if 'public/' in path_lower:
            return 'public'

        # Generic categories by language
        if language in ['javascript', 'typescript', 'vue', 'jsx', 'tsx']:
            return 'frontend'
        if language in ['css', 'scss', 'less']:
            return 'styles'
        if language == 'json':
            return 'config'

        return 'other'

    async def _analyze_structure(self, base_path: str, files: List[FileInfo]):
        """Analyze project structure."""
        structure = {
            "has_src_directory": os.path.exists(os.path.join(base_path, 'src')),
            "has_app_directory": os.path.exists(os.path.join(base_path, 'app')),
            "has_tests": os.path.exists(os.path.join(base_path, 'tests')),
            "has_docker": os.path.exists(os.path.join(base_path, 'docker-compose.yml')) or
                          os.path.exists(os.path.join(base_path, 'Dockerfile')),
            "has_ci_cd": any([
                os.path.exists(os.path.join(base_path, '.github', 'workflows')),
                os.path.exists(os.path.join(base_path, '.gitlab-ci.yml')),
                os.path.exists(os.path.join(base_path, 'Jenkinsfile')),
            ]),
            "has_readme": os.path.exists(os.path.join(base_path, 'README.md')),
            "has_contributing": os.path.exists(os.path.join(base_path, 'CONTRIBUTING.md')),
            "has_license": any([
                os.path.exists(os.path.join(base_path, 'LICENSE')),
                os.path.exists(os.path.join(base_path, 'LICENSE.md')),
            ]),
            "directories": {},
            "patterns_detected": [],
        }

        # Count files per directory
        for f in files:
            dir_name = os.path.dirname(f.relative_path).split(os.sep)[0] if os.sep in f.relative_path else '.'
            structure["directories"][dir_name] = structure["directories"].get(dir_name, 0) + 1

        # Detect patterns
        if structure["has_app_directory"]:
            structure["patterns_detected"].append("Laravel MVC")
        if os.path.exists(os.path.join(base_path, 'app', 'Services')):
            structure["patterns_detected"].append("Service Layer")
        if os.path.exists(os.path.join(base_path, 'app', 'Repositories')):
            structure["patterns_detected"].append("Repository Pattern")
        if os.path.exists(os.path.join(base_path, 'app', 'Actions')):
            structure["patterns_detected"].append("Action Classes")

        self.result.structure = structure

    async def _detect_stack(self, base_path: str):
        """Detect technology stack."""
        detector = StackDetector(base_path)
        stack = detector.detect()
        self.result.stack = stack

    async def _check_security(self, base_path: str, files: List[FileInfo]):
        """Check for security issues."""
        for file_info in files:
            if file_info.language not in ['php', 'blade', 'javascript', 'typescript', 'env']:
                continue

            try:
                with open(file_info.path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                for category, patterns in self.SECURITY_PATTERNS.items():
                    for pattern, description in patterns:
                        for i, line in enumerate(lines, 1):
                            if re.search(pattern, line, re.IGNORECASE):
                                issue = {
                                    "category": IssueCategory.SECURITY.value,
                                    "severity": IssueSeverity.CRITICAL.value if category in ['hardcoded_secret',
                                                                                             'sql_injection'] else IssueSeverity.WARNING.value,
                                    "title": f"Security: {category.replace('_', ' ').title()}",
                                    "description": description,
                                    "file_path": file_info.relative_path,
                                    "line_number": i,
                                    "suggestion": f"Review and fix the {category.replace('_', ' ')} issue",
                                    "auto_fixable": False,
                                }
                                self.result.issues.append(issue)
                                file_info.has_issues = True
                                file_info.issues.append(issue)

            except Exception as e:
                logger.warning(f"[SCANNER] Security check failed for {file_info.path}: {e}")

    async def _check_quality(self, base_path: str, files: List[FileInfo]):
        """Check code quality issues."""
        for file_info in files:
            if file_info.language not in ['php', 'javascript', 'typescript', 'blade']:
                continue

            try:
                with open(file_info.path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                # Check for TODO/FIXME
                for i, line in enumerate(lines, 1):
                    if re.search(self.QUALITY_PATTERNS['todo_fixme'], line):
                        issue = {
                            "category": IssueCategory.CODE_QUALITY.value,
                            "severity": IssueSeverity.INFO.value,
                            "title": "TODO/FIXME comment found",
                            "description": f"Found TODO or FIXME comment",
                            "file_path": file_info.relative_path,
                            "line_number": i,
                            "suggestion": "Address the TODO/FIXME or create a ticket",
                            "auto_fixable": False,
                        }
                        self.result.issues.append(issue)

                # Check for debug statements
                for i, line in enumerate(lines, 1):
                    if re.search(self.QUALITY_PATTERNS['var_dump'], line) or \
                            re.search(self.QUALITY_PATTERNS['console_log'], line):
                        issue = {
                            "category": IssueCategory.CODE_QUALITY.value,
                            "severity": IssueSeverity.WARNING.value,
                            "title": "Debug statement found",
                            "description": "Debug statement should be removed before production",
                            "file_path": file_info.relative_path,
                            "line_number": i,
                            "suggestion": "Remove debug statements",
                            "auto_fixable": True,
                        }
                        self.result.issues.append(issue)

                # Check for empty catch blocks
                for i, line in enumerate(lines, 1):
                    if re.search(self.QUALITY_PATTERNS['empty_catch'], line):
                        issue = {
                            "category": IssueCategory.CODE_QUALITY.value,
                            "severity": IssueSeverity.WARNING.value,
                            "title": "Empty catch block",
                            "description": "Empty catch blocks hide errors",
                            "file_path": file_info.relative_path,
                            "line_number": i,
                            "suggestion": "Add error handling or logging in catch block",
                            "auto_fixable": False,
                        }
                        self.result.issues.append(issue)

                # Check file length (potential god class)
                if file_info.lines > 500:
                    issue = {
                        "category": IssueCategory.ARCHITECTURE.value,
                        "severity": IssueSeverity.WARNING.value,
                        "title": "Large file detected",
                        "description": f"File has {file_info.lines} lines, consider splitting",
                        "file_path": file_info.relative_path,
                        "line_number": None,
                        "suggestion": "Consider breaking down into smaller classes/modules",
                        "auto_fixable": False,
                    }
                    self.result.issues.append(issue)

            except Exception as e:
                logger.warning(f"[SCANNER] Quality check failed for {file_info.path}: {e}")

    async def _analyze_dependencies(self, base_path: str):
        """Analyze project dependencies."""
        dependencies = {
            "php": {},
            "npm": {},
            "outdated": [],
            "security_alerts": [],
        }

        # Parse composer.json
        composer_path = os.path.join(base_path, 'composer.json')
        if os.path.exists(composer_path):
            try:
                with open(composer_path, 'r') as f:
                    composer = json.load(f)
                    dependencies["php"] = {
                        "require": composer.get("require", {}),
                        "require-dev": composer.get("require-dev", {}),
                    }
            except Exception as e:
                logger.warning(f"[SCANNER] Failed to parse composer.json: {e}")

        # Parse package.json
        package_path = os.path.join(base_path, 'package.json')
        if os.path.exists(package_path):
            try:
                with open(package_path, 'r') as f:
                    package = json.load(f)
                    dependencies["npm"] = {
                        "dependencies": package.get("dependencies", {}),
                        "devDependencies": package.get("devDependencies", {}),
                    }
            except Exception as e:
                logger.warning(f"[SCANNER] Failed to parse package.json: {e}")

        self.result.dependencies = dependencies

    async def _generate_report(self):
        """Generate final scan report."""
        # Calculate issue statistics
        for issue in self.result.issues:
            severity = issue.get("severity", "info")
            category = issue.get("category", "other")

            self.result.issues_by_severity[severity] = \
                self.result.issues_by_severity.get(severity, 0) + 1
            self.result.issues_by_category[category] = \
                self.result.issues_by_category.get(category, 0) + 1

        self.progress.issues_found = len(self.result.issues)

        # Calculate health score
        base_score = 100

        # Deduct for issues
        critical_count = self.result.issues_by_severity.get(IssueSeverity.CRITICAL.value, 0)
        warning_count = self.result.issues_by_severity.get(IssueSeverity.WARNING.value, 0)
        info_count = self.result.issues_by_severity.get(IssueSeverity.INFO.value, 0)

        base_score -= critical_count * 10
        base_score -= warning_count * 3
        base_score -= info_count * 0.5

        # Bonus for good practices
        if self.result.structure.get("has_tests"):
            base_score += 5
        if self.result.structure.get("has_ci_cd"):
            base_score += 5
        if self.result.structure.get("has_readme"):
            base_score += 2
        if "Service Layer" in self.result.structure.get("patterns_detected", []):
            base_score += 3

        self.result.health_score = max(0, min(100, base_score))

        self.result.health_details = {
            "base_score": 100,
            "critical_deductions": critical_count * 10,
            "warning_deductions": warning_count * 3,
            "info_deductions": info_count * 0.5,
            "bonuses": {
                "has_tests": self.result.structure.get("has_tests", False),
                "has_ci_cd": self.result.structure.get("has_ci_cd", False),
                "has_readme": self.result.structure.get("has_readme", False),
            },
            "final_score": self.result.health_score,
        }

        # Store issues in database
        await self._store_issues()

    async def _store_issues(self):
        """Store discovered issues in database."""
        # Clear existing issues
        stmt = select(ProjectIssue).where(ProjectIssue.project_id == self.project.id)
        result = await self.db.execute(stmt)
        existing = result.scalars().all()
        for issue in existing:
            await self.db.delete(issue)

        # Add new issues
        for issue_data in self.result.issues:
            issue = ProjectIssue(
                project_id=str(self.project.id),
                category=issue_data.get("category"),
                severity=issue_data.get("severity"),
                title=issue_data.get("title"),
                description=issue_data.get("description"),
                file_path=issue_data.get("file_path"),
                line_number=issue_data.get("line_number"),
                suggestion=issue_data.get("suggestion"),
                auto_fixable=issue_data.get("auto_fixable", False),
                status="open",
            )
            self.db.add(issue)

        await self.db.commit()