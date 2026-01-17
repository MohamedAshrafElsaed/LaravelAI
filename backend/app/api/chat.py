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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Project, User, ProjectStatus
from app.agents.orchestrator import Orchestrator, ProcessEvent, ProcessPhase
from app.services.claude import get_claude_service, ClaudeModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Request/Response Models ==============

class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # user, assistant, system
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response for non-streaming chat."""
    conversation_id: str
    message: ChatMessage
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


# ============== Streaming Generator ==============

async def stream_chat_response(
    project_id: str,
    message: str,
    conversation_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for chat response.

    Yields SSE events as the orchestrator processes the request.
    """
    logger.info(f"[CHAT] Starting stream for project={project_id}, conversation={conversation_id}")

    # Track events for the orchestrator callback
    event_queue: asyncio.Queue = asyncio.Queue()

    async def event_callback(event: ProcessEvent) -> None:
        """Callback to receive orchestrator events."""
        await event_queue.put(event)

    # Send connected event
    yield create_sse_event(EventType.CONNECTED, {
        "conversation_id": conversation_id,
        "message": "Connected to chat stream",
    })

    try:
        # Create orchestrator with event callback
        orchestrator = Orchestrator(db=db, event_callback=event_callback)

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

        # Send final complete event
        yield create_sse_event(EventType.COMPLETE, {
            "success": result.success,
            "plan": result.plan.to_dict() if result.plan else None,
            "execution_results": [r.to_dict() for r in result.execution_results],
            "validation": result.validation.to_dict() if result.validation else None,
            "error": result.error,
        })

    except Exception as e:
        logger.exception(f"[CHAT] Stream error: {e}")
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
            # Check if this is start or completion
            # For now, send step_started for each step event
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
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for question answering.

    Uses the orchestrator to get context, then streams Claude's response.
    """
    logger.info(f"[CHAT] Answering question for project={project_id}")

    yield create_sse_event(EventType.CONNECTED, {
        "conversation_id": conversation_id,
        "message": "Connected to chat stream",
    })

    try:
        # Create orchestrator for context retrieval
        orchestrator = Orchestrator(db=db)

        # Get intent and context
        yield create_sse_event(EventType.INTENT_ANALYZED, {
            "message": "Analyzing your question...",
            "progress": 0.1,
        })

        intent, context = await orchestrator.process_question(project_id, question)

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

        # Build prompt for question answering
        system_prompt = """You are an expert Laravel developer assistant.
Answer the user's question based on the provided codebase context.
Be specific, reference actual code when relevant, and provide examples.
If you're not sure about something, say so."""

        user_prompt = f"""## Question
{question}

## Codebase Context
{context.to_prompt_string()}

Please answer the question based on this codebase context."""

        # Stream response from Claude
        claude = get_claude_service()
        messages = [{"role": "user", "content": user_prompt}]

        full_response = ""
        async for chunk in claude.stream(
            model=ClaudeModel.SONNET,
            messages=messages,
            system=system_prompt,
            temperature=0.7,
        ):
            full_response += chunk
            yield create_sse_event(EventType.ANSWER_CHUNK, {
                "chunk": chunk,
            })

        # Send complete event
        yield create_sse_event(EventType.COMPLETE, {
            "success": True,
            "answer": full_response,
        })

    except Exception as e:
        logger.exception(f"[CHAT] Question stream error: {e}")
        yield create_sse_event(EventType.ERROR, {
            "message": str(e),
        })


# ============== API Endpoints ==============

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

    conversation_id = request.conversation_id or str(uuid4())

    try:
        # Create orchestrator
        orchestrator = Orchestrator(db=db)

        # Check if question or action
        is_question = request.message.strip().endswith("?")

        if is_question:
            # Get context and answer question
            intent, context = await orchestrator.process_question(project_id, request.message)

            system_prompt = """You are an expert Laravel developer assistant.
Answer the user's question based on the provided codebase context."""

            user_prompt = f"""## Question
{request.message}

## Codebase Context
{context.to_prompt_string()}"""

            claude = get_claude_service()
            response_text = await claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )

            return ChatResponse(
                conversation_id=conversation_id,
                message=ChatMessage(
                    role="assistant",
                    content=response_text,
                    timestamp=datetime.utcnow(),
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

            return ChatResponse(
                conversation_id=conversation_id,
                message=ChatMessage(
                    role="assistant",
                    content=response_content,
                    timestamp=datetime.utcnow(),
                ),
                code_changes={
                    "results": [r.to_dict() for r in result.execution_results],
                    "validation": result.validation.to_dict() if result.validation else None,
                } if result.execution_results else None,
            )

    except Exception as e:
        logger.exception(f"[CHAT] Sync chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{conversation_id}/messages", response_model=List[ChatMessage])
async def get_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all messages in a conversation.

    Note: Conversation history storage is not yet implemented.
    """
    logger.info(f"[CHAT] GET /chat/{conversation_id}/messages - user_id={current_user.id}")

    # TODO: Implement conversation history storage
    # For now, return empty list
    return []
