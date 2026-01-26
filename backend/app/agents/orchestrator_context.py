"""
Orchestrator Context Integration Module.

Handles loading, updating, and persisting conversation summaries.
Bridges Database <-> ConversationSummary <-> Agents.
"""
import logging
from typing import Optional, List, Tuple, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc

from app.agents.conversation_summary import (
    ConversationSummary,
    RecentMessage,
    create_recent_message_from_history,
    build_conversation_context,
)
from app.models.models import Conversation, Message

logger = logging.getLogger(__name__)


class ConversationContextManager:
    """Manages conversation context lifecycle."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: dict[str, ConversationSummary] = {}

    async def load_or_create(
        self,
        conversation_id: str,
        project_name: Optional[str] = None,
    ) -> ConversationSummary:
        """Load existing summary or create new one."""
        if conversation_id in self._cache:
            return self._cache[conversation_id]

        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation and hasattr(conversation, 'summary_data') and conversation.summary_data:
            try:
                summary = ConversationSummary.from_json(conversation.summary_data)
                logger.debug(f"[CTX_MGR] Loaded summary for conversation={conversation_id}")
            except Exception as e:
                logger.warning(f"[CTX_MGR] Failed to load summary: {e}")
                summary = ConversationSummary()
        else:
            summary = ConversationSummary()

        if project_name:
            summary.project_name = project_name
        if conversation:
            summary.project_id = conversation.project_id

        self._cache[conversation_id] = summary
        return summary

    async def get_context_for_agents(
        self,
        conversation_id: str,
        history_limit: int = 10,
        recent_limit: int = 4,
    ) -> Tuple[ConversationSummary, List[RecentMessage]]:
        """Get complete context for agent consumption."""
        summary = await self.load_or_create(conversation_id)
        history = await self._get_message_history(conversation_id, history_limit)
        summary, recent_messages = build_conversation_context(
            summary=summary,
            history=history,
            max_recent=recent_limit,
        )
        return summary, recent_messages

    async def _get_message_history(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[dict]:
        """Fetch message history from database."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = result.scalars().all()

        history = []
        for msg in reversed(messages):
            history.append({
                "role": msg.role,
                "content": msg.content,
                "has_code_changes": bool(msg.code_changes),
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })
        return history

    async def update_after_execution(
        self,
        conversation_id: str,
        task_completed: str,
        files_modified: List[str],
        execution_results: Optional[List[Any]] = None,
        new_decisions: Optional[List[str]] = None,
        new_pending: Optional[List[str]] = None,
    ) -> ConversationSummary:
        """Update summary after pipeline execution."""
        summary = await self.load_or_create(conversation_id)

        summary.update_after_execution(
            task_completed=task_completed,
            files_modified=files_modified,
            new_decisions=new_decisions,
            new_pending=new_pending,
            execution_results=execution_results,
        )

        await self.persist(conversation_id, summary)
        return summary

    async def set_current_task(
        self,
        conversation_id: str,
        task: str,
        files: List[str] = None,
        context: str = None,
    ) -> None:
        """Set current working task in summary."""
        summary = await self.load_or_create(conversation_id)
        summary.set_current_task(task, files, context)

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        has_code_changes: bool = False,
    ) -> None:
        """Add a message to the summary's recent history."""
        summary = await self.load_or_create(conversation_id)
        summary.add_message(role, content, has_code_changes)

    async def persist(
        self,
        conversation_id: str,
        summary: Optional[ConversationSummary] = None,
    ) -> None:
        """Persist summary to database."""
        if summary is None:
            summary = self._cache.get(conversation_id)
            if summary is None:
                return

        try:
            summary.truncate_to_budget()
            json_data = summary.to_json()

            stmt = (
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(summary_data=json_data)
            )
            await self.db.execute(stmt)
            await self.db.commit()

            logger.debug(
                f"[CTX_MGR] Persisted summary for conversation={conversation_id} "
                f"({summary.estimate_tokens()} tokens)"
            )
        except Exception as e:
            logger.error(f"[CTX_MGR] Failed to persist summary: {e}")
            await self.db.rollback()

    def clear_cache(self, conversation_id: Optional[str] = None) -> None:
        """Clear cached summaries."""
        if conversation_id:
            self._cache.pop(conversation_id, None)
        else:
            self._cache.clear()


def get_context_manager(db: AsyncSession) -> ConversationContextManager:
    """Factory function to get a context manager instance."""
    return ConversationContextManager(db)