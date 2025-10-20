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
    top_k: Optional[int] = 5  # 仍保留參數，但 Assistants 版本不使用


class ClearMemoryRequest(BaseModel):
    user_id: Optional[str] = None   # 不給就清全部（需謹慎）


# 以簡單單例建立服務
_memory = MemoryService(max_turns=10)
_retriever = RetrieverService(max_results=5)
_chat = ChatService(_memory, _retriever)


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    純文字聊天（Assistants）
    """
    try:
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
      - files[]: 多個附件（影像/文字/PDF 等）
    """
    try:
        res = await _chat.ask_with_attachments(user_id, message, files)
        return {"reply": res["answer"]}
    except Exception as e:
        print("chat_with_attachments error:", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/clear")
async def clear_memory(req: ClearMemoryRequest):
    """
    清除記憶 + 刪除 OpenAI Files：
      - 有 user_id：只清該使用者（含刪除他上傳到 OpenAI 的檔案）
      - 無 user_id：清全部（含刪除所有人已登記的檔案）⚠️ 請慎用
    """
    try:
        if req.user_id:
            delete_report = _chat.cleanup_user_uploads(req.user_id)
            _memory.clear(req.user_id)
            return {
                "ok": True,
                "scope": "user",
                "user_id": req.user_id,
                "deleted_file_ids": delete_report.get("deleted", []),
                "failed_file_ids": delete_report.get("failed", []),
            }
        else:
            deleted = _chat.cleanup_all_uploads()
            _memory.clear_all()
            return {
                "ok": True,
                "scope": "all",
                "deleted_file_ids_by_user": deleted,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector_store/debug")
async def debug_vector_store():
    """
    仍提供除錯端點，但 Assistants 版不使用本地 retriever 綁定。
    """
    return {
        "vector_store_ids": _retriever.get_active_vector_store_ids(),
        "max_results": _retriever.max_results
    }
