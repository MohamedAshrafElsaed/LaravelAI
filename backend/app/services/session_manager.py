"""
Session Management Service for Conversation Continuity.

Provides session persistence, resumption, and forking capabilities
for maintaining conversation state across server restarts.
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.core.config import settings

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """States a session can be in."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class SessionMessage:
    """A message in the session history."""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow(),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SessionContext:
    """Context preserved across session interactions."""
    project_context: Optional[str] = None
    code_context: Optional[str] = None
    intent_history: list[dict] = field(default_factory=list)
    plan_history: list[dict] = field(default_factory=list)
    execution_history: list[dict] = field(default_factory=list)
    custom_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project_context": self.project_context,
            "code_context": self.code_context,
            "intent_history": self.intent_history,
            "plan_history": self.plan_history,
            "execution_history": self.execution_history,
            "custom_data": self.custom_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionContext":
        return cls(
            project_context=data.get("project_context"),
            code_context=data.get("code_context"),
            intent_history=data.get("intent_history", []),
            plan_history=data.get("plan_history", []),
            execution_history=data.get("execution_history", []),
            custom_data=data.get("custom_data", {}),
        )


@dataclass
class Session:
    """Represents a conversation session."""
    id: str
    user_id: str
    project_id: str
    conversation_id: Optional[str] = None
    state: SessionState = SessionState.ACTIVE
    messages: list[SessionMessage] = field(default_factory=list)
    context: SessionContext = field(default_factory=SessionContext)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    parent_session_id: Optional[str] = None  # For forked sessions
    total_tokens_used: int = 0
    total_cost: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.expires_at is None:
            # Default 24-hour expiration
            self.expires_at = datetime.utcnow() + timedelta(hours=24)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "conversation_id": self.conversation_id,
            "state": self.state.value,
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "parent_session_id": self.parent_session_id,
            "total_tokens_used": self.total_tokens_used,
            "total_cost": self.total_cost,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        messages = [SessionMessage.from_dict(m) for m in data.get("messages", [])]
        context = SessionContext.from_dict(data.get("context", {}))

        return cls(
            id=data["id"],
            user_id=data["user_id"],
            project_id=data["project_id"],
            conversation_id=data.get("conversation_id"),
            state=SessionState(data.get("state", "active")),
            messages=messages,
            context=context,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            parent_session_id=data.get("parent_session_id"),
            total_tokens_used=data.get("total_tokens_used", 0),
            total_cost=data.get("total_cost", 0.0),
            metadata=data.get("metadata", {}),
        )


class SessionStore:
    """
    Abstract base for session storage backends.
    """

    async def save(self, session: Session) -> None:
        raise NotImplementedError

    async def load(self, session_id: str) -> Optional[Session]:
        raise NotImplementedError

    async def delete(self, session_id: str) -> bool:
        raise NotImplementedError

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        state: Optional[SessionState] = None,
        limit: int = 50,
    ) -> list[Session]:
        raise NotImplementedError


class FileSessionStore(SessionStore):
    """
    File-based session storage.

    Stores sessions as JSON files on disk.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize the file session store.

        Args:
            storage_dir: Directory to store session files
        """
        self.storage_dir = Path(storage_dir or "/tmp/sessions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[SESSION_STORE] File store initialized at {self.storage_dir}")

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.storage_dir / f"{session_id}.json"

    async def save(self, session: Session) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.id)

        try:
            session_data = session.to_dict()
            with open(path, "w") as f:
                json.dump(session_data, f, indent=2)
            logger.debug(f"[SESSION_STORE] Saved session {session.id}")
        except Exception as e:
            logger.error(f"[SESSION_STORE] Failed to save session {session.id}: {e}")
            raise

    async def load(self, session_id: str) -> Optional[Session]:
        """Load a session from disk."""
        path = self._get_session_path(session_id)

        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            session = Session.from_dict(data)
            logger.debug(f"[SESSION_STORE] Loaded session {session_id}")
            return session
        except Exception as e:
            logger.error(f"[SESSION_STORE] Failed to load session {session_id}: {e}")
            return None

    async def delete(self, session_id: str) -> bool:
        """Delete a session file."""
        path = self._get_session_path(session_id)

        if not path.exists():
            return False

        try:
            path.unlink()
            logger.debug(f"[SESSION_STORE] Deleted session {session_id}")
            return True
        except Exception as e:
            logger.error(f"[SESSION_STORE] Failed to delete session {session_id}: {e}")
            return False

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        state: Optional[SessionState] = None,
        limit: int = 50,
    ) -> list[Session]:
        """List sessions matching filters."""
        sessions = []

        for path in self.storage_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)

                # Apply filters
                if user_id and data.get("user_id") != user_id:
                    continue
                if project_id and data.get("project_id") != project_id:
                    continue
                if state and data.get("state") != state.value:
                    continue

                sessions.append(Session.from_dict(data))

                if len(sessions) >= limit:
                    break

            except Exception as e:
                logger.warning(f"[SESSION_STORE] Error reading session file {path}: {e}")

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]


class MemorySessionStore(SessionStore):
    """
    In-memory session storage.

    Fast but not persistent across restarts.
    """

    def __init__(self):
        """Initialize the memory session store."""
        self._sessions: dict[str, Session] = {}
        logger.info("[SESSION_STORE] Memory store initialized")

    async def save(self, session: Session) -> None:
        """Save a session to memory."""
        self._sessions[session.id] = session
        logger.debug(f"[SESSION_STORE] Saved session {session.id} to memory")

    async def load(self, session_id: str) -> Optional[Session]:
        """Load a session from memory."""
        return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> bool:
        """Delete a session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        state: Optional[SessionState] = None,
        limit: int = 50,
    ) -> list[Session]:
        """List sessions matching filters."""
        sessions = list(self._sessions.values())

        # Apply filters
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        if project_id:
            sessions = [s for s in sessions if s.project_id == project_id]
        if state:
            sessions = [s for s in sessions if s.state == state]

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]


class SessionManager:
    """
    Manages conversation sessions.

    Provides:
    - Session creation and persistence
    - Session resumption after interruption
    - Session forking for exploring alternatives
    - Context management across interactions
    """

    def __init__(
        self,
        store: Optional[SessionStore] = None,
        default_ttl_hours: int = 24,
        max_messages: int = 100,
    ):
        """
        Initialize the session manager.

        Args:
            store: Session storage backend
            default_ttl_hours: Default session TTL in hours
            max_messages: Maximum messages to keep per session
        """
        self.store = store or FileSessionStore()
        self.default_ttl_hours = default_ttl_hours
        self.max_messages = max_messages

        logger.info(f"[SESSION_MANAGER] Initialized with TTL={default_ttl_hours}h, max_messages={max_messages}")

    async def create_session(
        self,
        user_id: str,
        project_id: str,
        conversation_id: Optional[str] = None,
        initial_context: Optional[SessionContext] = None,
        metadata: Optional[dict] = None,
    ) -> Session:
        """
        Create a new session.

        Args:
            user_id: User identifier
            project_id: Project identifier
            conversation_id: Optional linked conversation ID
            initial_context: Optional initial context
            metadata: Optional metadata

        Returns:
            New Session object
        """
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            context=initial_context or SessionContext(),
            expires_at=datetime.utcnow() + timedelta(hours=self.default_ttl_hours),
            metadata=metadata or {},
        )

        await self.store.save(session)
        logger.info(f"[SESSION_MANAGER] Created session {session.id} for user {user_id}")

        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found and not expired, None otherwise
        """
        session = await self.store.load(session_id)

        if session is None:
            return None

        # Check expiration
        if session.is_expired:
            session.state = SessionState.EXPIRED
            await self.store.save(session)
            logger.info(f"[SESSION_MANAGER] Session {session_id} has expired")
            return None

        return session

    async def resume_session(self, session_id: str) -> Optional[Session]:
        """
        Resume a paused or active session.

        Args:
            session_id: Session to resume

        Returns:
            Resumed session or None
        """
        session = await self.get_session(session_id)

        if session is None:
            return None

        if session.state in [SessionState.COMPLETED, SessionState.ERROR]:
            logger.warning(f"[SESSION_MANAGER] Cannot resume session {session_id} in state {session.state}")
            return None

        # Reactivate session
        session.state = SessionState.ACTIVE
        session.updated_at = datetime.utcnow()

        # Extend expiration
        session.expires_at = datetime.utcnow() + timedelta(hours=self.default_ttl_hours)

        await self.store.save(session)
        logger.info(f"[SESSION_MANAGER] Resumed session {session_id}")

        return session

    async def fork_session(
        self,
        session_id: str,
        fork_point: Optional[int] = None,
    ) -> Optional[Session]:
        """
        Fork a session to explore alternative approaches.

        Args:
            session_id: Session to fork
            fork_point: Message index to fork from (defaults to current state)

        Returns:
            New forked session
        """
        parent = await self.get_session(session_id)

        if parent is None:
            return None

        # Determine fork point
        if fork_point is None:
            fork_point = len(parent.messages)
        else:
            fork_point = min(fork_point, len(parent.messages))

        # Create forked session
        forked = Session(
            id=str(uuid.uuid4()),
            user_id=parent.user_id,
            project_id=parent.project_id,
            conversation_id=parent.conversation_id,
            messages=parent.messages[:fork_point].copy(),
            context=SessionContext.from_dict(parent.context.to_dict()),  # Deep copy
            parent_session_id=parent.id,
            total_tokens_used=parent.total_tokens_used,
            total_cost=parent.total_cost,
            metadata={
                "forked_from": parent.id,
                "fork_point": fork_point,
                "forked_at": datetime.utcnow().isoformat(),
            },
        )

        await self.store.save(forked)
        logger.info(f"[SESSION_MANAGER] Forked session {session_id} at message {fork_point} -> {forked.id}")

        return forked

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Add a message to a session.

        Args:
            session_id: Session to update
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional message metadata

        Returns:
            True if successful
        """
        session = await self.get_session(session_id)

        if session is None:
            return False

        if session.state != SessionState.ACTIVE:
            logger.warning(f"[SESSION_MANAGER] Cannot add message to inactive session {session_id}")
            return False

        message = SessionMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        session.messages.append(message)

        # Trim old messages if needed
        if len(session.messages) > self.max_messages:
            # Keep system messages and recent messages
            system_messages = [m for m in session.messages if m.role == "system"]
            other_messages = [m for m in session.messages if m.role != "system"]
            keep_count = self.max_messages - len(system_messages)
            session.messages = system_messages + other_messages[-keep_count:]

        session.updated_at = datetime.utcnow()
        await self.store.save(session)

        logger.debug(f"[SESSION_MANAGER] Added {role} message to session {session_id}")
        return True

    async def update_context(
        self,
        session_id: str,
        project_context: Optional[str] = None,
        code_context: Optional[str] = None,
        intent: Optional[dict] = None,
        plan: Optional[dict] = None,
        execution: Optional[dict] = None,
        custom_data: Optional[dict] = None,
    ) -> bool:
        """
        Update session context.

        Args:
            session_id: Session to update
            project_context: New project context
            code_context: New code context
            intent: Intent analysis to add to history
            plan: Plan to add to history
            execution: Execution result to add to history
            custom_data: Custom data to merge

        Returns:
            True if successful
        """
        session = await self.get_session(session_id)

        if session is None:
            return False

        if project_context is not None:
            session.context.project_context = project_context

        if code_context is not None:
            session.context.code_context = code_context

        if intent is not None:
            session.context.intent_history.append({
                **intent,
                "timestamp": datetime.utcnow().isoformat(),
            })

        if plan is not None:
            session.context.plan_history.append({
                **plan,
                "timestamp": datetime.utcnow().isoformat(),
            })

        if execution is not None:
            session.context.execution_history.append({
                **execution,
                "timestamp": datetime.utcnow().isoformat(),
            })

        if custom_data is not None:
            session.context.custom_data.update(custom_data)

        session.updated_at = datetime.utcnow()
        await self.store.save(session)

        logger.debug(f"[SESSION_MANAGER] Updated context for session {session_id}")
        return True

    async def record_usage(
        self,
        session_id: str,
        tokens: int,
        cost: float,
    ) -> bool:
        """
        Record token usage for a session.

        Args:
            session_id: Session to update
            tokens: Tokens used
            cost: Cost incurred

        Returns:
            True if successful
        """
        session = await self.get_session(session_id)

        if session is None:
            return False

        session.total_tokens_used += tokens
        session.total_cost += cost
        session.updated_at = datetime.utcnow()

        await self.store.save(session)
        return True

    async def pause_session(self, session_id: str) -> bool:
        """
        Pause a session (can be resumed later).

        Args:
            session_id: Session to pause

        Returns:
            True if successful
        """
        session = await self.get_session(session_id)

        if session is None or session.state != SessionState.ACTIVE:
            return False

        session.state = SessionState.PAUSED
        session.updated_at = datetime.utcnow()

        await self.store.save(session)
        logger.info(f"[SESSION_MANAGER] Paused session {session_id}")

        return True

    async def complete_session(self, session_id: str) -> bool:
        """
        Mark a session as completed.

        Args:
            session_id: Session to complete

        Returns:
            True if successful
        """
        session = await self.get_session(session_id)

        if session is None:
            return False

        session.state = SessionState.COMPLETED
        session.updated_at = datetime.utcnow()

        await self.store.save(session)
        logger.info(f"[SESSION_MANAGER] Completed session {session_id}")

        return True

    async def list_user_sessions(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        active_only: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        """
        List sessions for a user.

        Args:
            user_id: User identifier
            project_id: Optional project filter
            active_only: Only return active/paused sessions
            limit: Maximum results

        Returns:
            List of session summaries
        """
        state = SessionState.ACTIVE if active_only else None
        sessions = await self.store.list_sessions(
            user_id=user_id,
            project_id=project_id,
            state=state,
            limit=limit,
        )

        return [
            {
                "id": s.id,
                "project_id": s.project_id,
                "state": s.state.value,
                "message_count": s.message_count,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "total_tokens_used": s.total_tokens_used,
                "total_cost": s.total_cost,
                "is_forked": s.parent_session_id is not None,
            }
            for s in sessions
        ]

    async def get_conversation_messages(
        self,
        session_id: str,
        format_for_api: bool = False,
    ) -> list[dict]:
        """
        Get messages from a session formatted for the Claude API.

        Args:
            session_id: Session to get messages from
            format_for_api: If True, return in API format

        Returns:
            List of messages
        """
        session = await self.get_session(session_id)

        if session is None:
            return []

        if format_for_api:
            # Format for Claude API (exclude system messages, combine consecutive same-role messages)
            api_messages = []
            for msg in session.messages:
                if msg.role == "system":
                    continue

                if api_messages and api_messages[-1]["role"] == msg.role:
                    api_messages[-1]["content"] += "\n\n" + msg.content
                else:
                    api_messages.append({
                        "role": msg.role,
                        "content": msg.content,
                    })

            return api_messages

        return [m.to_dict() for m in session.messages]

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session to delete

        Returns:
            True if successful
        """
        result = await self.store.delete(session_id)
        if result:
            logger.info(f"[SESSION_MANAGER] Deleted session {session_id}")
        return result

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        sessions = await self.store.list_sessions(limit=1000)
        cleaned = 0

        for session in sessions:
            if session.is_expired:
                await self.store.delete(session.id)
                cleaned += 1

        if cleaned > 0:
            logger.info(f"[SESSION_MANAGER] Cleaned up {cleaned} expired sessions")

        return cleaned


# Factory function
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
