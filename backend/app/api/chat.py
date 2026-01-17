"""
AI chat routes with Server-Sent Events (SSE) streaming.

Provides endpoints for AI-powered code assistance with real-time updates.
"""
import json
import logging
import asyncio
from typing import List, Optional, AsyncGenerator
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.prompts import CHAT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT_SIMPLE
from app.models.models import Project, User, ProjectStatus, Conversation, Message
from app.agents.orchestrator import Orchestrator, ProcessEvent, ProcessPhase
from app.services.claude import get_claude_service, create_tracked_claude_service, ClaudeModel
from app.services.usage_tracker import UsageTracker
from app.services.conversation_logger import (
    get_conversation_logger,
    finalize_conversation_logger,
    ConversationLogger,
)
from app.services.ai_operations_logger import get_operations_logger, OperationType

logger = logging.getLogger(__name__)

# Get operations logger for tracking all AI operations
_ops_logger = get_operations_logger()

router = APIRouter()


# ============== Request/Response Models ==============

class ChatMessageResponse(BaseModel):
    """A single chat message."""
    id: str
    role: str  # user, assistant, system
    content: str
    code_changes: Optional[dict] = None
    processing_data: Optional[dict] = None  # Full processing history (intent, plan, steps, etc.)
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation summary."""
    id: str
    project_id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message: Optional[str] = None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response for non-streaming chat."""
    conversation_id: str
    message: ChatMessageResponse
    code_changes: Optional[dict] = None


class SSEEvent(BaseModel):
    """Server-Sent Event structure."""
    event: str
    data: dict

    def to_sse(self) -> str:
        """Format as SSE string."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


# ============== SSE Event Types ==============

class EventType:
    """SSE event type constants."""
    CONNECTED = "connected"
    INTENT_ANALYZED = "intent_analyzed"
    CONTEXT_RETRIEVED = "context_retrieved"
    PLANNING_STARTED = "planning_started"
    PLAN_CREATED = "plan_created"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    VALIDATION_RESULT = "validation_result"
    ANSWER_CHUNK = "answer_chunk"  # For streaming text responses
    COMPLETE = "complete"
    ERROR = "error"


# ============== Helper Functions ==============

def create_sse_event(event_type: str, data: dict) -> str:
    """Create an SSE formatted event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def verify_project_access(
    project_id: str,
    user: User,
    db: AsyncSession,
) -> Project:
    """Verify user has access to project and it's ready."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status != ProjectStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project is not ready. Current status: {project.status}",
        )

    return project


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: str,
    project_id: str,
    conversation_id: Optional[str] = None,
) -> Conversation:
    """Get existing conversation or create new one."""
    if conversation_id:
        # Try to get existing conversation
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.project_id == project_id,
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if conversation:
            return conversation

    # Create new conversation
    conversation = Conversation(
        id=conversation_id or str(uuid4()),
        user_id=user_id,
        project_id=project_id,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation_history(
    db: AsyncSession,
    conversation_id: str,
    limit: int = 10,
) -> list[dict]:
    """
    Fetch recent conversation history for context.

    Args:
        db: Database session
        conversation_id: The conversation ID
        limit: Maximum number of messages to fetch (default 10)

    Returns:
        List of message dicts with role and content
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    # Reverse to get chronological order and format for Claude
    history = []
    for msg in reversed(messages):
        history.append({
            "role": msg.role,
            "content": msg.content,
            # Include summary of code changes if present
            "has_code_changes": bool(msg.code_changes),
        })

    return history


def format_conversation_history(history: list[dict], max_chars: int = 8000) -> str:
    """
    Format conversation history for inclusion in prompts.

    Args:
        history: List of message dicts
        max_chars: Maximum characters to include

    Returns:
        Formatted conversation history string
    """
    if not history:
        return ""

    parts = ["<previous_conversation>"]
    total_chars = 0

    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]

        # Truncate long messages
        if len(content) > 1000:
            content = content[:1000] + "... [truncated]"

        # Check if we'd exceed the limit
        entry = f"\n**{role}:** {content}"
        if msg.get("has_code_changes"):
            entry += " [made code changes]"

        if total_chars + len(entry) > max_chars:
            parts.append("\n... [earlier messages omitted for brevity]")
            break

        parts.append(entry)
        total_chars += len(entry)

    parts.append("\n</previous_conversation>")
    return "\n".join(parts)


async def save_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    code_changes: Optional[dict] = None,
    tokens_used: Optional[int] = None,
    processing_data: Optional[dict] = None,
) -> Message:
    """Save a message to the database."""
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        code_changes=code_changes,
        tokens_used=tokens_used,
        processing_data=processing_data,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Update conversation title if first user message
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if conversation and not conversation.title and role == "user":
        # Use first 50 chars of first user message as title
        conversation.title = content[:50] + ("..." if len(content) > 50 else "")
        await db.commit()

    return message


# ============== Streaming Generator ==============

async def stream_chat_response(
    project_id: str,
    message: str,
    conversation_id: str,
    user_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for chat response.

    Yields SSE events as the orchestrator processes the request.
    """
    logger.info(f"[CHAT] Starting stream for project={project_id}, conversation={conversation_id}")

    # Start AI operations session for logging
    ops_session_id = _ops_logger.start_chat_session(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
    )

    # Get or create conversation
    conversation = await get_or_create_conversation(db, user_id, project_id, conversation_id)

    # Initialize conversation logger
    conv_logger = get_conversation_logger(
        conversation_id=conversation.id,
        project_id=project_id,
        user_id=user_id,
    )

    # Fetch conversation history BEFORE saving current message
    history = await get_conversation_history(db, conversation.id, limit=10)
    conversation_context = format_conversation_history(history)

    # Count messages for logging
    message_count = len(history) + 1

    # Log user message
    conv_logger.log_user_message(
        message=message,
        message_number=message_count,
        conversation_context=conversation_context if conversation_context else None,
    )

    # Now save the user message
    await save_message(db, conversation.id, "user", message)

    # Build message with conversation context
    if conversation_context:
        message_with_context = f"""{conversation_context}

<current_request>
{message}
</current_request>

IMPORTANT: Consider the conversation history above when processing this request. The user may be referring to previous messages, code changes, or context from earlier in the conversation."""
        logger.info(f"[CHAT] Including {len(history)} previous messages in context")
    else:
        message_with_context = message

    # Track events for the orchestrator callback
    event_queue: asyncio.Queue = asyncio.Queue()

    async def event_callback(event: ProcessEvent) -> None:
        """Callback to receive orchestrator events."""
        await event_queue.put(event)

    # Send connected event
    yield create_sse_event(EventType.CONNECTED, {
        "conversation_id": conversation.id,
        "message": "Connected to chat stream",
    })

    try:
        # Create tracked Claude service for this request
        tracker = UsageTracker(db)
        claude_service = create_tracked_claude_service(
            tracker=tracker,
            user_id=user_id,
            project_id=project_id,
        )

        # Create orchestrator with event callback, tracked Claude service, and conversation logger
        orchestrator = Orchestrator(
            db=db,
            event_callback=event_callback,
            claude_service=claude_service,
            conversation_logger=conv_logger,
        )

        # Start processing in background with conversation context
        process_task = asyncio.create_task(
            orchestrator.process_request(project_id, message_with_context)
        )

        # Stream events as they come
        while not process_task.done():
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(event_queue.get(), timeout=0.5)

                # Map orchestrator phases to SSE events
                sse_event = map_phase_to_sse_event(event)
                if sse_event:
                    yield sse_event

            except asyncio.TimeoutError:
                # No event yet, continue waiting
                continue

        # Get final result
        result = await process_task

        # Drain any remaining events
        while not event_queue.empty():
            event = await event_queue.get()
            sse_event = map_phase_to_sse_event(event)
            if sse_event:
                yield sse_event

        # Build assistant response content
        if result.success:
            # Check if this was classified as a question (no plan/execution)
            if not result.plan and not result.execution_results:
                # This was classified as a question - generate an answer
                logger.info("[CHAT] Intent classified as question, generating answer...")

                # Get intent and context from orchestrator result
                intent = result.intent
                context = await orchestrator.context_retriever.retrieve(project_id, intent) if intent else None
                project_context = orchestrator.build_project_context(await orchestrator._get_project(project_id))

                # Build prompt for question answering
                user_prompt = f"""<question>
{message}
</question>

<project_info>
{project_context}
</project_info>

<codebase_context>
{context.to_prompt_string() if context else "No context available"}
</codebase_context>

Answer the question based on this project's specific technology stack, conventions, and patterns. Reference actual code and files when relevant."""

                # Stream response from Claude with caching
                messages_for_claude = [{"role": "user", "content": user_prompt}]
                full_response = ""

                async for chunk in claude_service.stream_cached(
                    model=ClaudeModel.SONNET,
                    messages=messages_for_claude,
                    system=CHAT_SYSTEM_PROMPT,
                    temperature=0.7,
                    request_type="chat",
                ):
                    full_response += chunk
                    yield create_sse_event(EventType.ANSWER_CHUNK, {
                        "chunk": chunk,
                    })

                response_content = full_response
            else:
                # Normal task completion with plan and execution
                summary_parts = []
                if result.plan:
                    summary_parts.append(f"**Plan:** {result.plan.summary}")
                if result.execution_results:
                    summary_parts.append(f"\n**Files changed:** {len(result.execution_results)}")
                    for r in result.execution_results:
                        summary_parts.append(f"- [{r.action}] {r.file}")
                if result.validation:
                    summary_parts.append(f"\n**Validation score:** {result.validation.score}/100")
                response_content = "\n".join(summary_parts) if summary_parts else "Task completed successfully."
        else:
            # Build meaningful error message
            error_msg = result.error
            if not error_msg and result.validation and result.validation.errors:
                error_msg = "; ".join([e.message for e in result.validation.errors[:3]])
            if not error_msg:
                error_msg = "Unknown error occurred during processing"
            response_content = f"Failed to process request: {error_msg}"

        # Save assistant message with full processing data
        code_changes = {
            "results": [r.to_dict() for r in result.execution_results],
            "validation": result.validation.to_dict() if result.validation else None,
        } if result.execution_results else None

        # Build processing_data to store all steps for history replay
        processing_data = {
            "intent": result.intent.to_dict() if result.intent else None,
            "plan": result.plan.to_dict() if result.plan else None,
            "execution_results": [r.to_dict() for r in result.execution_results],
            "validation": result.validation.to_dict() if result.validation else None,
            "events": [e.to_dict() for e in result.events],
            "success": result.success,
            "error": result.error,
        }

        await save_message(db, conversation.id, "assistant", response_content, code_changes, processing_data=processing_data)

        # Log the final response
        conv_logger.log_response(
            response_content=response_content,
            response_type="assistant",
            is_streaming=False,
        )

        # Finalize the conversation log
        log_paths = finalize_conversation_logger(conversation.id)
        logger.info(f"[CHAT] Conversation log finalized: {log_paths}")

        # End AI operations session and get summary
        ops_summary = _ops_logger.end_chat_session(ops_session_id)

        # Send final complete event
        yield create_sse_event(EventType.COMPLETE, {
            "success": result.success,
            "answer": response_content,
            "plan": result.plan.to_dict() if result.plan else None,
            "execution_results": [r.to_dict() for r in result.execution_results],
            "validation": result.validation.to_dict() if result.validation else None,
            "error": result.error,
            "log_paths": log_paths,  # Include log file paths in response
            "ops_summary": ops_summary,  # Include AI operations summary
        })

    except Exception as e:
        logger.exception(f"[CHAT] Stream error: {e}")
        # Log error to operations logger
        _ops_logger.log(
            operation_type=OperationType.ERROR,
            message=f"Stream error: {str(e)}",
            user_id=user_id,
            project_id=project_id,
            success=False,
            error=str(e),
        )
        # End AI operations session
        _ops_logger.end_chat_session(ops_session_id)
        # Log error
        conv_logger.log_error(
            error_message=str(e),
            error_type="stream_error",
        )
        # Finalize the conversation log even on error
        finalize_conversation_logger(conversation.id)
        # Save error as assistant message
        await save_message(db, conversation.id, "assistant", f"Error: {str(e)}")
        yield create_sse_event(EventType.ERROR, {
            "message": str(e),
        })


def map_phase_to_sse_event(event: ProcessEvent) -> Optional[str]:
    """Map orchestrator phase to SSE event."""
    phase = event.phase
    data = {
        "message": event.message,
        "progress": event.progress,
        "timestamp": event.timestamp.isoformat(),
    }

    if event.data:
        data.update(event.data)

    if phase == ProcessPhase.ANALYZING:
        if "intent" in (event.data or {}):
            return create_sse_event(EventType.INTENT_ANALYZED, data)
        return None  # Skip intermediate analyzing events

    elif phase == ProcessPhase.RETRIEVING:
        if "chunks_count" in (event.data or {}):
            return create_sse_event(EventType.CONTEXT_RETRIEVED, data)
        return None

    elif phase == ProcessPhase.PLANNING:
        if "plan" in (event.data or {}):
            return create_sse_event(EventType.PLAN_CREATED, data)
        else:
            return create_sse_event(EventType.PLANNING_STARTED, data)

    elif phase == ProcessPhase.EXECUTING:
        step_data = event.data or {}
        if "step" in step_data:
            # Check step_status to determine if started or completed
            step_status = step_data.get("step_status", "started")
            if step_status == "completed":
                return create_sse_event(EventType.STEP_COMPLETED, data)
            else:
                return create_sse_event(EventType.STEP_STARTED, data)
        return None

    elif phase == ProcessPhase.VALIDATING:
        if "validation" in (event.data or {}):
            return create_sse_event(EventType.VALIDATION_RESULT, data)
        return None

    elif phase == ProcessPhase.FIXING:
        return create_sse_event(EventType.STEP_STARTED, {
            **data,
            "fixing": True,
        })

    elif phase in [ProcessPhase.COMPLETED, ProcessPhase.FAILED]:
        # These are handled separately
        return None

    return None


# ============== Streaming Question Response ==============

async def stream_question_response(
    project_id: str,
    question: str,
    conversation_id: str,
    user_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for question answering.

    Uses the orchestrator to get context, then streams Claude's response.
    """
    logger.info(f"[CHAT] Answering question for project={project_id}")

    # Start AI operations session for logging
    ops_session_id = _ops_logger.start_chat_session(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
    )

    # Get or create conversation
    conversation = await get_or_create_conversation(db, user_id, project_id, conversation_id)

    # Initialize conversation logger
    conv_logger = get_conversation_logger(
        conversation_id=conversation.id,
        project_id=project_id,
        user_id=user_id,
    )

    # Fetch conversation history BEFORE saving current message
    history = await get_conversation_history(db, conversation.id, limit=10)
    conversation_context = format_conversation_history(history)

    # Count messages for logging
    message_count = len(history) + 1

    # Log user question
    conv_logger.log_user_message(
        message=question,
        message_number=message_count,
        conversation_context=conversation_context if conversation_context else None,
    )

    # Now save the user message
    await save_message(db, conversation.id, "user", question)

    yield create_sse_event(EventType.CONNECTED, {
        "conversation_id": conversation.id,
        "message": "Connected to chat stream",
    })

    try:
        # Create tracked Claude service for this request
        tracker = UsageTracker(db)
        claude_service = create_tracked_claude_service(
            tracker=tracker,
            user_id=user_id,
            project_id=project_id,
        )

        # Create orchestrator for context retrieval with tracked Claude service and logger
        orchestrator = Orchestrator(db=db, claude_service=claude_service, conversation_logger=conv_logger)

        # Get intent, context, and project context (include conversation history in question)
        question_with_context = question
        if conversation_context:
            question_with_context = f"{conversation_context}\n\n<current_question>\n{question}\n</current_question>"
            logger.info(f"[CHAT] Including {len(history)} previous messages in question context")

        yield create_sse_event(EventType.INTENT_ANALYZED, {
            "message": "Analyzing your question...",
            "progress": 0.1,
        })

        intent, context, project_context = await orchestrator.process_question(project_id, question_with_context)

        yield create_sse_event(EventType.INTENT_ANALYZED, {
            "message": f"Identified as: {intent.task_type}",
            "progress": 0.2,
            "intent": intent.to_dict(),
        })

        yield create_sse_event(EventType.CONTEXT_RETRIEVED, {
            "message": f"Found {len(context.chunks)} relevant code sections",
            "progress": 0.3,
            "chunks_count": len(context.chunks),
        })

        # Build prompt for question answering with rich project context
        user_prompt = f"""<question>
{question}
</question>
{conversation_context if conversation_context else ""}
<project_info>
{project_context}
</project_info>

<codebase_context>
{context.to_prompt_string()}
</codebase_context>

Answer the question based on this project's specific technology stack, conventions, and patterns. Reference actual code and files when relevant. If the user is referring to previous conversation context, use that information to provide a relevant answer."""

        # Stream response from Claude using cached streaming for prompt caching
        messages = [{"role": "user", "content": user_prompt}]

        full_response = ""
        async for chunk in claude_service.stream_cached(
            model=ClaudeModel.SONNET,
            messages=messages,
            system=CHAT_SYSTEM_PROMPT,
            temperature=0.7,
            request_type="chat",
        ):
            full_response += chunk
            yield create_sse_event(EventType.ANSWER_CHUNK, {
                "chunk": chunk,
            })

        # Save assistant message
        await save_message(db, conversation.id, "assistant", full_response)

        # Log the final response
        conv_logger.log_response(
            response_content=full_response,
            response_type="assistant",
            is_streaming=False,
        )

        # Finalize the conversation log
        log_paths = finalize_conversation_logger(conversation.id)
        logger.info(f"[CHAT] Question conversation log finalized: {log_paths}")

        # End AI operations session and get summary
        ops_summary = _ops_logger.end_chat_session(ops_session_id)

        # Send complete event
        yield create_sse_event(EventType.COMPLETE, {
            "success": True,
            "answer": full_response,
            "log_paths": log_paths,  # Include log file paths in response
            "ops_summary": ops_summary,  # Include AI operations summary
        })

    except Exception as e:
        logger.exception(f"[CHAT] Question stream error: {e}")
        # Log error to operations logger
        _ops_logger.log(
            operation_type=OperationType.ERROR,
            message=f"Question stream error: {str(e)}",
            user_id=user_id,
            project_id=project_id,
            success=False,
            error=str(e),
        )
        # End AI operations session
        _ops_logger.end_chat_session(ops_session_id)
        # Log error
        conv_logger.log_error(
            error_message=str(e),
            error_type="question_stream_error",
        )
        # Finalize the conversation log even on error
        finalize_conversation_logger(conversation.id)
        await save_message(db, conversation.id, "assistant", f"Error: {str(e)}")
        yield create_sse_event(EventType.ERROR, {
            "message": str(e),
        })


# ============== API Endpoints ==============

@router.get("/{project_id}/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all conversations for a project.

    Returns conversations sorted by most recent first.
    """
    logger.info(f"[CHAT] GET /projects/{project_id}/conversations - user_id={current_user.id}")

    # Verify project access (but don't require READY status for viewing history)
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get conversations with message count
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.project_id == project_id,
            Conversation.user_id == current_user.id,
        )
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    # Build response with message counts
    response = []
    for conv in conversations:
        last_msg = None
        if conv.messages:
            sorted_messages = sorted(conv.messages, key=lambda m: m.created_at, reverse=True)
            if sorted_messages:
                last_msg = sorted_messages[0].content[:100]

        response.append(ConversationResponse(
            id=conv.id,
            project_id=conv.project_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages),
            last_message=last_msg,
        ))

    return response


@router.get("/{project_id}/conversations/{conversation_id}", response_model=List[ChatMessageResponse])
async def get_conversation_messages(
    project_id: str,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all messages in a conversation.

    Returns messages in chronological order.
    """
    logger.info(f"[CHAT] GET /projects/{project_id}/conversations/{conversation_id} - user_id={current_user.id}")

    # Verify conversation belongs to user and project
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.project_id == project_id,
        Conversation.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get messages
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            code_changes=msg.code_changes,
            processing_data=msg.processing_data,
            created_at=msg.created_at,
        )
        for msg in messages
    ]


@router.delete("/{project_id}/conversations/{conversation_id}")
async def delete_conversation(
    project_id: str,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a conversation and all its messages."""
    logger.info(f"[CHAT] DELETE /projects/{project_id}/conversations/{conversation_id} - user_id={current_user.id}")

    # Verify conversation belongs to user and project
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.project_id == project_id,
        Conversation.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    await db.delete(conversation)
    await db.commit()

    return {"message": "Conversation deleted"}


@router.get("/{project_id}/conversations/{conversation_id}/logs")
async def get_conversation_logs(
    project_id: str,
    conversation_id: str,
    log_type: str = Query("main", description="Type of log: main, json, agents, files"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get conversation logs for analysis.

    Returns the contents of conversation log files.

    Log types:
    - main: Full conversation log in human-readable format
    - json: Structured JSON log with all entries
    - agents: Detailed agent outputs
    - files: File change tracking

    Returns:
        The log content or paths to log files
    """
    import os
    from pathlib import Path

    logger.info(f"[CHAT] GET /projects/{project_id}/conversations/{conversation_id}/logs - user_id={current_user.id}")

    # Verify conversation belongs to user and project
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.project_id == project_id,
        Conversation.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Build log directory path
    log_dir = Path("/tmp/conversation_logs") / project_id / conversation_id

    # Map log types to file names
    log_files = {
        "main": "conversation.txt",
        "json": "conversation.json",
        "agents": "agents.txt",
        "files": "file_changes.txt",
    }

    if log_type not in log_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid log type. Must be one of: {', '.join(log_files.keys())}",
        )

    log_file = log_dir / log_files[log_type]

    if not log_file.exists():
        # Return empty response with info about available logs
        available_logs = [
            log_type for log_type, filename in log_files.items()
            if (log_dir / filename).exists()
        ]
        return {
            "exists": False,
            "message": f"Log file not found. Conversation may not have been logged yet.",
            "available_logs": available_logs,
            "log_dir": str(log_dir),
        }

    try:
        content = log_file.read_text(encoding="utf-8")

        # For JSON logs, parse and return as dict
        if log_type == "json":
            import json
            return {
                "exists": True,
                "log_type": log_type,
                "data": json.loads(content),
            }
        else:
            return {
                "exists": True,
                "log_type": log_type,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
            }
    except Exception as e:
        logger.error(f"[CHAT] Error reading log file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading log file: {str(e)}",
        )


@router.get("/{project_id}/conversations/{conversation_id}/logs/download")
async def download_conversation_logs(
    project_id: str,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download all conversation logs as a zip file.

    Returns a zip archive containing all log files for the conversation.
    """
    import io
    import zipfile
    from pathlib import Path
    from fastapi.responses import Response

    logger.info(f"[CHAT] GET /projects/{project_id}/conversations/{conversation_id}/logs/download - user_id={current_user.id}")

    # Verify conversation belongs to user and project
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.project_id == project_id,
        Conversation.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Build log directory path
    log_dir = Path("/tmp/conversation_logs") / project_id / conversation_id

    if not log_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logs found for this conversation",
        )

    # Create zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for log_file in log_dir.glob("*"):
            if log_file.is_file():
                zip_file.write(log_file, log_file.name)

    zip_buffer.seek(0)

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=conversation_logs_{conversation_id[:8]}.zip"
        },
    )


@router.post("/{project_id}/chat")
async def chat_with_project(
    project_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat with AI about a project.

    Returns Server-Sent Events (SSE) stream with progress updates.

    Events:
    - connected: Connection established
    - intent_analyzed: User intent understood
    - context_retrieved: Relevant code found
    - planning_started: Creating implementation plan
    - plan_created: Plan ready
    - step_started: Executing a step
    - step_completed: Step finished
    - validation_result: Code validated
    - answer_chunk: Streaming text response (for questions)
    - complete: Processing finished
    - error: An error occurred
    """
    logger.info(f"[CHAT] POST /projects/{project_id}/chat - user_id={current_user.id}")

    # Verify project access
    project = await verify_project_access(project_id, current_user, db)

    # Generate or use conversation ID
    conversation_id = request.conversation_id or str(uuid4())

    logger.info(f"[CHAT] Processing message: {request.message[:100]}...")

    # Determine if this is a question or action request
    # For now, we'll use a simple heuristic - questions end with ?
    # The intent analyzer will refine this
    is_likely_question = request.message.strip().endswith("?")

    if is_likely_question:
        # Stream question response
        return StreamingResponse(
            stream_question_response(
                project_id=project_id,
                question=request.message,
                conversation_id=conversation_id,
                user_id=current_user.id,
                db=db,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    else:
        # Stream action response (full orchestration)
        return StreamingResponse(
            stream_chat_response(
                project_id=project_id,
                message=request.message,
                conversation_id=conversation_id,
                user_id=current_user.id,
                db=db,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


@router.post("/{project_id}/chat/sync", response_model=ChatResponse)
async def chat_sync(
    project_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Synchronous chat endpoint (non-streaming).

    Use this for simple requests where streaming is not needed.
    Returns the complete response at once.
    """
    logger.info(f"[CHAT] POST /projects/{project_id}/chat/sync - user_id={current_user.id}")

    # Verify project access
    project = await verify_project_access(project_id, current_user, db)

    # Get or create conversation
    conversation = await get_or_create_conversation(
        db, current_user.id, project_id, request.conversation_id
    )

    # Start AI operations session for logging
    ops_session_id = _ops_logger.start_chat_session(
        user_id=str(current_user.id),
        project_id=project_id,
        conversation_id=conversation.id,
    )

    # Initialize conversation logger
    conv_logger = get_conversation_logger(
        conversation_id=conversation.id,
        project_id=project_id,
        user_id=str(current_user.id),
    )

    # Fetch conversation history for context logging
    history = await get_conversation_history(db, conversation.id, limit=10)
    conversation_context = format_conversation_history(history)

    # Log user message
    conv_logger.log_user_message(
        message=request.message,
        message_number=len(history) + 1,
        conversation_context=conversation_context if conversation_context else None,
    )

    # Save user message
    await save_message(db, conversation.id, "user", request.message)

    try:
        # Create tracked Claude service for this request
        tracker = UsageTracker(db)
        claude_service = create_tracked_claude_service(
            tracker=tracker,
            user_id=str(current_user.id),
            project_id=project_id,
        )

        # Create orchestrator with tracked Claude service and logger
        orchestrator = Orchestrator(db=db, claude_service=claude_service, conversation_logger=conv_logger)

        # Check if question or action
        is_question = request.message.strip().endswith("?")

        if is_question:
            # Get context, project context and answer question
            intent, context, project_context = await orchestrator.process_question(project_id, request.message)

            user_prompt = f"""<question>
{request.message}
</question>

<project_info>
{project_context}
</project_info>

<codebase_context>
{context.to_prompt_string()}
</codebase_context>

Answer based on this project's specific technology stack, conventions, and patterns."""

            response_text = await claude_service.chat_async(
                model=ClaudeModel.SONNET,
                messages=[{"role": "user", "content": user_prompt}],
                system=CHAT_SYSTEM_PROMPT_SIMPLE,
                request_type="chat",
            )

            # Save assistant message
            saved_message = await save_message(db, conversation.id, "assistant", response_text)

            # Log the response and finalize
            conv_logger.log_response(
                response_content=response_text,
                response_type="assistant",
                is_streaming=False,
            )
            finalize_conversation_logger(conversation.id)

            # End AI operations session
            _ops_logger.end_chat_session(ops_session_id)

            return ChatResponse(
                conversation_id=conversation.id,
                message=ChatMessageResponse(
                    id=saved_message.id,
                    role="assistant",
                    content=response_text,
                    created_at=saved_message.created_at,
                ),
            )

        else:
            # Full orchestration
            result = await orchestrator.process_request(project_id, request.message)

            # Format response
            if result.success:
                # Check if this was classified as a question (no plan/execution)
                if not result.plan and not result.execution_results:
                    # This was classified as a question - generate an answer
                    logger.info("[CHAT] Intent classified as question, generating answer...")

                    intent = result.intent
                    context = await orchestrator.context_retriever.retrieve(project_id, intent) if intent else None
                    project_context = orchestrator.build_project_context(await orchestrator._get_project(project_id))

                    user_prompt = f"""<question>
{request.message}
</question>

<project_info>
{project_context}
</project_info>

<codebase_context>
{context.to_prompt_string() if context else "No context available"}
</codebase_context>

Answer based on this project's specific technology stack, conventions, and patterns."""

                    response_content = await claude_service.chat_async(
                        model=ClaudeModel.SONNET,
                        messages=[{"role": "user", "content": user_prompt}],
                        system=CHAT_SYSTEM_PROMPT_SIMPLE,
                        request_type="chat",
                    )
                    code_changes = None
                else:
                    # Normal task completion with plan and execution
                    summary_parts = []
                    if result.plan:
                        summary_parts.append(f"**Plan:** {result.plan.summary}")
                    if result.execution_results:
                        summary_parts.append(f"**Files changed:** {len(result.execution_results)}")
                        for r in result.execution_results:
                            summary_parts.append(f"- [{r.action}] {r.file}")
                    if result.validation:
                        summary_parts.append(f"**Validation score:** {result.validation.score}/100")

                    response_content = "\n".join(summary_parts) if summary_parts else "Task completed."

                    code_changes = {
                        "results": [r.to_dict() for r in result.execution_results],
                        "validation": result.validation.to_dict() if result.validation else None,
                    } if result.execution_results else None
            else:
                response_content = f"Failed to process request: {result.error}"
                code_changes = None

            # Save assistant message
            saved_message = await save_message(
                db, conversation.id, "assistant", response_content, code_changes
            )

            # Log the response and finalize
            conv_logger.log_response(
                response_content=response_content,
                response_type="assistant",
                is_streaming=False,
            )
            finalize_conversation_logger(conversation.id)

            # End AI operations session
            _ops_logger.end_chat_session(ops_session_id)

            return ChatResponse(
                conversation_id=conversation.id,
                message=ChatMessageResponse(
                    id=saved_message.id,
                    role="assistant",
                    content=response_content,
                    code_changes=code_changes,
                    created_at=saved_message.created_at,
                ),
                code_changes=code_changes,
            )

    except Exception as e:
        logger.exception(f"[CHAT] Sync chat error: {e}")
        # Log error to operations logger
        _ops_logger.log(
            operation_type=OperationType.ERROR,
            message=f"Sync chat error: {str(e)}",
            user_id=str(current_user.id),
            project_id=project_id,
            success=False,
            error=str(e),
        )
        # End AI operations session
        _ops_logger.end_chat_session(ops_session_id)
        # Log error and finalize
        conv_logger.log_error(
            error_message=str(e),
            error_type="sync_chat_error",
        )
        finalize_conversation_logger(conversation.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============== AI Operations Logs Endpoints ==============

@router.get("/operations/stats")
async def get_operations_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Get global AI operations statistics.

    Returns aggregated stats across all sessions:
    - Total operations count
    - Total API calls
    - Total tokens used
    - Total cost
    - Cache hit statistics
    - Cost saved through caching
    """
    logger.info(f"[CHAT] GET /operations/stats - user_id={current_user.id}")

    stats = _ops_logger.get_global_stats()

    return {
        "success": True,
        "stats": stats,
    }


@router.get("/operations/recent")
async def get_recent_operations(
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent AI operations across all sessions.

    Returns the most recent operations with full details.
    Useful for debugging and monitoring AI usage.
    """
    logger.info(f"[CHAT] GET /operations/recent - user_id={current_user.id}")

    operations = _ops_logger.get_recent_operations(limit=limit)

    return {
        "success": True,
        "count": len(operations),
        "operations": operations,
    }


@router.get("/operations/session/{session_id}")
async def get_session_operations(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get operations for a specific AI session.

    Returns all operations logged during the session with summary statistics.
    """
    logger.info(f"[CHAT] GET /operations/session/{session_id} - user_id={current_user.id}")

    session = _ops_logger.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {
        "success": True,
        "session": session.to_dict(),
    }


@router.get("/operations/logs/{date}")
async def get_operations_logs_by_date(
    date: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get saved operation logs for a specific date.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        List of available log files for the date
    """
    from pathlib import Path

    logger.info(f"[CHAT] GET /operations/logs/{date} - user_id={current_user.id}")

    log_dir = Path("/tmp/laravelai_ops_logs") / date

    if not log_dir.exists():
        return {
            "success": True,
            "message": f"No logs found for date {date}",
            "logs": [],
        }

    # List all log files
    logs = []
    for log_file in log_dir.glob("*.json"):
        try:
            import json
            with open(log_file, "r") as f:
                data = json.load(f)
                logs.append({
                    "filename": log_file.name,
                    "session_id": data.get("session_id"),
                    "user_id": data.get("user_id"),
                    "project_id": data.get("project_id"),
                    "started_at": data.get("started_at"),
                    "total_operations": data.get("total_operations"),
                    "total_cost": data.get("total_cost"),
                    "cache_stats": data.get("cache_stats"),
                })
        except Exception as e:
            logger.error(f"[CHAT] Error reading log file {log_file}: {e}")

    return {
        "success": True,
        "date": date,
        "count": len(logs),
        "logs": logs,
    }


@router.get("/operations/logs/{date}/{session_id}")
async def get_operations_log_detail(
    date: str,
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed operations log for a specific session.

    Returns the full session log with all operations.
    """
    from pathlib import Path
    import json

    logger.info(f"[CHAT] GET /operations/logs/{date}/{session_id} - user_id={current_user.id}")

    log_file = Path("/tmp/laravelai_ops_logs") / date / f"session_{session_id}.json"

    if not log_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log file not found for session {session_id} on {date}",
        )

    try:
        with open(log_file, "r") as f:
            data = json.load(f)

        return {
            "success": True,
            "session": data,
        }
    except Exception as e:
        logger.error(f"[CHAT] Error reading log file {log_file}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading log file: {str(e)}",
        )


# ============== Batch Processing Endpoints ==============

class BatchAnalysisRequest(BaseModel):
    """Request body for batch file analysis."""
    files: list[dict]  # List of {"path": str, "content": str}
    analysis_type: str = "file_analysis"  # file_analysis, code_review, security_scan
    wait_for_completion: bool = False


class BatchStatusResponse(BaseModel):
    """Response for batch status check."""
    id: str
    status: str
    total_requests: int
    completed_requests: int
    failed_requests: int
    total_tokens: int
    total_cost: float
    error: Optional[str] = None


# Store batch processor and jobs
_batch_processor = None
_batch_jobs: dict = {}


def _get_batch_processor():
    """Get or create batch processor."""
    global _batch_processor
    if _batch_processor is None:
        from app.services.batch_processor import BatchProcessor
        _batch_processor = BatchProcessor()
    return _batch_processor


@router.post("/{project_id}/batch/analyze")
async def create_batch_analysis(
    project_id: str,
    request: BatchAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a batch analysis job for multiple files.

    Provides 50% cost savings compared to individual API calls.
    Use for bulk file analysis, code review, or security scanning.

    Analysis types:
    - file_analysis: General file analysis (summary, complexity, issues)
    - code_review: Detailed code review with quality score
    - security_scan: Security vulnerability scanning

    Args:
        files: List of {"path": str, "content": str}
        analysis_type: Type of analysis to perform
        wait_for_completion: If true, waits for results (may timeout for large batches)

    Returns:
        Batch job ID and initial status
    """
    from app.services.batch_processor import BatchRequestType

    logger.info(f"[CHAT] POST /{project_id}/batch/analyze - user_id={current_user.id}, files={len(request.files)}")

    # Verify project access
    await verify_project_access(project_id, current_user, db)

    # Map analysis type to BatchRequestType
    type_map = {
        "file_analysis": BatchRequestType.FILE_ANALYSIS,
        "code_review": BatchRequestType.CODE_REVIEW,
        "security_scan": BatchRequestType.SECURITY_SCAN,
        "architecture_review": BatchRequestType.ARCHITECTURE_REVIEW,
        "performance_analysis": BatchRequestType.PERFORMANCE_ANALYSIS,
        "documentation_generation": BatchRequestType.DOCUMENTATION_GENERATION,
    }

    request_type = type_map.get(request.analysis_type, BatchRequestType.FILE_ANALYSIS)

    # Start operations logging
    ops_session_id = _ops_logger.start_chat_session(
        user_id=str(current_user.id),
        project_id=project_id,
        conversation_id=f"batch_{uuid4()}",
    )

    try:
        processor = _get_batch_processor()

        # Create batch job
        job = await processor.analyze_files(
            files=request.files,
            request_type=request_type,
            wait_for_completion=request.wait_for_completion,
        )

        # Store job for later retrieval
        _batch_jobs[job.id] = {
            "job": job,
            "user_id": str(current_user.id),
            "project_id": project_id,
            "ops_session_id": ops_session_id,
        }

        # If completed, end session
        if job.status.value in ["completed", "failed", "cancelled"]:
            _ops_logger.end_chat_session(ops_session_id)

        return {
            "success": True,
            "batch_id": job.id,
            "status": job.status.value,
            "total_requests": job.total_requests,
            "completed_requests": job.completed_requests,
            "failed_requests": job.failed_requests,
            "message": f"Batch job created with {len(request.files)} files. "
                      f"Use GET /batch/{job.id} to check status.",
        }

    except Exception as e:
        logger.exception(f"[CHAT] Batch creation error: {e}")
        _ops_logger.end_chat_session(ops_session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{project_id}/batch/{batch_id}")
async def get_batch_status(
    project_id: str,
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of a batch processing job.

    Returns current status, progress, and results if completed.
    """
    logger.info(f"[CHAT] GET /{project_id}/batch/{batch_id} - user_id={current_user.id}")

    # Check if job exists
    job_data = _batch_jobs.get(batch_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch job not found",
        )

    # Verify ownership
    if job_data["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    job = job_data["job"]

    # If still processing, poll for updates
    if job.status.value == "processing":
        processor = _get_batch_processor()
        job = await processor.poll_batch(job, wait_for_completion=False)
        job_data["job"] = job

        # If now completed, end session
        if job.status.value in ["completed", "failed", "cancelled"]:
            ops_session_id = job_data.get("ops_session_id")
            if ops_session_id:
                _ops_logger.end_chat_session(ops_session_id)

    return {
        "success": True,
        "batch_id": job.id,
        "status": job.status.value,
        "total_requests": job.total_requests,
        "completed_requests": job.completed_requests,
        "failed_requests": job.failed_requests,
        "total_tokens": job.total_tokens,
        "total_cost": job.total_cost,
        "cost_savings": job.total_cost,  # Same as cost since batch is 50% off
        "error": job.error,
        "results": [r.to_dict() for r in job.results] if job.results else [],
    }


@router.delete("/{project_id}/batch/{batch_id}")
async def cancel_batch_job(
    project_id: str,
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a running batch job.
    """
    logger.info(f"[CHAT] DELETE /{project_id}/batch/{batch_id} - user_id={current_user.id}")

    # Check if job exists
    job_data = _batch_jobs.get(batch_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch job not found",
        )

    # Verify ownership
    if job_data["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    job = job_data["job"]

    processor = _get_batch_processor()
    job = await processor.cancel_batch(job)
    job_data["job"] = job

    # End session
    ops_session_id = job_data.get("ops_session_id")
    if ops_session_id:
        _ops_logger.end_chat_session(ops_session_id)

    return {
        "success": True,
        "batch_id": job.id,
        "status": job.status.value,
        "message": "Batch job cancelled",
    }


@router.get("/{project_id}/batch")
async def list_batch_jobs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all batch jobs for the current user.
    """
    logger.info(f"[CHAT] GET /{project_id}/batch - user_id={current_user.id}")

    user_jobs = [
        {
            "batch_id": batch_id,
            "status": data["job"].status.value,
            "total_requests": data["job"].total_requests,
            "completed_requests": data["job"].completed_requests,
            "failed_requests": data["job"].failed_requests,
            "total_cost": data["job"].total_cost,
            "created_at": data["job"].created_at.isoformat(),
        }
        for batch_id, data in _batch_jobs.items()
        if data["user_id"] == str(current_user.id) and data["project_id"] == project_id
    ]

    return {
        "success": True,
        "jobs": user_jobs,
        "count": len(user_jobs),
    }
