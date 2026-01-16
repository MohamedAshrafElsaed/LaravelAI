"""AI chat routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    project_id: str
    conversation_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    code_changes: Optional[dict] = None


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get AI response."""
    # TODO: Implement with AI agents
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Stream AI response."""
    # TODO: Implement streaming
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{conversation_id}/messages", response_model=List[ChatMessage])
async def get_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a conversation."""
    raise HTTPException(status_code=501, detail="Not implemented yet")