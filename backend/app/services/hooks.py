"""
Hooks Service for AI Pipeline Control and Logging.

Provides a hook system for intercepting and controlling AI operations.
Supports blocking dangerous operations, audit logging, cost controls, and custom validation.
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    """Events that can trigger hooks."""
    # Request lifecycle
    REQUEST_START = "request_start"
    REQUEST_END = "request_end"
    REQUEST_ERROR = "request_error"

    # Intent analysis
    INTENT_BEFORE = "intent_before"
    INTENT_AFTER = "intent_after"

    # Planning
    PLAN_BEFORE = "plan_before"
    PLAN_AFTER = "plan_after"

    # Execution
    EXECUTE_BEFORE = "execute_before"
    EXECUTE_AFTER = "execute_after"
    EXECUTE_STEP = "execute_step"

    # Validation
    VALIDATE_BEFORE = "validate_before"
    VALIDATE_AFTER = "validate_after"

    # File operations
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"

    # API calls
    API_CALL_BEFORE = "api_call_before"
    API_CALL_AFTER = "api_call_after"

    # Cost controls
    COST_CHECK = "cost_check"
    BUDGET_EXCEEDED = "budget_exceeded"

    # Security
    SECURITY_CHECK = "security_check"
    DANGEROUS_OPERATION = "dangerous_operation"


class HookDecision(str, Enum):
    """Decisions a hook can return."""
    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"
    MODIFY = "modify"


@dataclass
class HookContext:
    """Context passed to hooks."""
    event: HookEvent
    user_id: str
    project_id: Optional[str] = None
    conversation_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event": self.event.value,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "conversation_id": self.conversation_id,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata,
        }


@dataclass
class HookResult:
    """Result from a hook execution."""
    decision: HookDecision
    reason: Optional[str] = None
    modified_data: Optional[dict] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "modified_data": self.modified_data,
            "metadata": self.metadata,
        }


@dataclass
class AuditLogEntry:
    """Entry in the audit log."""
    timestamp: datetime
    event: HookEvent
    user_id: str
    project_id: Optional[str]
    request_id: Optional[str]
    action: str
    details: dict
    result: Optional[HookResult]
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event": self.event.value,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "request_id": self.request_id,
            "action": self.action,
            "details": self.details,
            "result": self.result.to_dict() if self.result else None,
            "duration_ms": self.duration_ms,
        }


# Type alias for hook handlers
HookHandler = Callable[[HookContext], Awaitable[HookResult]]


class Hook:
    """
    Individual hook definition.
    """

    def __init__(
        self,
        name: str,
        event: HookEvent,
        handler: HookHandler,
        priority: int = 100,
        enabled: bool = True,
    ):
        """
        Initialize a hook.

        Args:
            name: Hook identifier
            event: Event to trigger on
            handler: Async function to execute
            priority: Execution order (lower = earlier)
            enabled: Whether hook is active
        """
        self.name = name
        self.event = event
        self.handler = handler
        self.priority = priority
        self.enabled = enabled
        self.execution_count = 0
        self.total_duration_ms = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "event": self.event.value,
            "priority": self.priority,
            "enabled": self.enabled,
            "execution_count": self.execution_count,
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": self.total_duration_ms // self.execution_count if self.execution_count > 0 else 0,
        }


class HooksManager:
    """
    Manages hooks for the AI pipeline.

    Provides:
    - Hook registration and deregistration
    - Hook execution with priority ordering
    - Audit logging of all operations
    - Built-in security and cost control hooks
    """

    def __init__(
        self,
        enable_audit_log: bool = True,
        max_audit_entries: int = 10000,
    ):
        """
        Initialize the hooks manager.

        Args:
            enable_audit_log: Whether to log all operations
            max_audit_entries: Maximum audit log entries to keep
        """
        self._hooks: dict[HookEvent, list[Hook]] = {event: [] for event in HookEvent}
        self._audit_log: list[AuditLogEntry] = []
        self._enable_audit_log = enable_audit_log
        self._max_audit_entries = max_audit_entries

        # User budget tracking
        self._user_budgets: dict[str, dict] = {}

        logger.info(f"[HOOKS_MANAGER] Initialized with audit_log={'enabled' if enable_audit_log else 'disabled'}")

        # Register built-in hooks
        self._register_builtin_hooks()

    def _register_builtin_hooks(self) -> None:
        """Register built-in security and control hooks."""

        # Dangerous file operation hook
        async def dangerous_file_hook(context: HookContext) -> HookResult:
            """Block dangerous file operations."""
            file_path = context.data.get("file_path", "")

            # Block operations on sensitive files
            dangerous_patterns = [
                ".env",
                "credentials",
                "secrets",
                "private_key",
                ".pem",
                "password",
                "config/app.php",  # Contains app key
                "storage/app/public",  # Public storage
                "bootstrap/cache",
            ]

            for pattern in dangerous_patterns:
                if pattern in file_path.lower():
                    logger.warning(f"[HOOKS] Blocked dangerous file operation: {file_path}")
                    return HookResult(
                        decision=HookDecision.DENY,
                        reason=f"Blocked: Operation on sensitive file pattern '{pattern}'",
                    )

            # Block deletion of critical files
            if context.event == HookEvent.FILE_DELETE:
                critical_files = [
                    "composer.json",
                    "package.json",
                    "artisan",
                    ".gitignore",
                ]
                for critical in critical_files:
                    if file_path.endswith(critical):
                        return HookResult(
                            decision=HookDecision.DENY,
                            reason=f"Blocked: Cannot delete critical file '{critical}'",
                        )

            return HookResult(decision=HookDecision.ALLOW)

        self.register(
            Hook(
                name="dangerous_file_guard",
                event=HookEvent.FILE_WRITE,
                handler=dangerous_file_hook,
                priority=1,  # Run first
            )
        )

        self.register(
            Hook(
                name="dangerous_file_guard",
                event=HookEvent.FILE_DELETE,
                handler=dangerous_file_hook,
                priority=1,
            )
        )

        # Cost control hook
        async def cost_control_hook(context: HookContext) -> HookResult:
            """Check if user is within budget."""
            user_id = context.user_id
            estimated_cost = context.data.get("estimated_cost", 0)

            budget_info = self._user_budgets.get(user_id, {
                "daily_budget": 10.0,  # Default $10/day
                "spent_today": 0.0,
            })

            remaining = budget_info["daily_budget"] - budget_info["spent_today"]

            if estimated_cost > remaining:
                logger.warning(f"[HOOKS] Budget exceeded for user {user_id}")
                return HookResult(
                    decision=HookDecision.DENY,
                    reason=f"Budget limit reached. Remaining: ${remaining:.2f}",
                    metadata={"remaining_budget": remaining},
                )

            if remaining < budget_info["daily_budget"] * 0.1:  # 10% remaining
                return HookResult(
                    decision=HookDecision.WARN,
                    reason=f"Low budget warning. Remaining: ${remaining:.2f}",
                    metadata={"remaining_budget": remaining},
                )

            return HookResult(decision=HookDecision.ALLOW)

        self.register(
            Hook(
                name="cost_control",
                event=HookEvent.COST_CHECK,
                handler=cost_control_hook,
                priority=10,
            )
        )

        # Security check hook
        async def security_check_hook(context: HookContext) -> HookResult:
            """Check for potentially dangerous code patterns."""
            code = context.data.get("code", "")

            dangerous_patterns = [
                ("eval(", "Dynamic code execution via eval()"),
                ("exec(", "Shell command execution via exec()"),
                ("shell_exec(", "Shell command execution via shell_exec()"),
                ("system(", "System command execution"),
                ("passthru(", "Command execution via passthru()"),
                ("unserialize(", "Unsafe deserialization"),
                ("$$", "Variable variables (potential injection)"),
                ("file_put_contents($_", "Writing user input to file"),
                ("include($_", "Dynamic include (LFI risk)"),
                ("require($_", "Dynamic require (LFI risk)"),
            ]

            warnings = []
            for pattern, description in dangerous_patterns:
                if pattern in code:
                    warnings.append(description)

            if warnings:
                logger.warning(f"[HOOKS] Security concerns detected: {warnings}")
                return HookResult(
                    decision=HookDecision.WARN,
                    reason=f"Security concerns: {', '.join(warnings)}",
                    metadata={"warnings": warnings},
                )

            return HookResult(decision=HookDecision.ALLOW)

        self.register(
            Hook(
                name="security_check",
                event=HookEvent.SECURITY_CHECK,
                handler=security_check_hook,
                priority=5,
            )
        )

        logger.info("[HOOKS_MANAGER] Built-in hooks registered")

    def register(self, hook: Hook) -> None:
        """
        Register a hook.

        Args:
            hook: Hook to register
        """
        self._hooks[hook.event].append(hook)
        # Sort by priority (lower first)
        self._hooks[hook.event].sort(key=lambda h: h.priority)
        logger.info(f"[HOOKS_MANAGER] Registered hook '{hook.name}' for event '{hook.event.value}'")

    def unregister(self, name: str, event: Optional[HookEvent] = None) -> bool:
        """
        Unregister a hook by name.

        Args:
            name: Hook name to remove
            event: Specific event (removes from all if not specified)

        Returns:
            True if hook was found and removed
        """
        removed = False
        events = [event] if event else list(HookEvent)

        for evt in events:
            initial_count = len(self._hooks[evt])
            self._hooks[evt] = [h for h in self._hooks[evt] if h.name != name]
            if len(self._hooks[evt]) < initial_count:
                removed = True
                logger.info(f"[HOOKS_MANAGER] Unregistered hook '{name}' from event '{evt.value}'")

        return removed

    def set_hook_enabled(self, name: str, enabled: bool) -> bool:
        """
        Enable or disable a hook.

        Args:
            name: Hook name
            enabled: New enabled state

        Returns:
            True if hook was found
        """
        found = False
        for hooks in self._hooks.values():
            for hook in hooks:
                if hook.name == name:
                    hook.enabled = enabled
                    found = True
                    logger.info(f"[HOOKS_MANAGER] Hook '{name}' {'enabled' if enabled else 'disabled'}")

        return found

    def _log_audit(
        self,
        context: HookContext,
        action: str,
        details: dict,
        result: Optional[HookResult] = None,
        duration_ms: int = 0,
    ) -> None:
        """Add entry to audit log."""
        if not self._enable_audit_log:
            return

        entry = AuditLogEntry(
            timestamp=datetime.utcnow(),
            event=context.event,
            user_id=context.user_id,
            project_id=context.project_id,
            request_id=context.request_id,
            action=action,
            details=details,
            result=result,
            duration_ms=duration_ms,
        )

        self._audit_log.append(entry)

        # Trim if too large
        if len(self._audit_log) > self._max_audit_entries:
            self._audit_log = self._audit_log[-self._max_audit_entries:]

        logger.debug(f"[HOOKS_AUDIT] {action} - {context.event.value} - user={context.user_id}")

    async def execute(
        self,
        event: HookEvent,
        user_id: str,
        project_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> HookResult:
        """
        Execute all hooks for an event.

        Args:
            event: Event type
            user_id: User identifier
            project_id: Optional project ID
            conversation_id: Optional conversation ID
            request_id: Optional request ID
            data: Event-specific data

        Returns:
            Combined HookResult (DENY takes precedence)
        """
        context = HookContext(
            event=event,
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            request_id=request_id,
            data=data or {},
        )

        hooks = self._hooks.get(event, [])
        enabled_hooks = [h for h in hooks if h.enabled]

        if not enabled_hooks:
            return HookResult(decision=HookDecision.ALLOW)

        logger.debug(f"[HOOKS_MANAGER] Executing {len(enabled_hooks)} hooks for event '{event.value}'")

        start_time = time.time()
        final_decision = HookDecision.ALLOW
        reasons = []
        modified_data = None
        all_metadata = {}

        for hook in enabled_hooks:
            hook_start = time.time()

            try:
                result = await hook.handler(context)

                # Update hook stats
                hook.execution_count += 1
                hook_duration = int((time.time() - hook_start) * 1000)
                hook.total_duration_ms += hook_duration

                # Process result
                if result.decision == HookDecision.DENY:
                    final_decision = HookDecision.DENY
                    if result.reason:
                        reasons.append(f"[{hook.name}] {result.reason}")

                    # Log audit entry for denial
                    self._log_audit(
                        context=context,
                        action=f"DENIED by {hook.name}",
                        details={"reason": result.reason},
                        result=result,
                        duration_ms=hook_duration,
                    )

                    # Stop processing on deny
                    break

                elif result.decision == HookDecision.WARN:
                    if final_decision != HookDecision.DENY:
                        final_decision = HookDecision.WARN
                    if result.reason:
                        reasons.append(f"[{hook.name}] {result.reason}")

                elif result.decision == HookDecision.MODIFY:
                    if result.modified_data:
                        modified_data = result.modified_data
                        context.data.update(modified_data)  # Update context for next hook

                if result.metadata:
                    all_metadata.update(result.metadata)

            except Exception as e:
                logger.error(f"[HOOKS_MANAGER] Hook '{hook.name}' error: {e}")
                # Log the error but don't fail
                self._log_audit(
                    context=context,
                    action=f"ERROR in {hook.name}",
                    details={"error": str(e)},
                    duration_ms=int((time.time() - hook_start) * 1000),
                )

        total_duration = int((time.time() - start_time) * 1000)

        # Log overall execution
        self._log_audit(
            context=context,
            action=f"Hooks executed ({final_decision.value})",
            details={"hooks_run": len(enabled_hooks), "reasons": reasons},
            duration_ms=total_duration,
        )

        return HookResult(
            decision=final_decision,
            reason="; ".join(reasons) if reasons else None,
            modified_data=modified_data,
            metadata=all_metadata,
        )

    def set_user_budget(
        self,
        user_id: str,
        daily_budget: float,
        spent_today: float = 0.0,
    ) -> None:
        """
        Set budget for a user.

        Args:
            user_id: User identifier
            daily_budget: Daily budget limit
            spent_today: Amount already spent today
        """
        self._user_budgets[user_id] = {
            "daily_budget": daily_budget,
            "spent_today": spent_today,
        }
        logger.info(f"[HOOKS_MANAGER] Set budget for user {user_id}: ${daily_budget:.2f}/day")

    def record_user_spending(self, user_id: str, amount: float) -> None:
        """
        Record spending for a user.

        Args:
            user_id: User identifier
            amount: Amount spent
        """
        if user_id not in self._user_budgets:
            self._user_budgets[user_id] = {"daily_budget": 10.0, "spent_today": 0.0}

        self._user_budgets[user_id]["spent_today"] += amount
        logger.debug(f"[HOOKS_MANAGER] Recorded ${amount:.4f} for user {user_id}")

    def get_user_budget_status(self, user_id: str) -> dict:
        """Get budget status for a user."""
        budget = self._user_budgets.get(user_id, {"daily_budget": 10.0, "spent_today": 0.0})
        return {
            "user_id": user_id,
            "daily_budget": budget["daily_budget"],
            "spent_today": budget["spent_today"],
            "remaining": budget["daily_budget"] - budget["spent_today"],
            "percentage_used": (budget["spent_today"] / budget["daily_budget"]) * 100 if budget["daily_budget"] > 0 else 0,
        }

    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        event: Optional[HookEvent] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get audit log entries.

        Args:
            user_id: Filter by user
            event: Filter by event
            limit: Maximum entries to return

        Returns:
            List of audit log entries
        """
        entries = self._audit_log

        if user_id:
            entries = [e for e in entries if e.user_id == user_id]

        if event:
            entries = [e for e in entries if e.event == event]

        # Return most recent entries
        return [e.to_dict() for e in entries[-limit:]]

    def get_hook_stats(self) -> dict:
        """Get statistics for all hooks."""
        stats = {}
        for event, hooks in self._hooks.items():
            stats[event.value] = [h.to_dict() for h in hooks]
        return stats

    def list_hooks(self, event: Optional[HookEvent] = None) -> list[dict]:
        """List registered hooks."""
        if event:
            return [h.to_dict() for h in self._hooks[event]]

        all_hooks = []
        for hooks in self._hooks.values():
            all_hooks.extend([h.to_dict() for h in hooks])
        return all_hooks


# Decorator for adding hooks
def with_hooks(
    before_event: Optional[HookEvent] = None,
    after_event: Optional[HookEvent] = None,
):
    """
    Decorator to add hook execution to a function.

    Args:
        before_event: Event to fire before function
        after_event: Event to fire after function

    Usage:
        @with_hooks(before_event=HookEvent.EXECUTE_BEFORE, after_event=HookEvent.EXECUTE_AFTER)
        async def execute_code(self, code: str) -> str:
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            hooks_manager = getattr(self, '_hooks_manager', None)
            user_id = kwargs.get('user_id') or getattr(self, 'user_id', 'unknown')
            project_id = kwargs.get('project_id') or getattr(self, 'project_id', None)

            # Execute before hook
            if before_event and hooks_manager:
                result = await hooks_manager.execute(
                    event=before_event,
                    user_id=user_id,
                    project_id=project_id,
                    data=kwargs,
                )
                if result.decision == HookDecision.DENY:
                    raise PermissionError(result.reason or "Operation blocked by hook")
                if result.modified_data:
                    kwargs.update(result.modified_data)

            # Execute function
            result = await func(self, *args, **kwargs)

            # Execute after hook
            if after_event and hooks_manager:
                await hooks_manager.execute(
                    event=after_event,
                    user_id=user_id,
                    project_id=project_id,
                    data={"result": result, **kwargs},
                )

            return result

        return wrapper
    return decorator


# Global instance
_hooks_manager: Optional[HooksManager] = None


def get_hooks_manager() -> HooksManager:
    """Get the global hooks manager instance."""
    global _hooks_manager
    if _hooks_manager is None:
        _hooks_manager = HooksManager()
    return _hooks_manager
