"""
Batch Processing Service for Claude API.

Provides batch processing capabilities for bulk file analysis with 50% cost savings.
Uses Anthropic's Message Batches API for efficient parallel processing.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


class BatchStatus(str, Enum):
    """Status of a batch processing job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchRequestType(str, Enum):
    """Types of batch requests."""
    FILE_ANALYSIS = "file_analysis"
    CODE_REVIEW = "code_review"
    ARCHITECTURE_REVIEW = "architecture_review"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    DOCUMENTATION_GENERATION = "documentation_generation"


@dataclass
class BatchRequest:
    """Individual request within a batch."""
    custom_id: str
    file_path: Optional[str] = None
    content: str = ""
    request_type: BatchRequestType = BatchRequestType.FILE_ANALYSIS
    metadata: dict = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of a single batch request."""
    custom_id: str
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    processing_time_ms: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "custom_id": self.custom_id,
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class BatchJob:
    """Represents a batch processing job."""
    id: str
    status: BatchStatus
    total_requests: int
    completed_requests: int = 0
    failed_requests: int = 0
    results: list[BatchResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    total_tokens: int = 0
    total_cost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "total_requests": self.total_requests,
            "completed_requests": self.completed_requests,
            "failed_requests": self.failed_requests,
            "results": [r.to_dict() for r in self.results],
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
        }


class BatchProcessor:
    """
    Service for batch processing of Claude API requests.

    Provides 50% cost savings for bulk operations by using the Message Batches API.
    Supports file analysis, code review, security scanning, and more.
    """

    # Batch API provides 50% discount
    BATCH_DISCOUNT = 0.5

    # Default batch settings
    MAX_BATCH_SIZE = 100
    POLL_INTERVAL_SECONDS = 5
    MAX_POLL_ATTEMPTS = 360  # 30 minutes max wait

    def __init__(
        self,
        api_key: Optional[str] = None,
        progress_callback: Optional[Callable[[BatchJob], Any]] = None,
    ):
        """
        Initialize the batch processor.

        Args:
            api_key: Anthropic API key. Uses settings if not provided.
            progress_callback: Optional callback for progress updates.
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        self.progress_callback = progress_callback

        # Active jobs tracking
        self._active_jobs: dict[str, BatchJob] = {}

        logger.info("[BATCH_PROCESSOR] Initialized with batch processing support")

    def _get_system_prompt(self, request_type: BatchRequestType) -> str:
        """Get system prompt based on request type."""
        prompts = {
            BatchRequestType.FILE_ANALYSIS: """You are an expert code analyst. Analyze the provided code file and return a JSON response with:
- summary: Brief description of what the file does
- complexity: low/medium/high
- issues: Array of potential issues found
- suggestions: Array of improvement suggestions
- dependencies: Array of external dependencies used
- patterns: Array of design patterns detected""",

            BatchRequestType.CODE_REVIEW: """You are a senior code reviewer. Review the provided code and return a JSON response with:
- quality_score: 0-100
- issues: Array of {severity: critical/warning/info, message: string, line: number}
- security_concerns: Array of security issues
- performance_issues: Array of performance concerns
- best_practices: Array of best practice violations
- refactoring_suggestions: Array of suggested refactors""",

            BatchRequestType.ARCHITECTURE_REVIEW: """You are a software architect. Analyze the code for architectural patterns and return a JSON response with:
- patterns_detected: Array of design patterns used
- architecture_style: The overall architecture style (MVC, microservices, etc.)
- coupling_analysis: Analysis of code coupling
- cohesion_analysis: Analysis of code cohesion
- solid_compliance: SOLID principle compliance analysis
- recommendations: Array of architectural recommendations""",

            BatchRequestType.SECURITY_SCAN: """You are a security expert. Scan the provided code for vulnerabilities and return a JSON response with:
- vulnerability_score: 0-100 (100 = most secure)
- vulnerabilities: Array of {type: string, severity: critical/high/medium/low, description: string, line: number, cwe_id: string}
- sql_injection_risks: Array of SQL injection vulnerabilities
- xss_risks: Array of XSS vulnerabilities
- authentication_issues: Array of auth-related issues
- recommendations: Array of security recommendations""",

            BatchRequestType.PERFORMANCE_ANALYSIS: """You are a performance optimization expert. Analyze the code for performance and return a JSON response with:
- performance_score: 0-100
- bottlenecks: Array of {location: string, issue: string, impact: high/medium/low}
- n_plus_one_queries: Array of potential N+1 query issues
- memory_concerns: Array of memory-related issues
- optimization_suggestions: Array of optimization recommendations
- caching_opportunities: Array of caching suggestions""",

            BatchRequestType.DOCUMENTATION_GENERATION: """You are a technical writer. Generate documentation for the provided code and return a JSON response with:
- description: Overall description of the code
- purpose: What the code accomplishes
- usage_examples: Array of usage examples
- parameters: Array of {name: string, type: string, description: string}
- return_value: Description of return value
- related_code: Array of related files/classes""",
        }
        return prompts.get(request_type, prompts[BatchRequestType.FILE_ANALYSIS])

    async def _notify_progress(self, job: BatchJob) -> None:
        """Notify progress callback if set."""
        if self.progress_callback:
            try:
                result = self.progress_callback(job)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"[BATCH_PROCESSOR] Progress callback error: {e}")

    async def create_batch(
        self,
        requests: list[BatchRequest],
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
    ) -> BatchJob:
        """
        Create and submit a batch processing job.

        Args:
            requests: List of BatchRequest objects to process
            model: Claude model to use
            max_tokens: Maximum tokens per response

        Returns:
            BatchJob with batch ID and initial status
        """
        if len(requests) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Batch size exceeds maximum of {self.MAX_BATCH_SIZE}")

        job_id = str(uuid.uuid4())
        logger.info(f"[BATCH_PROCESSOR] Creating batch job {job_id} with {len(requests)} requests")

        # Create job tracking object
        job = BatchJob(
            id=job_id,
            status=BatchStatus.PENDING,
            total_requests=len(requests),
        )
        self._active_jobs[job_id] = job

        try:
            # Build batch requests
            batch_requests = []
            for req in requests:
                system_prompt = self._get_system_prompt(req.request_type)

                user_content = f"File: {req.file_path}\n\n```\n{req.content}\n```" if req.file_path else req.content

                batch_requests.append({
                    "custom_id": req.custom_id,
                    "params": {
                        "model": model,
                        "max_tokens": max_tokens,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": user_content}
                        ],
                    }
                })

            # Submit batch to API
            logger.info(f"[BATCH_PROCESSOR] Submitting batch {job_id} to Anthropic API")

            message_batch = self.client.messages.batches.create(
                requests=batch_requests
            )

            job.status = BatchStatus.PROCESSING
            job.metadata = {"anthropic_batch_id": message_batch.id}  # Store Anthropic's batch ID

            logger.info(f"[BATCH_PROCESSOR] Batch {job_id} submitted successfully, Anthropic batch ID: {message_batch.id}")

            await self._notify_progress(job)
            return job

        except Exception as e:
            logger.error(f"[BATCH_PROCESSOR] Failed to create batch {job_id}: {e}")
            job.status = BatchStatus.FAILED
            job.error = str(e)
            await self._notify_progress(job)
            return job

    async def poll_batch(
        self,
        job: BatchJob,
        wait_for_completion: bool = True,
    ) -> BatchJob:
        """
        Poll a batch job for completion.

        Args:
            job: BatchJob to poll
            wait_for_completion: If True, blocks until completion

        Returns:
            Updated BatchJob with results
        """
        if job.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]:
            return job

        anthropic_batch_id = job.metadata.get("anthropic_batch_id")
        if not anthropic_batch_id:
            job.status = BatchStatus.FAILED
            job.error = "No Anthropic batch ID found"
            return job

        logger.info(f"[BATCH_PROCESSOR] Polling batch {job.id} (Anthropic ID: {anthropic_batch_id})")

        poll_count = 0
        while poll_count < self.MAX_POLL_ATTEMPTS:
            try:
                # Check batch status
                batch_status = self.client.messages.batches.retrieve(anthropic_batch_id)

                # Update progress
                job.completed_requests = batch_status.request_counts.succeeded
                job.failed_requests = batch_status.request_counts.errored

                logger.info(
                    f"[BATCH_PROCESSOR] Batch {job.id} progress: "
                    f"{job.completed_requests}/{job.total_requests} completed, "
                    f"{job.failed_requests} failed"
                )

                await self._notify_progress(job)

                # Check if complete
                if batch_status.processing_status == "ended":
                    job.status = BatchStatus.COMPLETED
                    job.completed_at = datetime.utcnow()

                    # Fetch results
                    results = []
                    for result in self.client.messages.batches.results(anthropic_batch_id):
                        if result.result.type == "succeeded":
                            message = result.result.message
                            content = message.content[0].text if message.content else ""
                            tokens = message.usage.input_tokens + message.usage.output_tokens

                            results.append(BatchResult(
                                custom_id=result.custom_id,
                                success=True,
                                content=content,
                                tokens_used=tokens,
                            ))
                            job.total_tokens += tokens
                        else:
                            results.append(BatchResult(
                                custom_id=result.custom_id,
                                success=False,
                                error=str(result.result.error) if hasattr(result.result, 'error') else "Unknown error",
                            ))

                    job.results = results

                    # Calculate cost (with 50% batch discount)
                    job.total_cost = self._calculate_cost(job.total_tokens) * self.BATCH_DISCOUNT

                    logger.info(
                        f"[BATCH_PROCESSOR] Batch {job.id} completed: "
                        f"{job.completed_requests} succeeded, {job.failed_requests} failed, "
                        f"{job.total_tokens} tokens, ${job.total_cost:.4f}"
                    )

                    await self._notify_progress(job)
                    return job

                if not wait_for_completion:
                    return job

                # Wait before next poll
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                poll_count += 1

            except Exception as e:
                logger.error(f"[BATCH_PROCESSOR] Error polling batch {job.id}: {e}")
                if not wait_for_completion:
                    return job
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                poll_count += 1

        # Timeout
        job.status = BatchStatus.FAILED
        job.error = "Polling timeout exceeded"
        logger.error(f"[BATCH_PROCESSOR] Batch {job.id} polling timeout")
        return job

    def _calculate_cost(self, total_tokens: int) -> float:
        """Calculate estimated cost for tokens (before batch discount)."""
        # Approximate cost per token for Sonnet
        # Input: $3/MTok, Output: $15/MTok - assume 70% input, 30% output
        avg_cost_per_mtok = (3 * 0.7 + 15 * 0.3)
        return (total_tokens / 1_000_000) * avg_cost_per_mtok

    async def cancel_batch(self, job: BatchJob) -> BatchJob:
        """
        Cancel a running batch job.

        Args:
            job: BatchJob to cancel

        Returns:
            Updated BatchJob
        """
        if job.status not in [BatchStatus.PENDING, BatchStatus.PROCESSING]:
            logger.warning(f"[BATCH_PROCESSOR] Cannot cancel batch {job.id} in status {job.status}")
            return job

        anthropic_batch_id = job.metadata.get("anthropic_batch_id")
        if not anthropic_batch_id:
            job.status = BatchStatus.CANCELLED
            return job

        try:
            logger.info(f"[BATCH_PROCESSOR] Cancelling batch {job.id}")
            self.client.messages.batches.cancel(anthropic_batch_id)
            job.status = BatchStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            logger.info(f"[BATCH_PROCESSOR] Batch {job.id} cancelled successfully")
        except Exception as e:
            logger.error(f"[BATCH_PROCESSOR] Failed to cancel batch {job.id}: {e}")
            job.error = str(e)

        await self._notify_progress(job)
        return job

    async def analyze_files(
        self,
        files: list[dict],
        request_type: BatchRequestType = BatchRequestType.FILE_ANALYSIS,
        model: str = "claude-sonnet-4-5-20250929",
        wait_for_completion: bool = True,
    ) -> BatchJob:
        """
        Convenience method to analyze multiple files in batch.

        Args:
            files: List of dicts with 'path' and 'content' keys
            request_type: Type of analysis to perform
            model: Claude model to use
            wait_for_completion: If True, waits for results

        Returns:
            BatchJob with results
        """
        logger.info(f"[BATCH_PROCESSOR] Starting batch analysis of {len(files)} files")

        requests = [
            BatchRequest(
                custom_id=f"file_{i}_{file['path'].replace('/', '_')}",
                file_path=file.get("path", f"file_{i}"),
                content=file.get("content", ""),
                request_type=request_type,
                metadata=file.get("metadata", {}),
            )
            for i, file in enumerate(files)
        ]

        job = await self.create_batch(requests, model=model)

        if wait_for_completion and job.status != BatchStatus.FAILED:
            job = await self.poll_batch(job, wait_for_completion=True)

        return job

    async def bulk_security_scan(
        self,
        files: list[dict],
        wait_for_completion: bool = True,
    ) -> BatchJob:
        """
        Perform security scan on multiple files.

        Args:
            files: List of dicts with 'path' and 'content' keys
            wait_for_completion: If True, waits for results

        Returns:
            BatchJob with security scan results
        """
        logger.info(f"[BATCH_PROCESSOR] Starting bulk security scan of {len(files)} files")
        return await self.analyze_files(
            files,
            request_type=BatchRequestType.SECURITY_SCAN,
            wait_for_completion=wait_for_completion,
        )

    async def bulk_code_review(
        self,
        files: list[dict],
        wait_for_completion: bool = True,
    ) -> BatchJob:
        """
        Perform code review on multiple files.

        Args:
            files: List of dicts with 'path' and 'content' keys
            wait_for_completion: If True, waits for results

        Returns:
            BatchJob with code review results
        """
        logger.info(f"[BATCH_PROCESSOR] Starting bulk code review of {len(files)} files")
        return await self.analyze_files(
            files,
            request_type=BatchRequestType.CODE_REVIEW,
            wait_for_completion=wait_for_completion,
        )

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a batch job by ID."""
        return self._active_jobs.get(job_id)

    def list_jobs(self) -> list[BatchJob]:
        """List all tracked batch jobs."""
        return list(self._active_jobs.values())


# Factory function
def get_batch_processor(
    progress_callback: Optional[Callable[[BatchJob], Any]] = None,
) -> BatchProcessor:
    """Get a batch processor instance."""
    return BatchProcessor(progress_callback=progress_callback)
