"""Authenticated local RAG chat routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth_security import get_current_user
from ..groq_chat import get_project, local_chat

logger = logging.getLogger("mospi_backend.local_chat")

router = APIRouter(prefix="/groq-chat", tags=["Local Project Assistant"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User question")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Optional prior turns")


class ChatSource(BaseModel):
    title: str
    project_id: Optional[str] = None
    text: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]
    model: str


class ChatHealthResponse(BaseModel):
    status: str
    model: str
    project_context_loaded: bool


@router.post("", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Ask a question using role-scoped project records and local Ollama."""
    history = [m.dict() for m in payload.history]
    result = local_chat.chat(db, payload.message, history, user=user)
    return ChatResponse(
        answer=result["answer"],
        sources=[ChatSource(**s) for s in result.get("sources", [])],
        model=result["model"],
    )


@router.get("/tools/get-project/{project_id}")
def get_project_tool(project_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Read-only deterministic project lookup, filtered by the caller's role scope."""
    result = get_project(db, user, project_id)
    if result is None:
        # Same response for nonexistent and unauthorized project IDs.
        raise HTTPException(status_code=404, detail="Project not found in your authorized records.")
    return result


@router.get("/health", response_model=ChatHealthResponse)
def chat_health():
    """Local Ollama model status."""
    return ChatHealthResponse(
        status="online" if local_chat.is_healthy() else "offline",
        model=local_chat.model,
        project_context_loaded=local_chat.context_loaded,
    )
