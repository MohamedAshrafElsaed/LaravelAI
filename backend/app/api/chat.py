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
from app.models.models import Project, User, ProjectStatus, Conversation, Message
from app.agents.orchestrator import Orchestrator, ProcessEvent, ProcessPhase
from app.services.claude import get_claude_service, create_tracked_claude_service, ClaudeModel
from app.services.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)

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

    # Get or create conversation and save user message
    conversation = await get_or_create_conversation(db, user_id, project_id, conversation_id)
    await save_message(db, conversation.id, "user", message)

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

        # Create orchestrator with event callback and tracked Claude service
        orchestrator = Orchestrator(
            db=db,
            event_callback=event_callback,
            claude_service=claude_service,
        )

        # Start processing in background
        process_task = asyncio.create_task(
            orchestrator.process_request(project_id, message)
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

        # Send final complete event
        yield create_sse_event(EventType.COMPLETE, {
            "success": result.success,
            "answer": response_content,
            "plan": result.plan.to_dict() if result.plan else None,
            "execution_results": [r.to_dict() for r in result.execution_results],
            "validation": result.validation.to_dict() if result.validation else None,
            "error": result.error,
        })

    except Exception as e:
        logger.exception(f"[CHAT] Stream error: {e}")
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

    # Get or create conversation and save user message
    conversation = await get_or_create_conversation(db, user_id, project_id, conversation_id)
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

        # Create orchestrator for context retrieval with tracked Claude service
        orchestrator = Orchestrator(db=db, claude_service=claude_service)

        # Get intent, context, and project context
        yield create_sse_event(EventType.INTENT_ANALYZED, {
            "message": "Analyzing your question...",
            "progress": 0.1,
        })

        intent, context, project_context = await orchestrator.process_question(project_id, question)

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
        system_prompt = """You are an expert developer assistant with deep knowledge of this specific codebase.
Answer the user's question based on the provided project information and codebase context.
Be specific, reference actual code when relevant, and provide examples.
Follow the project's conventions and patterns when suggesting solutions.
If you're not sure about something, say so."""

        user_prompt = f"""## Question
{question}

{project_context}

## Relevant Code Context
{context.to_prompt_string()}

Please answer the question based on this project and codebase context. Use the technology stack, conventions, and patterns specific to this project."""

        # Stream response from Claude using the tracked service
        messages = [{"role": "user", "content": user_prompt}]

        full_response = ""
        async for chunk in claude_service.stream(
            model=ClaudeModel.SONNET,
            messages=messages,
            system=system_prompt,
            temperature=0.7,
            request_type="chat",
        ):
            full_response += chunk
            yield create_sse_event(EventType.ANSWER_CHUNK, {
                "chunk": chunk,
            })

        # Save assistant message
        await save_message(db, conversation.id, "assistant", full_response)

        # Send complete event
        yield create_sse_event(EventType.COMPLETE, {
            "success": True,
            "answer": full_response,
        })

    except Exception as e:
        logger.exception(f"[CHAT] Question stream error: {e}")
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

        # Create orchestrator with tracked Claude service
        orchestrator = Orchestrator(db=db, claude_service=claude_service)

        # Check if question or action
        is_question = request.message.strip().endswith("?")

        if is_question:
            # Get context, project context and answer question
            intent, context, project_context = await orchestrator.process_question(project_id, request.message)

            system_prompt = """You are an expert developer assistant with deep knowledge of this specific codebase.
Answer the user's question based on the provided project information and codebase context.
Follow the project's conventions and patterns when suggesting solutions."""

            user_prompt = f"""## Question
{request.message}

{project_context}

## Relevant Code Context
{context.to_prompt_string()}

Please answer based on this project's specific technology stack, conventions, and patterns."""

            response_text = await claude_service.chat_async(
                model=ClaudeModel.SONNET,
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
                request_type="chat",
            )

            # Save assistant message
            saved_message = await save_message(db, conversation.id, "assistant", response_text)

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
                summary_parts = []
                if result.plan:
                    summary_parts.append(f"**Plan:** {result.plan.summary}")
                if result.execution_results:
                    summary_parts.append(f"**Files changed:** {len(result.execution_results)}")
                    for r in result.execution_results:
                        summary_parts.append(f"- [{r.action}] {r.file}")
                if result.validation:
                    summary_parts.append(f"**Validation score:** {result.validation.score}/100")

                response_content = "\n".join(summary_parts)
            else:
                response_content = f"Failed to process request: {result.error}"

            code_changes = {
                "results": [r.to_dict() for r in result.execution_results],
                "validation": result.validation.to_dict() if result.validation else None,
            } if result.execution_results else None

            # Save assistant message
            saved_message = await save_message(
                db, conversation.id, "assistant", response_content, code_changes
            )

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
