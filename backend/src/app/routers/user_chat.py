# -*- coding: utf-8-sig -*-
"""
Per-user chat saving/listing/loading endpoints.
"""

from typing import Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from pydantic import BaseModel, Field

from .auth import get_current_user
from ..services.firestore_store import (
    delete_chat as delete_chat_doc,
    list_chats,
    load_chat,
    upsert_chat,
)

router = APIRouter(prefix="/api/v1/chats", tags=["chats"])

class Message(BaseModel):
    """Single chat message.

    Attributes:
        role: Message role ('user' | 'assistant' | 'system').
        content: Text content.
    """
    role: Literal["user", "assistant", "system"]
    content: str


class SaveChatIn(BaseModel):
    """Payload for saving a chat.

    Attributes:
        title: Optional custom title; default to auto date title.
        messages: Whole conversation turns.
    """
    title: Optional[str] = None
    messages: List[Message]
    chat_id: Optional[str] = None   # ✅ 讓前端能指定原檔續寫


@router.post("/save")
def save_chat_api(data: SaveChatIn, username: str = Depends(get_current_user)) -> Dict:
    """Save/Upsert chat for current user."""
    meta = upsert_chat(
        username=username,
        messages=[m.model_dump() for m in data.messages],
        chat_id=data.chat_id,
        title=data.title,
    )
    return {"ok": True, "meta": meta}


@router.get("/list")
def list_chats_api(username: str = Depends(get_current_user)) -> Dict:
    """List chat index for current user."""
    rows = list_chats(username)
    return {"items": rows}


@router.get("/{chat_id}")
def load_chat_api(chat_id: str, username: str = Depends(get_current_user)) -> Dict:
    """Load a chat JSON by chat_id."""
    data = load_chat(username, chat_id)
    if not data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return data

@router.delete("/{chat_id}")
def delete_chat_record(chat_id: str, username: str = Depends(get_current_user)):
    """刪除目前使用者的一筆聊天紀錄（JSON + 索引列）。"""
    meta = delete_chat_doc(username, chat_id)
    if not meta.get("deleted"):
        raise HTTPException(status_code=404, detail="chat not found")
    return JSONResponse({"ok": True, "meta": meta})
