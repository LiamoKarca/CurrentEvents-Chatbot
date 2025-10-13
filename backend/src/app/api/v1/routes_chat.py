# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from ...services.memory_service import MemoryService
from ...services.retriever_service import RetrieverService
from ...services.chat_service import ChatService

router = APIRouter()


class ChatRequest(BaseModel):
    user_id: str
    message: str
    top_k: Optional[int] = 5


class ClearMemoryRequest(BaseModel):
    user_id: Optional[str] = None   # 不給就清全部（要小心）


# 以簡單的單例模式建立服務
_memory = MemoryService(max_turns=10)
_retriever = RetrieverService(max_results=5)
_chat = ChatService(_memory, _retriever)


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        if req.top_k is not None:
            _retriever.max_results = req.top_k
        res = _chat.ask(req.user_id, req.message)
        return {"reply": res["answer"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/with-attachments")
async def chat_with_attachments(
    user_id: str = Form(...),
    message: str = Form(""),
    files: List[UploadFile] = File(default_factory=list),
    top_k: Optional[int] = Form(5),
):
    """
    multipart/form-data：
      - user_id: 使用者 ID
      - message: 文字訊息
      - files[]: 多個附件（影像/文字/PDF）
      - top_k: 檢索文件數
    """
    try:
        if top_k is not None:
            _retriever.max_results = int(top_k)
        res = await _chat.ask_with_attachments(user_id, message, files)
        return {"reply": res["answer"]}
    except Exception as e:
        print("chat_with_attachments error:", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/clear")
async def clear_memory(req: ClearMemoryRequest):
    """
    清除記憶：
      - 有 user_id：只清該使用者
      - 無 user_id：清全部（⚠️ 請慎用）
    """
    try:
        if req.user_id:
            _memory.clear(req.user_id)
            return {"ok": True, "scope": "user", "user_id": req.user_id}
        else:
            _memory.clear_all()
            return {"ok": True, "scope": "all"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector_store/debug")
async def debug_vector_store():
    """
    回傳目前生效中的 vector_store_ids（含自動選到的最新向量庫）。
    """
    return {"vector_store_ids": _retriever.get_active_vector_store_ids(),
            "max_results": _retriever.max_results}
