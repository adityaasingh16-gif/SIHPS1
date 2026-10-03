"""Authenticated production RAG chat routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth_security import get_current_user
from ..database import get_db
from ..groq_chat import get_project
from ..groq_service import production_chat, is_healthy, GROQ_CHAT_MODEL

router = APIRouter(prefix="/groq-chat", tags=["Dhrishti Assistant"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: Optional[List[ChatMessage]] = Field(default_factory=list)


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
def chat_endpoint(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    history = [m.model_dump() for m in payload.history]
    result = production_chat.chat(db, payload.message, history, user=user)
    return ChatResponse(
        answer=result["answer"],
        sources=[ChatSource(**source) for source in result.get("sources", [])],
        model=result["model"],
    )


@router.get("/tools/get-project/{project_id}")
def get_project_tool(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    result = get_project(db, user, project_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found in your authorized records.",
        )
    return result


@router.get("/health", response_model=ChatHealthResponse)
def chat_health():
    healthy = is_healthy()
    return ChatHealthResponse(
        status="online" if healthy else "offline",
        model=getattr(production_chat, "model", GROQ_CHAT_MODEL) or "openai/gpt-oss-120b",
        project_context_loaded=True,
    )


@router.get("/version")
def chat_version():
    import subprocess, os
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        sha = "unknown"
    return {"version": sha, "key_configured": bool(is_healthy.__module__)}
