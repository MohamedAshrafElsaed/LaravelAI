"""
Conversation Summary Schema and Management.

Provides rolling context for Nova without exhausting the context window.
Updated after each completed pipeline execution.

NOTE: This integrates with the existing Project model which already contains:
- project.stack (Laravel/PHP versions, packages, database, frontend)
- project.file_stats (file counts by type)
- project.structure (architecture patterns)
- project.ai_context (AI-specific context)
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


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
    decisions: list[str] = field(default_factory=list)

    # Completed Work (what is done)
    completed_tasks: list[str] = field(default_factory=list)

    # Pending Tasks (what remains + next steps)
    pending_tasks: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    # Constraints / Rules (user-specified or discovered)
    constraints: list[str] = field(default_factory=lambda: [
        "Use focused diffs only - no full rewrites",
        "Ask for missing files - never assume content",
        "Do not invent routes, stores, or APIs",
        "Do not over-engineer solutions",
    ])

    # Known Entities (confirmed files, classes, routes from conversation)
    known_files: list[str] = field(default_factory=list)
    known_classes: list[str] = field(default_factory=list)
    known_routes: list[str] = field(default_factory=list)
    known_methods: list[str] = field(default_factory=list)
    known_tables: list[str] = field(default_factory=list)

    # Metadata
    last_updated: Optional[str] = None
    update_count: int = 0

    def to_prompt_text(self) -> str:
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

        if not sections:
            return "<conversation_context>No prior conversation context.</conversation_context>"

        return "<conversation_context>\n" + "\n\n".join(sections) + "\n</conversation_context>"

    def update_after_execution(
            self,
            task_completed: str,
            files_modified: list[str],
            new_decisions: Optional[list[str]] = None,
            new_pending: Optional[list[str]] = None,
            new_entities: Optional[dict] = None,
    ) -> None:
        """
        Update summary after a pipeline execution completes.

        Args:
            task_completed: Description of what was done
            files_modified: List of files that were changed
            new_decisions: Any new decisions made
            new_pending: New pending tasks identified
            new_entities: New confirmed entities {"files": [], "classes": [], "tables": [], ...}
        """
        # Add completed task
        self.completed_tasks.append(task_completed)

        # Track modified files as known
        for f in files_modified:
            if f not in self.known_files:
                self.known_files.append(f)

        # Add decisions
        if new_decisions:
            self.decisions.extend(new_decisions)

        # Update pending tasks
        if new_pending:
            self.pending_tasks = new_pending

        # Add new entities
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

        # Update metadata
        self.last_updated = datetime.now(timezone.utc).isoformat()
        self.update_count += 1

        # Trim old entries to prevent bloat
        self._trim_old_entries()

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

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationSummary":
        """Deserialize from storage, ignoring unknown fields."""
        # Get valid field names from the dataclass
        valid_fields = set(cls.__dataclass_fields__.keys())
        # Filter out any unknown fields
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "ConversationSummary":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class RecentMessage:
    """A single recent message for context."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None

    def to_prompt_text(self) -> str:
        """Format for inclusion in prompt."""
        return f"[{self.role.upper()}]: {self.content}"


def format_recent_messages(messages: list[RecentMessage], max_messages: int = 4) -> str:
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
