# utf-8-sig
"""
FastAPI routes for chat endpoints.

This module exposes REST endpoints for the frontend to interact with
the ChatService, including plain chat and chat with retrieval.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ...routers.auth import get_current_user
from ...services.chat_service import ChatService
from ...services.memory_service import MemoryService
from ...services.retriever_service import RetrieverService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str
    message: str
    chat_id: Optional[str] = None
    conversation_id: Optional[str] = None
    top_k: Optional[int] = 5


class MemoryClearRequest(BaseModel):
    user_id: str


# Global singletons for services (simple approach)
_retriever = RetrieverService(max_results=5)
_upload_tracker = MemoryService(max_turns=1)
_chat = ChatService(_retriever, upload_tracker=_upload_tracker)


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, username: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Plain chat endpoint using OpenAI Responses API."""
    try:
        if username and req.user_id and username != req.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id does not match token")
        resolved_user = username or req.user_id
        chat_id = req.chat_id or req.conversation_id
        result = _chat.ask(resolved_user, req.message, chat_id=chat_id, top_k=req.top_k)
        return {
            "reply": result["answer"],
            "chat_id": result.get("chat_id"),
            "title": result.get("title"),
            "meta": result.get("meta", {}),
        }
    except Exception as exc:  # pragma: no cover - runtime
        logger.exception("Error in /chat endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat/retrieval")
async def chat_with_retrieval(req: ChatRequest, username: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Chat endpoint that also uses custom retrieval as additional context."""
    try:
        if username and req.user_id and username != req.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id does not match token")
        resolved_user = username or req.user_id
        chat_id = req.chat_id or req.conversation_id
        result = _chat.ask_with_retrieval(
            user_id=resolved_user,
            user_message=req.message,
            chat_id=chat_id,
            top_k=req.top_k or 5,
        )
        return {
            "reply": result["answer"],
            "chat_id": result.get("chat_id"),
            "title": result.get("title"),
            "retrieved": result.get("retrieved", []),
            "meta": result.get("meta", {}),
        }
    except Exception as exc:  # pragma: no cover - runtime
        logger.exception("Error in /chat/retrieval endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat/with-attachments")
async def chat_with_attachments(
    user_id: str = Form(...),
    message: str = Form(""),
    chat_id: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    username: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Chat endpoint supporting file/image uploads."""
    try:
        if username and user_id and username != user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id does not match token")
        resolved_user = username or user_id
        resolved_chat_id = chat_id or conversation_id
        result = await _chat.ask_with_attachments(resolved_user, message, files or [], chat_id=resolved_chat_id)
        return {
            "reply": result["answer"],
            "chat_id": result.get("chat_id"),
            "title": result.get("title"),
            "meta": result.get("meta", {}),
            "raw": result.get("raw", {}),
        }
    except Exception as exc:  # pragma: no cover - runtime
        logger.exception("Error in /chat/with-attachments endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/memory/clear")
async def clear_memory(req: MemoryClearRequest, username: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Front-end compatibility endpoint：僅清除記錄的上傳檔案，不含對話（已改用 Firestore）。"""
    if username and req.user_id and username != req.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id does not match token")
    meta = _chat.cleanup_user_uploads(username or req.user_id)
    return {"ok": True, "meta": meta}
