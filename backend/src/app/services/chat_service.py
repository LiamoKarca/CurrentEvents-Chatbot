# -*- coding: utf-8 -*-
"""
聊天服務（Assistants 版）
- 完全使用 OpenAI 平台上「已設定好的 Assistant」。
- /chat：純文字 -> 建 thread -> run -> 取回回覆
- /chat/with-attachments：支援圖片（vision）與文件（file_search），上傳到
  Files 後綁到該 thread
- /memory/clear：刪除這段會話期間上傳的 OpenAI Files + 清理記憶
"""
import io
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import UploadFile
from openai import OpenAI

from .memory_service import MemoryService
from .retriever_service import RetrieverService

load_dotenv()

OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID", "").strip()
if not OPENAI_ASSISTANT_ID:
    raise RuntimeError(
        "環境變數 OPENAI_ASSISTANT_ID 未設定，請在 .env 設定你的 Assistant ID。"
    )

# 用於圖片與文件的副檔名判斷
TEXT_LIKE = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
SEARCHABLE_DOCS = {
    ".txt",
    ".pdf",
    ".md",
    ".doc",
    ".docx",
    ".pptx",
    ".html",
    ".json",
    ".csv",
    ".tex",
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".cs",
    ".rb",
    ".php",
}
IMAGE_LIKE = {".png", ".jpg", ".jpeg", ".webp"}


def _ext(name: str) -> str:
    """回傳副檔名（含點），若沒有則回空字串。"""
    name = (name or "").lower()
    i = name.rfind(".")
    return name[i:] if i >= 0 else ""


class ChatService:
    """聊天服務核心，串接 OpenAI Assistants。"""

    def __init__(
        self,
        memory: MemoryService,
        retriever: RetrieverService,
        client: Optional[OpenAI] = None,
    ):
        self.memory = memory
        self.retriever = retriever
        self.client = client or OpenAI()

    # ----------------- 基本工具 -----------------
    def _wait_run_completed(
        self,
        thread_id: str,
        run_id: str,
        timeout_s: int = 120,
        poll_interval: float = 0.8,
    ) -> str:
        """輪詢直到 run 完成，回傳最終狀態字串。"""
        start = time.time()
        status = "queued"
        while time.time() - start < timeout_s:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run_id
            )
            status = run.status
            if status in ("completed", "failed", "cancelled", "expired"):
                return status
            time.sleep(poll_interval)
        return status

    def _read_latest_assistant_text(self, thread_id: str) -> str:
        """從 thread 取回最新一則 assistant 的文字內容。"""
        msgs = self.client.beta.threads.messages.list(thread_id=thread_id)
        for m in reversed(getattr(msgs, "data", [])):
            if m.role == "assistant" and m.content:
                for c in m.content:
                    if (
                        hasattr(c, "text")
                        and c.text
                        and getattr(c.text, "value", "")
                    ):
                        return c.text.value
        return "（未取得模型回覆）"

    def _delete_file_safe(self, file_id: str) -> bool:
        """嘗試刪除單一 OpenAI File，失敗則略過並回 False。"""
        try:
            self.client.files.delete(file_id)
            return True
        except Exception:
            return False

    # ----------------- 文字聊天 -----------------
    def ask(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """純文字聊天：用平台上的 Assistant。"""
        self.memory.add(user_id, "user", user_message)

        thread = self.client.beta.threads.create(
            messages=[{"role": "user", "content": user_message}]
        )

        run = self.client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=OPENAI_ASSISTANT_ID
        )

        status = self._wait_run_completed(thread_id=thread.id, run_id=run.id)
        if status != "completed":
            answer_text = f"（Assistant run 未完成，狀態：{status}）"
        else:
            answer_text = self._read_latest_assistant_text(thread.id)

        self.memory.add(user_id, "assistant", answer_text)
        return {
            "answer": answer_text,
            "raw": {"thread_id": thread.id, "run_id": run.id, "status": status},
        }

    # ----------------- 附件聊天（圖/檔案） -----------------
    async def ask_with_attachments(
        self, user_id: str, user_message: str, files: List[UploadFile]
    ) -> Dict[str, Any]:
        """
        文字 + 影像（vision） + 可檢索文件（file_search）
        - 上傳到 Files（purpose="assistants"）
        - 可檢索文件綁到 message.attachments
        - 影像以 image_file block 放入 message.content
        """
        self.memory.add(user_id, "user", user_message or "")

        text_snippets: List[Tuple[str, str]] = []
        file_ids_for_search: List[str] = []
        image_file_ids: List[str] = []

        for f in files or []:
            data = await f.read()
            await f.close()
            ext = _ext(f.filename)

            # 文字檔嘗試解出文字，供對話顯示（同時也會上傳以便 file_search）
            if ext in TEXT_LIKE:
                try:
                    text = data.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
                if text.strip():
                    text_snippets.append((f.filename, text))

            # 上傳到 OpenAI Files
            bio = io.BytesIO(data)
            bio.name = f.filename or "upload.bin"
            file_resp = self.client.files.create(file=bio, purpose="assistants")
            file_id = file_resp.id

            # 記錄以便 /memory/clear 時刪除
            self.memory.register_upload(user_id, file_id)

            # 分流：可檢索文件 vs 影像
            if ext in SEARCHABLE_DOCS:
                file_ids_for_search.append(file_id)
            if ext in IMAGE_LIKE:
                image_file_ids.append(file_id)

        # 準備 content blocks（避免空字串 text 觸發 400）
        content_blocks: List[Dict[str, Any]] = []

        # 只有在訊息非空時才加入 text block
        if user_message and user_message.strip():
            content_blocks.append({"type": "text", "text": user_message.strip()})

        # 影像 block
        for fid in image_file_ids:
            content_blocks.append(
                {"type": "image_file", "image_file": {"file_id": fid}}
            )

        # 若文字檔有成功解析文字，附在同一則訊息後面，幫助理解
        if text_snippets:
            merged = "\n\n".join([f"【{name}】\n{txt}" for name, txt in text_snippets])
            content_blocks.append(
                {"type": "text", "text": f"[以下為使用者附檔文字內容]\n{merged}"}
            )

        # 若完全沒有任何 content（例如 message 空 & 無影像 & 無可解讀文字），補一個占位字串
        if not content_blocks:
            content_blocks.append({"type": "text", "text": "（內容見附件）"})

        # 準備 attachments（讓 Assistant 的 file_search 能讀到這些檔案）
        attachments = [
            {"file_id": fid, "tools": [{"type": "file_search"}]}
            for fid in file_ids_for_search
        ]

        # 建立 thread + user 訊息
        thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": content_blocks,
                    **({"attachments": attachments} if attachments else {}),
                }
            ]
        )

        # 透過平台上的 Assistant 執行（Web / file_search / 向量庫等皆以平台設定為準）
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=OPENAI_ASSISTANT_ID
        )

        status = self._wait_run_completed(thread_id=thread.id, run_id=run.id)
        if status != "completed":
            answer_text = f"（Assistant run 未完成，狀態：{status}）"
        else:
            answer_text = self._read_latest_assistant_text(thread.id)

        self.memory.add(user_id, "assistant", answer_text)
        return {
            "answer": answer_text,
            "raw": {"thread_id": thread.id, "run_id": run.id, "status": status},
        }

    # ----------------- 檔案清理 -----------------
    def cleanup_user_uploads(self, user_id: str) -> Dict[str, Any]:
        """刪除某使用者在本服務生命週期內上傳到 OpenAI Files 的所有檔案。"""
        file_ids = self.memory.pop_uploads(user_id)
        ok, fail = [], []
        for fid in file_ids:
            (ok if self._delete_file_safe(fid) else fail).append(fid)
        return {"deleted": ok, "failed": fail}

    def cleanup_all_uploads(self) -> Dict[str, List[str]]:
        """刪除所有使用者已登記的檔案。"""
        all_ids = self.memory.pop_all_uploads()
        result: Dict[str, List[str]] = {}
        for uid, ids in all_ids.items():
            ok: List[str] = []
            for fid in ids:
                if self._delete_file_safe(fid):
                    ok.append(fid)
            result[uid] = ok
        return result
