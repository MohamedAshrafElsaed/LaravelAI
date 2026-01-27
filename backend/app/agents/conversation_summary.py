"""
Conversation Summary Schema and Management (Enhanced).

Provides rolling context for Nova without exhausting the context window.
Updated after each completed pipeline execution.

NOTE: This integrates with the existing Project model which already contains:
- project.stack (Laravel/PHP versions, packages, database, frontend)
- project.file_stats (file counts by type)
- project.structure (architecture patterns)
- project.ai_context (AI-specific context)

ENHANCEMENTS:
- Group A: Persistence layer with JSON serialization
- Group B: Token-aware management with priority truncation
- Group C: Intelligent summarization of older content
- Group D: Integration helpers for chat flow
- Group E: Working memory pattern with entity extraction
"""
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Token estimation (avg 4 chars per token for English)
CHARS_PER_TOKEN = 4

# Token budgets (configurable)
DEFAULT_TOKEN_BUDGET = 4000
MAX_TOKEN_BUDGET = 8000
MIN_TOKEN_BUDGET = 1000


class ContextPriority(int, Enum):
    """Priority levels for context retention during truncation."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class RecentMessage:
    """A single recent message for context."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None
    has_code_changes: bool = False
    summary: Optional[str] = None  # Summarized version for older messages

    def to_prompt_text(self, use_summary: bool = False) -> str:
        """Format for inclusion in prompt."""
        content = self.summary if (use_summary and self.summary) else self.content
        suffix = " [made code changes]" if self.has_code_changes else ""
        return f"[{self.role.upper()}]: {content}{suffix}"

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "has_code_changes": self.has_code_changes,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecentMessage":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def estimate_tokens(self, use_summary: bool = False) -> int:
        """Estimate token count for this message."""
        text = self.to_prompt_text(use_summary)
        return len(text) // CHARS_PER_TOKEN


@dataclass
class ConversationSummary:
    """
    Structured rolling summary of conversation context.

    Updated after each completed step to maintain continuity
    without sending full chat history.

    NOTE: Project metadata (stack, file_stats, structure) comes from
    the Project model and is passed separately via build_project_context().
    This summary focuses on CONVERSATION state, not project metadata.
    """

    # Project Context (basic info - detailed info comes from Project model)
    project_name: Optional[str] = None
    project_id: Optional[str] = None

    # Decisions Made (what we agreed on)
    decisions: List[str] = field(default_factory=list)

    # Completed Work (what is done)
    completed_tasks: List[str] = field(default_factory=list)

    # Pending Tasks (what remains + next steps)
    pending_tasks: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)

    # Working Memory (Group E) - Current task tracking
    current_task: Optional[str] = None
    current_files: List[str] = field(default_factory=list)
    current_context: Optional[str] = None

    # Constraints / Rules (user-specified or discovered)
    constraints: List[str] = field(default_factory=lambda: [
        "Use focused diffs only - no full rewrites",
        "Ask for missing files - never assume content",
        "Do not invent routes, stores, or APIs",
        "Do not over-engineer solutions",
    ])

    # Known Entities (confirmed files, classes, routes from conversation)
    known_files: List[str] = field(default_factory=list)
    known_classes: List[str] = field(default_factory=list)
    known_routes: List[str] = field(default_factory=list)
    known_methods: List[str] = field(default_factory=list)
    known_tables: List[str] = field(default_factory=list)

    # Recent Messages (Group D) - for immediate context
    recent_messages: List[Dict] = field(default_factory=list)

    # Summarized History (Group C) - compressed older messages
    history_summary: Optional[str] = None
    summarized_turn_count: int = 0

    # Token Management (Group B)
    token_budget: int = DEFAULT_TOKEN_BUDGET
    last_token_count: int = 0

    # Metadata
    last_updated: Optional[str] = None
    update_count: int = 0
    conversation_turn: int = 0

    # =========================================================================
    # GROUP D: Integration Helpers
    # =========================================================================

    def get_recent_messages(self, max_messages: int = 4) -> List[RecentMessage]:
        """Get recent messages as RecentMessage objects."""
        messages = [RecentMessage.from_dict(m) for m in self.recent_messages]
        return messages[-max_messages:]

    def add_message(self, role: str, content: str, has_code_changes: bool = False) -> None:
        """Add a message to recent history."""
        msg = RecentMessage(
            role=role,
            content=content[:2000],  # Truncate long messages
            timestamp=datetime.now(timezone.utc).isoformat(),
            has_code_changes=has_code_changes,
        )
        self.recent_messages.append(msg.to_dict())
        self.conversation_turn += 1

        # Trigger compression if too many messages
        if len(self.recent_messages) > 10:
            self._compress_old_messages()

    def set_current_task(self, task: str, files: List[str] = None, context: str = None) -> None:
        """Set the current working task (Group E: Working Memory)."""
        self.current_task = task
        self.current_files = files or []
        self.current_context = context
        logger.debug(f"[SUMMARY] Set current task: {task[:50]}...")

    def clear_current_task(self) -> None:
        """Clear current task after completion."""
        if self.current_task:
            self.completed_tasks.append(self.current_task)
        self.current_task = None
        self.current_files = []
        self.current_context = None

    # =========================================================================
    # GROUP C: Intelligent Summarization
    # =========================================================================

    def _compress_old_messages(self, keep_recent: int = 4) -> None:
        """Compress older messages into a summary."""
        if len(self.recent_messages) <= keep_recent:
            return

        # Messages to compress
        to_compress = self.recent_messages[:-keep_recent]
        self.recent_messages = self.recent_messages[-keep_recent:]

        # Build summary of compressed messages
        summary_parts = []
        for msg_dict in to_compress:
            msg = RecentMessage.from_dict(msg_dict)
            key_points = self._extract_key_points(msg.content, msg.role)
            if key_points:
                summary_parts.append(f"[{msg.role}] {key_points}")

        if summary_parts:
            new_summary = "; ".join(summary_parts)
            if self.history_summary:
                self.history_summary = f"{self.history_summary} | {new_summary}"
            else:
                self.history_summary = new_summary

            # Truncate if too long
            if len(self.history_summary) > 1500:
                self.history_summary = self.history_summary[-1500:]

        self.summarized_turn_count += len(to_compress)
        logger.debug(f"[SUMMARY] Compressed {len(to_compress)} messages")

    def _extract_key_points(self, content: str, role: str) -> str:
        """Extract key points from a message for summarization."""
        if not content:
            return ""

        # For user messages, extract the main request
        if role == "user":
            first_line = content.split('\n')[0][:150]
            return first_line.strip()

        # For assistant messages, extract decisions/actions
        if role == "assistant":
            actions = []
            patterns = [
                r"(?:I'll|I will|Let me|Going to)\s+(.{20,80}?)(?:\.|$)",
                r"(?:Created|Modified|Updated|Added|Fixed)\s+(.{10,50}?)(?:\.|$)",
                r"(?:Decision|Decided|Chose):\s*(.{20,80}?)(?:\.|$)",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                actions.extend(matches[:2])

            if actions:
                return "; ".join(actions[:3])

            # Fallback: first meaningful line
            for line in content.split('\n'):
                line = line.strip()
                if len(line) > 20 and not line.startswith('#'):
                    return line[:100]

        return content[:80] if len(content) > 80 else content

    # =========================================================================
    # GROUP B: Token-Aware Management
    # =========================================================================

    def estimate_tokens(self) -> int:
        """Estimate total token count of the summary."""
        text = self.to_prompt_text()
        tokens = len(text) // CHARS_PER_TOKEN
        self.last_token_count = tokens
        return tokens

    def fits_budget(self, budget: Optional[int] = None) -> bool:
        """Check if current summary fits within token budget."""
        budget = budget or self.token_budget
        return self.estimate_tokens() <= budget

    def truncate_to_budget(self, budget: Optional[int] = None) -> None:
        """Truncate summary to fit within token budget using priority-based removal."""
        budget = budget or self.token_budget

        while not self.fits_budget(budget):
            removed = self._remove_lowest_priority_item()
            if not removed:
                break

        logger.debug(f"[SUMMARY] Truncated to {self.estimate_tokens()} tokens (budget: {budget})")

    def _remove_lowest_priority_item(self) -> bool:
        """Remove one item of lowest priority. Returns True if something was removed."""
        # Priority order for removal (LOW priority = remove first)
        # 1. Old completed tasks
        if len(self.completed_tasks) > 3:
            self.completed_tasks.pop(0)
            return True

        # 2. History summary (compress further)
        if self.history_summary and len(self.history_summary) > 200:
            self.history_summary = self.history_summary[-200:]
            return True

        # 3. Known entities (keep only most recent)
        for attr in ['known_methods', 'known_tables', 'known_routes', 'known_classes']:
            lst = getattr(self, attr)
            if len(lst) > 5:
                lst.pop(0)
                return True

        # 4. Known files (keep more of these)
        if len(self.known_files) > 10:
            self.known_files.pop(0)
            return True

        # 5. Old decisions
        if len(self.decisions) > 3:
            self.decisions.pop(0)
            return True

        # 6. Pending tasks (risky but necessary)
        if len(self.pending_tasks) > 2:
            self.pending_tasks.pop(0)
            return True

        return False

    # =========================================================================
    # GROUP A: Persistence Layer
    # =========================================================================

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationSummary":
        """Deserialize from storage, ignoring unknown fields."""
        valid_fields = set(cls.__dataclass_fields__.keys())
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """Serialize to JSON string for database storage."""
        return json.dumps(self.to_dict(), indent=None, separators=(',', ':'))

    @classmethod
    def from_json(cls, json_str: str) -> "ConversationSummary":
        """Deserialize from JSON string."""
        if not json_str:
            return cls()
        try:
            return cls.from_dict(json.loads(json_str))
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"[SUMMARY] Failed to parse JSON: {e}")
            return cls()

    # =========================================================================
    # PROMPT GENERATION
    # =========================================================================

    def to_prompt_text(self, include_recent: bool = True) -> str:
        """
        Convert summary to structured text for Nova's prompt.

        NOTE: This only includes CONVERSATION context (decisions, tasks, entities).
        Project metadata (stack, structure, etc.) is provided separately by
        Orchestrator.build_project_context() from the Project model.
        """
        sections = []

        # Project name (if set)
        if self.project_name:
            sections.append(f"<project_name>{self.project_name}</project_name>")

        # Current Task (Working Memory - highest priority)
        if self.current_task:
            current = [f"Task: {self.current_task}"]
            if self.current_files:
                current.append(f"Active files: {', '.join(self.current_files[:5])}")
            if self.current_context:
                current.append(f"Context: {self.current_context[:200]}")
            sections.append(f"<current_work>\n" + "\n".join(current) + "\n</current_work>")

        # Decisions
        if self.decisions:
            sections.append(f"<decisions_made>\n- " + "\n- ".join(self.decisions[-5:]) + "\n</decisions_made>")

        # Completed Work
        if self.completed_tasks:
            sections.append(f"<completed_work>\n- " + "\n- ".join(self.completed_tasks[-5:]) + "\n</completed_work>")

        # Pending Tasks
        if self.pending_tasks or self.next_steps:
            pending = []
            if self.pending_tasks:
                pending.append("Pending: " + "; ".join(self.pending_tasks[-3:]))
            if self.next_steps:
                pending.append("Next: " + "; ".join(self.next_steps[-2:]))
            sections.append(f"<pending_work>\n{chr(10).join(pending)}\n</pending_work>")

        # Constraints (always include)
        if self.constraints:
            sections.append(f"<constraints>\n- " + "\n- ".join(self.constraints) + "\n</constraints>")

        # Known Entities (from conversation, not from scanner)
        entities = []
        if self.known_files:
            entities.append(f"Files: {', '.join(self.known_files[-10:])}")
        if self.known_classes:
            entities.append(f"Classes: {', '.join(self.known_classes[-10:])}")
        if self.known_routes:
            entities.append(f"Routes: {', '.join(self.known_routes[-5:])}")
        if self.known_tables:
            entities.append(f"Tables: {', '.join(self.known_tables[-5:])}")
        if entities:
            sections.append(f"<confirmed_entities>\n{chr(10).join(entities)}\n</confirmed_entities>")

        # History Summary (LOW priority - compressed older context)
        if self.history_summary:
            sections.append(f"<earlier_context>{self.history_summary}</earlier_context>")

        if not sections:
            return "<conversation_context>No prior conversation context.</conversation_context>"

        return "<conversation_context>\n" + "\n\n".join(sections) + "\n</conversation_context>"

    # =========================================================================
    # GROUP E: Entity Extraction from Results
    # =========================================================================

    def extract_entities_from_execution(self, execution_results: List[Any]) -> None:
        """Extract and store entities from execution results."""
        for result in execution_results:
            if not hasattr(result, 'file') or not result.file:
                continue

            # Track modified files
            file_path = result.file
            if file_path not in self.known_files:
                self.known_files.append(file_path)

            # Extract class names from content
            if hasattr(result, 'content') and result.content:
                self._extract_entities_from_code(result.content, file_path)

    def _extract_entities_from_code(self, content: str, file_path: str) -> None:
        """Extract entities (classes, methods, etc.) from code content."""
        # PHP class extraction
        class_matches = re.findall(r'class\s+(\w+)', content)
        for cls in class_matches:
            if cls not in self.known_classes:
                self.known_classes.append(cls)

        # PHP method extraction (public/protected/private function)
        method_matches = re.findall(r'(?:public|protected|private)\s+function\s+(\w+)', content)
        for method in method_matches[:10]:  # Limit to avoid bloat
            qualified = f"{file_path}::{method}"
            if qualified not in self.known_methods:
                self.known_methods.append(qualified)

        # Route extraction
        route_matches = re.findall(r"Route::\w+\(['\"]([^'\"]+)['\"]", content)
        for route in route_matches[:5]:
            if route not in self.known_routes:
                self.known_routes.append(route)

        # Table extraction (migrations)
        table_matches = re.findall(r"Schema::\w+\(['\"](\w+)['\"]", content)
        for table in table_matches:
            if table not in self.known_tables:
                self.known_tables.append(table)

    # =========================================================================
    # UPDATE METHODS
    # =========================================================================

    def update_after_execution(
            self,
            task_completed: str,
            files_modified: List[str],
            new_decisions: Optional[List[str]] = None,
            new_pending: Optional[List[str]] = None,
            new_entities: Optional[dict] = None,
            execution_results: Optional[List[Any]] = None,
    ) -> None:
        """
        Update summary after a pipeline execution completes.

        Args:
            task_completed: Description of what was done
            files_modified: List of files that were changed
            new_decisions: Any new decisions made
            new_pending: New pending tasks identified
            new_entities: New confirmed entities {"files": [], "classes": [], "tables": [], ...}
            execution_results: Execution results for entity extraction
        """
        # Add completed task
        self.completed_tasks.append(task_completed)

        # Track modified files as known
        for f in files_modified:
            if f not in self.known_files:
                self.known_files.append(f)

        # Clear from current files (task done)
        for f in files_modified:
            if f in self.current_files:
                self.current_files.remove(f)

        # Add decisions
        if new_decisions:
            self.decisions.extend(new_decisions)

        # Update pending tasks
        if new_pending is not None:
            self.pending_tasks = new_pending

        # Add new entities (manual)
        if new_entities:
            for cls in new_entities.get("classes", []):
                if cls not in self.known_classes:
                    self.known_classes.append(cls)
            for route in new_entities.get("routes", []):
                if route not in self.known_routes:
                    self.known_routes.append(route)
            for method in new_entities.get("methods", []):
                if method not in self.known_methods:
                    self.known_methods.append(method)
            for table in new_entities.get("tables", []):
                if table not in self.known_tables:
                    self.known_tables.append(table)

        # Extract entities from execution results (Group E)
        if execution_results:
            self.extract_entities_from_execution(execution_results)

        # Clear current task if it matches completed
        if self.current_task and task_completed in self.current_task:
            self.clear_current_task()

        # Update metadata
        self.last_updated = datetime.now(timezone.utc).isoformat()
        self.update_count += 1

        # Trim and fit budget
        self._trim_old_entries()
        self.truncate_to_budget()

    def _trim_old_entries(self, max_items: int = 10) -> None:
        """Keep only recent entries to prevent summary bloat."""
        self.completed_tasks = self.completed_tasks[-max_items:]
        self.decisions = self.decisions[-max_items:]
        self.known_files = self.known_files[-20:]
        self.known_classes = self.known_classes[-15:]
        self.known_routes = self.known_routes[-10:]
        self.known_methods = self.known_methods[-15:]
        self.known_tables = self.known_tables[-10:]

    def add_constraint(self, constraint: str) -> None:
        """Add a user-specified constraint."""
        if constraint not in self.constraints:
            self.constraints.append(constraint)

    def add_known_entity(self, entity_type: str, entity_name: str) -> None:
        """Add a confirmed entity from conversation."""
        if entity_type == "file" and entity_name not in self.known_files:
            self.known_files.append(entity_name)
        elif entity_type == "class" and entity_name not in self.known_classes:
            self.known_classes.append(entity_name)
        elif entity_type == "route" and entity_name not in self.known_routes:
            self.known_routes.append(entity_name)
        elif entity_type == "table" and entity_name not in self.known_tables:
            self.known_tables.append(entity_name)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_recent_messages(messages: List[RecentMessage], max_messages: int = 4) -> str:
    """
    Format recent messages for Nova's prompt.

    Args:
        messages: List of recent messages
        max_messages: Maximum number to include (default 4)

    Returns:
        Formatted string for prompt inclusion
    """
    if not messages:
        return "<recent_messages>No recent messages.</recent_messages>"

    recent = messages[-max_messages:]
    formatted = [msg.to_prompt_text() for msg in recent]

    return "<recent_messages>\n" + "\n".join(formatted) + "\n</recent_messages>"


def create_recent_message_from_history(history_item: dict) -> RecentMessage:
    """Convert a database history item to RecentMessage."""
    return RecentMessage(
        role=history_item.get("role", "user"),
        content=history_item.get("content", "")[:2000],
        has_code_changes=history_item.get("has_code_changes", False),
        timestamp=history_item.get("created_at"),
    )


def build_conversation_context(
        summary: ConversationSummary,
        history: List[dict],
        max_recent: int = 4,
) -> Tuple[ConversationSummary, List[RecentMessage]]:
    """
    Build complete conversation context from summary and history.

    Args:
        summary: Existing conversation summary
        history: Raw message history from database
        max_recent: Maximum recent messages to include

    Returns:
        Tuple of (updated summary, recent messages list)
    """
    # Convert history to RecentMessages
    recent_messages = [
        create_recent_message_from_history(h) for h in history[-max_recent:]
    ]

    # Sync recent messages to summary
    for msg in recent_messages:
        existing = [m.get("content", "")[:50] for m in summary.recent_messages]
        if msg.content[:50] not in existing:
            summary.recent_messages.append(msg.to_dict())

    return summary, recent_messages
