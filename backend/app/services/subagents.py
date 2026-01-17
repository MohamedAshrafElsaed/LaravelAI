"""
Subagents Service for Specialized AI Tasks.

Provides specialized AI agents for specific domains like security review,
performance analysis, test generation, and migration planning.
Each subagent has optimized prompts and tools for their domain.
"""
import asyncio
import logging
import time
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.prompt_cache import PromptCacheService, get_prompt_cache_service

logger = logging.getLogger(__name__)

# Import operations logger (lazy to avoid circular imports)
_ops_logger = None

def _get_ops_logger():
    """Lazy load operations logger."""
    global _ops_logger
    if _ops_logger is None:
        try:
            from app.services.ai_operations_logger import get_operations_logger
            _ops_logger = get_operations_logger()
        except ImportError:
            pass
    return _ops_logger


class SubagentType(str, Enum):
    """Types of specialized subagents."""
    SECURITY_REVIEWER = "security-reviewer"
    PERFORMANCE_ANALYZER = "performance-analyzer"
    TEST_GENERATOR = "test-generator"
    MIGRATION_PLANNER = "migration-planner"
    DOCUMENTATION_WRITER = "documentation-writer"
    CODE_REFACTORER = "code-refactorer"
    API_DESIGNER = "api-designer"
    DATABASE_OPTIMIZER = "database-optimizer"


class SubagentModel(str, Enum):
    """Models available for subagents."""
    HAIKU = "claude-haiku-4-5-20251001"
    SONNET = "claude-sonnet-4-5-20250929"


@dataclass
class SubagentResult:
    """Result from a subagent execution."""
    success: bool
    subagent_type: SubagentType
    content: Optional[str] = None
    data: Optional[dict] = None
    error: Optional[str] = None
    tokens_used: int = 0
    latency_ms: int = 0
    cache_hit: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "subagent_type": self.subagent_type.value,
            "content": self.content,
            "data": self.data,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "cache_hit": self.cache_hit,
            "metadata": self.metadata,
        }


@dataclass
class SubagentConfig:
    """Configuration for a subagent."""
    agent_type: SubagentType
    description: str
    system_prompt: str
    model: SubagentModel = SubagentModel.SONNET
    temperature: float = 0.5
    max_tokens: int = 4096
    tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent_type": self.agent_type.value,
            "description": self.description,
            "model": self.model.value,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools": self.tools,
        }


# Predefined Subagent Configurations
SUBAGENT_CONFIGS = {
    SubagentType.SECURITY_REVIEWER: SubagentConfig(
        agent_type=SubagentType.SECURITY_REVIEWER,
        description="Security vulnerability scanner for Laravel applications",
        system_prompt="""You are an expert security reviewer specializing in Laravel and PHP applications.
Your role is to identify security vulnerabilities and provide actionable remediation advice.

Key areas to analyze:
1. **SQL Injection**: Check for raw queries, improper use of Query Builder
2. **XSS (Cross-Site Scripting)**: Check Blade templates for unescaped output
3. **CSRF**: Verify CSRF tokens on forms and AJAX requests
4. **Authentication Issues**: Check auth middleware, password hashing, session management
5. **Authorization**: Verify policies, gates, and permission checks
6. **Mass Assignment**: Check $fillable and $guarded on models
7. **File Upload**: Validate file types, storage locations, permissions
8. **Sensitive Data**: Check for hardcoded secrets, exposed .env values
9. **Input Validation**: Verify request validation rules
10. **Dependencies**: Flag known vulnerable packages

For each issue found, provide:
- Severity (critical/high/medium/low)
- Location (file and line number if possible)
- Description of the vulnerability
- CWE ID if applicable
- Specific code fix recommendation""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),

    SubagentType.PERFORMANCE_ANALYZER: SubagentConfig(
        agent_type=SubagentType.PERFORMANCE_ANALYZER,
        description="Performance optimization expert for Laravel applications",
        system_prompt="""You are a performance optimization expert for Laravel applications.
Your role is to identify performance bottlenecks and suggest optimizations.

Key areas to analyze:
1. **N+1 Query Problems**: Check for eager loading opportunities
2. **Database Queries**: Identify slow queries, missing indexes
3. **Caching Opportunities**: Suggest where to add caching
4. **Memory Usage**: Check for memory leaks, large collections
5. **API Response Times**: Optimize response payloads
6. **Queue Optimization**: Suggest queueable operations
7. **Asset Optimization**: Check for unoptimized assets
8. **Lazy Loading**: Identify opportunities for lazy loading
9. **Chunking**: Suggest chunking for large datasets
10. **Query Optimization**: Suggest query improvements

For each issue found, provide:
- Impact level (high/medium/low)
- Location (file and line)
- Current performance concern
- Recommended optimization
- Expected improvement estimate""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),

    SubagentType.TEST_GENERATOR: SubagentConfig(
        agent_type=SubagentType.TEST_GENERATOR,
        description="Test case generator for Laravel applications",
        system_prompt="""You are an expert test engineer for Laravel applications.
Your role is to generate comprehensive test cases using PHPUnit and Laravel testing utilities.

Test types to generate:
1. **Unit Tests**: Test individual classes and methods
2. **Feature Tests**: Test HTTP endpoints and responses
3. **Integration Tests**: Test component interactions
4. **Database Tests**: Test model relationships and queries
5. **Browser Tests**: Suggest Dusk tests for UI

For each test:
- Use Laravel's testing conventions and helpers
- Include setUp and tearDown when needed
- Use factories and seeders appropriately
- Test both success and failure cases
- Include edge cases
- Use meaningful test names
- Add assertions for all expected outcomes

Generate tests that:
- Are isolated and don't depend on external state
- Use RefreshDatabase trait when appropriate
- Mock external services
- Follow AAA pattern (Arrange, Act, Assert)""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),

    SubagentType.MIGRATION_PLANNER: SubagentConfig(
        agent_type=SubagentType.MIGRATION_PLANNER,
        description="Database migration planner for Laravel applications",
        system_prompt="""You are a database architect specializing in Laravel migrations.
Your role is to plan safe, reversible database migrations.

Key considerations:
1. **Schema Changes**: Plan incremental schema changes
2. **Data Migrations**: Handle data transformations safely
3. **Rollback Safety**: Ensure all migrations are reversible
4. **Zero Downtime**: Plan for zero-downtime deployments
5. **Foreign Keys**: Handle constraints properly
6. **Indexes**: Add appropriate indexes for performance
7. **Column Types**: Choose appropriate column types
8. **Nullable Fields**: Handle null values correctly

For each migration:
- Provide up() and down() methods
- Consider data preservation
- Include any seeder updates needed
- Note deployment order if multiple migrations
- Warn about potential data loss
- Suggest backup procedures""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),

    SubagentType.DOCUMENTATION_WRITER: SubagentConfig(
        agent_type=SubagentType.DOCUMENTATION_WRITER,
        description="Technical documentation writer",
        system_prompt="""You are a technical writer specializing in Laravel documentation.
Your role is to create clear, comprehensive documentation.

Documentation types:
1. **API Documentation**: OpenAPI/Swagger specs, endpoint docs
2. **Code Documentation**: PHPDoc blocks, inline comments
3. **README Files**: Project setup and usage instructions
4. **Architecture Docs**: System design documentation
5. **User Guides**: End-user documentation

For each documentation piece:
- Use clear, concise language
- Include code examples
- Follow Laravel documentation style
- Add diagrams where helpful (Mermaid)
- Include versioning information
- Note any prerequisites""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),

    SubagentType.CODE_REFACTORER: SubagentConfig(
        agent_type=SubagentType.CODE_REFACTORER,
        description="Code refactoring specialist",
        system_prompt="""You are a code refactoring expert for Laravel applications.
Your role is to improve code quality while preserving functionality.

Refactoring areas:
1. **SOLID Principles**: Apply single responsibility, open/closed, etc.
2. **Design Patterns**: Apply appropriate patterns
3. **Code Duplication**: Extract common code
4. **Complexity Reduction**: Simplify complex methods
5. **Naming Improvements**: Improve variable/method names
6. **Type Safety**: Add type hints and return types
7. **Laravel Best Practices**: Follow Laravel conventions

For each refactoring:
- Explain the problem with current code
- Show the refactored version
- Explain the benefits
- Note any breaking changes
- Suggest tests to verify behavior""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),

    SubagentType.API_DESIGNER: SubagentConfig(
        agent_type=SubagentType.API_DESIGNER,
        description="RESTful API designer for Laravel",
        system_prompt="""You are an API design expert for Laravel applications.
Your role is to design clean, RESTful APIs following best practices.

Design considerations:
1. **REST Conventions**: Proper resource naming, HTTP methods
2. **Versioning**: API versioning strategies
3. **Authentication**: OAuth, Sanctum, Passport
4. **Rate Limiting**: Throttling configuration
5. **Response Format**: Consistent JSON structure
6. **Error Handling**: Standardized error responses
7. **Pagination**: Cursor vs offset pagination
8. **Filtering/Sorting**: Query parameter conventions
9. **Documentation**: OpenAPI/Swagger specs

For each API endpoint:
- Define the route and controller
- Specify request validation
- Define response structure
- Include error responses
- Add authentication requirements
- Include example requests/responses""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),

    SubagentType.DATABASE_OPTIMIZER: SubagentConfig(
        agent_type=SubagentType.DATABASE_OPTIMIZER,
        description="Database optimization specialist",
        system_prompt="""You are a database optimization expert for Laravel applications.
Your role is to optimize database schema and queries.

Optimization areas:
1. **Query Optimization**: Rewrite slow queries
2. **Index Design**: Add appropriate indexes
3. **Schema Design**: Normalize/denormalize as needed
4. **Relationship Optimization**: Improve model relationships
5. **Caching Strategy**: Implement query caching
6. **Partitioning**: Suggest table partitioning
7. **Connection Pooling**: Optimize connections

For each optimization:
- Show the current problem
- Provide the optimized solution
- Explain the improvement
- Include benchmark expectations
- Note any trade-offs""",
        model=SubagentModel.SONNET,
        tools=["Read", "Grep", "Glob"],
    ),
}


class Subagent:
    """
    Specialized AI agent for a specific domain.
    """

    def __init__(
        self,
        config: SubagentConfig,
        api_key: Optional[str] = None,
        cache_service: Optional[PromptCacheService] = None,
    ):
        """
        Initialize a subagent.

        Args:
            config: Subagent configuration
            api_key: Anthropic API key
            cache_service: Optional prompt cache service
        """
        self.config = config
        self.api_key = api_key or settings.anthropic_api_key
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        self.cache_service = cache_service

        logger.info(f"[SUBAGENT:{config.agent_type.value}] Initialized")

    async def execute(
        self,
        task: str,
        context: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> SubagentResult:
        """
        Execute the subagent's task.

        Args:
            task: Task description
            context: Code or file context
            project_context: Optional project information

        Returns:
            SubagentResult with execution results
        """
        logger.info(f"[SUBAGENT:{self.config.agent_type.value}] Executing task")
        start_time = time.time()

        # Log subagent start
        ops_logger = _get_ops_logger()
        if ops_logger:
            ops_logger.log_subagent(
                agent_type=self.config.agent_type.value,
                action="start",
            )

        try:
            # Build the user message
            user_content = f"Task: {task}"
            if context:
                user_content += f"\n\nCode Context:\n```\n{context}\n```"
            if project_context:
                user_content += f"\n\nProject Info:\n{project_context}"

            # Use cache service if available
            if self.cache_service:
                response = await self.cache_service.chat_with_cache(
                    messages=[{"role": "user", "content": user_content}],
                    system_prompt=self.config.system_prompt,
                    project_context=project_context,
                    code_context=context,
                    model=self.config.model.value,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )

                total_tokens = response.input_tokens + response.output_tokens

                # Log subagent completion
                if ops_logger:
                    ops_logger.log_subagent(
                        agent_type=self.config.agent_type.value,
                        action="end",
                        tokens=total_tokens,
                        duration_ms=response.latency_ms,
                        cache_hit=response.cache_hit,
                    )

                return SubagentResult(
                    success=True,
                    subagent_type=self.config.agent_type,
                    content=response.content,
                    tokens_used=total_tokens,
                    latency_ms=response.latency_ms,
                    cache_hit=response.cache_hit,
                    metadata={
                        "cache_read_tokens": response.cache_read_input_tokens,
                        "cost_savings": response.cost_savings_estimate,
                    },
                )
            else:
                # Direct API call without caching
                response = await self.async_client.messages.create(
                    model=self.config.model.value,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=self.config.system_prompt,
                    messages=[{"role": "user", "content": user_content}],
                )

                latency_ms = int((time.time() - start_time) * 1000)

                return SubagentResult(
                    success=True,
                    subagent_type=self.config.agent_type,
                    content=response.content[0].text,
                    tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                    latency_ms=latency_ms,
                )

        except Exception as e:
            logger.error(f"[SUBAGENT:{self.config.agent_type.value}] Error: {e}")
            return SubagentResult(
                success=False,
                subagent_type=self.config.agent_type,
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )


class SubagentManager:
    """
    Manages multiple subagents and coordinates their execution.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        enable_caching: bool = True,
    ):
        """
        Initialize the subagent manager.

        Args:
            api_key: Anthropic API key
            enable_caching: Whether to enable prompt caching
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.cache_service = get_prompt_cache_service() if enable_caching else None
        self._subagents: dict[SubagentType, Subagent] = {}

        logger.info(f"[SUBAGENT_MANAGER] Initialized with caching={'enabled' if enable_caching else 'disabled'}")

    def _get_subagent(self, agent_type: SubagentType) -> Subagent:
        """Get or create a subagent."""
        if agent_type not in self._subagents:
            config = SUBAGENT_CONFIGS.get(agent_type)
            if not config:
                raise ValueError(f"Unknown subagent type: {agent_type}")

            self._subagents[agent_type] = Subagent(
                config=config,
                api_key=self.api_key,
                cache_service=self.cache_service,
            )

        return self._subagents[agent_type]

    async def run_subagent(
        self,
        agent_type: SubagentType,
        task: str,
        context: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> SubagentResult:
        """
        Run a single subagent.

        Args:
            agent_type: Type of subagent to run
            task: Task description
            context: Code context
            project_context: Project information

        Returns:
            SubagentResult
        """
        subagent = self._get_subagent(agent_type)
        return await subagent.execute(task, context, project_context)

    async def run_parallel(
        self,
        tasks: list[dict],
    ) -> list[SubagentResult]:
        """
        Run multiple subagents in parallel.

        Args:
            tasks: List of dicts with 'agent_type', 'task', 'context', 'project_context'

        Returns:
            List of SubagentResult
        """
        logger.info(f"[SUBAGENT_MANAGER] Running {len(tasks)} subagents in parallel")

        async def run_task(task_config: dict) -> SubagentResult:
            return await self.run_subagent(
                agent_type=task_config["agent_type"],
                task=task_config["task"],
                context=task_config.get("context"),
                project_context=task_config.get("project_context"),
            )

        results = await asyncio.gather(*[run_task(t) for t in tasks])
        return list(results)

    async def security_review(
        self,
        code: str,
        file_path: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> SubagentResult:
        """
        Run security review on code.

        Args:
            code: Code to review
            file_path: Optional file path
            project_context: Project information

        Returns:
            SubagentResult with security findings
        """
        task = f"Perform a comprehensive security review of this code"
        if file_path:
            task += f" from {file_path}"

        return await self.run_subagent(
            agent_type=SubagentType.SECURITY_REVIEWER,
            task=task,
            context=code,
            project_context=project_context,
        )

    async def performance_analysis(
        self,
        code: str,
        file_path: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> SubagentResult:
        """
        Run performance analysis on code.

        Args:
            code: Code to analyze
            file_path: Optional file path
            project_context: Project information

        Returns:
            SubagentResult with performance findings
        """
        task = f"Analyze the performance of this code and identify bottlenecks"
        if file_path:
            task += f" from {file_path}"

        return await self.run_subagent(
            agent_type=SubagentType.PERFORMANCE_ANALYZER,
            task=task,
            context=code,
            project_context=project_context,
        )

    async def generate_tests(
        self,
        code: str,
        file_path: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> SubagentResult:
        """
        Generate tests for code.

        Args:
            code: Code to test
            file_path: Optional file path
            project_context: Project information

        Returns:
            SubagentResult with generated tests
        """
        task = f"Generate comprehensive PHPUnit tests for this code"
        if file_path:
            task += f" from {file_path}"

        return await self.run_subagent(
            agent_type=SubagentType.TEST_GENERATOR,
            task=task,
            context=code,
            project_context=project_context,
        )

    async def plan_migration(
        self,
        requirements: str,
        current_schema: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> SubagentResult:
        """
        Plan database migrations.

        Args:
            requirements: Migration requirements
            current_schema: Current database schema
            project_context: Project information

        Returns:
            SubagentResult with migration plan
        """
        return await self.run_subagent(
            agent_type=SubagentType.MIGRATION_PLANNER,
            task=requirements,
            context=current_schema,
            project_context=project_context,
        )

    async def comprehensive_review(
        self,
        code: str,
        file_path: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> dict[str, SubagentResult]:
        """
        Run multiple subagents for a comprehensive code review.

        Args:
            code: Code to review
            file_path: Optional file path
            project_context: Project information

        Returns:
            Dict of SubagentType -> SubagentResult
        """
        logger.info("[SUBAGENT_MANAGER] Running comprehensive review")

        tasks = [
            {
                "agent_type": SubagentType.SECURITY_REVIEWER,
                "task": f"Security review of {file_path or 'code'}",
                "context": code,
                "project_context": project_context,
            },
            {
                "agent_type": SubagentType.PERFORMANCE_ANALYZER,
                "task": f"Performance analysis of {file_path or 'code'}",
                "context": code,
                "project_context": project_context,
            },
            {
                "agent_type": SubagentType.CODE_REFACTORER,
                "task": f"Refactoring suggestions for {file_path or 'code'}",
                "context": code,
                "project_context": project_context,
            },
        ]

        results = await self.run_parallel(tasks)

        return {
            result.subagent_type.value: result
            for result in results
        }

    def list_available_subagents(self) -> list[dict]:
        """List all available subagent types with their descriptions."""
        return [
            config.to_dict()
            for config in SUBAGENT_CONFIGS.values()
        ]

    def get_cache_stats(self) -> Optional[dict]:
        """Get caching statistics if caching is enabled."""
        if self.cache_service:
            return self.cache_service.get_total_savings()
        return None


# Factory function
def get_subagent_manager(enable_caching: bool = True) -> SubagentManager:
    """Get a subagent manager instance."""
    return SubagentManager(enable_caching=enable_caching)
