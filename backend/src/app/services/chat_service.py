# -*- coding: utf-8 -*-
"""
聊天服務：整合 記憶 + RAG（file_search）+ OpenAI Assistants（支援看圖）
- 模式：
  (A) ask()：純文字訊息（Responses API）
  (B) ask_with_attachments()：文字 + 附件（圖片走 vision；文件走 file_search）
"""
import os
import time
from typing import Optional, Dict, Any, List, Tuple
from openai import OpenAI
from fastapi import UploadFile
from dotenv import load_dotenv

from ..llm.openai_client import get_openai_client
from .memory_service import MemoryService
from .retriever_service import RetrieverService

load_dotenv()  # 會自動讀取專案根目錄的 .env
DEFAULT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

SYSTEM_INSTRUCTION = (
    "你是一位專業的中文助理。"
    "必須結合向量檢索到的文件內容（若有），並忠實引用事實。"
    "若文件不足以回答，請坦誠說明不足並詢問使用者是否要提供更多資訊。"
)

# 可直接拼進文字的副檔名（同時也可能能被 file_search 支援）
TEXT_LIKE = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}

# 依官方 File Search 支援清單整理（可自行增減）
# https://platform.openai.com/docs/assistants/tools/file-search#supported-files
SEARCHABLE_DOCS = {
    ".txt", ".pdf", ".md", ".doc", ".docx", ".pptx", ".html", ".json",
    ".csv", ".tex", ".py", ".java", ".c", ".cpp", ".cs", ".rb", ".php"
}

IMAGE_LIKE = {".png", ".jpg", ".jpeg", ".webp"}


def _ext(name: str) -> str:
    name = (name or "").lower()
    i = name.rfind(".")
    return name[i:] if i >= 0 else ""


class ChatService:
    def __init__(self, memory: MemoryService, retriever: RetrieverService, client: Optional[OpenAI] = None):
        self.memory = memory
        self.retriever = retriever
        self.client = client or get_openai_client()

    def _build_input_text(self, user_id: str, user_message: str) -> str:
        history = self.memory.render_history(user_id)
        parts = [f"[系統指令]\n{SYSTEM_INSTRUCTION}"]
        if history:
            parts.append(f"[對話歷史]\n{history}")
        parts.append(f"[使用者訊息]\n{user_message}")
        return "\n\n".join(parts)

    def _parse_responses_output_text(self, resp) -> str:
        try:
            answer_text = getattr(resp, "output_text", None)
            if not answer_text and hasattr(resp, "output") and resp.output:
                for item in resp.output:
                    if getattr(item, "type", None) == "message":
                        if item.content and len(item.content) > 0:
                            maybe = getattr(item.content[0], "text", None) or getattr(
                                item.content[0], "content", None)
                            if isinstance(maybe, str) and maybe.strip():
                                return maybe
            return answer_text or "（未取得文字輸出）"
        except Exception as e:
            return f"發生解析錯誤：{e!r}"

    # ------ A) 純文字（Responses API）------
    def ask(self, user_id: str, user_message: str) -> Dict[str, Any]:
        self.memory.add(user_id, "user", user_message)

        input_text = self._build_input_text(user_id, user_message)
        tools = self.retriever.build_tools()

        resp = self.client.responses.create(
            model=DEFAULT_MODEL,
            input=input_text,
            tools=tools if tools else None,
        )
        answer_text = self._parse_responses_output_text(resp)
        self.memory.add(user_id, "assistant", answer_text)
        return {"answer": answer_text, "raw": resp.to_dict() if hasattr(resp, "to_dict") else None}

    # 便利函數：輪詢 run 直到完成
    def _wait_run_completed(self, thread_id: str, run_id: str, timeout_s: int = 120, poll_interval: float = 0.8) -> str:
        """
        回傳最終 run 狀態字串；若超時則回傳最後一次狀態
        """
        start = time.time()
        status = "queued"
        while time.time() - start < timeout_s:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run_id)
            status = run.status
            if status in ("completed", "failed", "cancelled", "expired"):
                return status
            time.sleep(poll_interval)
        return status

    # 從 thread 讀最新一則 assistant 訊息文字
    def _read_latest_assistant_text(self, thread_id: str) -> str:
        msgs = self.client.beta.threads.messages.list(thread_id=thread_id)
        for m in reversed(getattr(msgs, "data", [])):
            if m.role == "assistant" and m.content:
                # content 可能有多段，找第一段 text
                for c in m.content:
                    if hasattr(c, "text") and c.text and getattr(c.text, "value", ""):
                        return c.text.value
        return "（未取得模型回覆）"

    # ------ B) 文字 + 附件（影像看圖 + file_search 檢索）------
    async def ask_with_attachments(self, user_id: str, user_message: str, files: List[UploadFile]) -> Dict[str, Any]:
        self.memory.add(user_id, "user", user_message)

        # 收集：可直接拼成文字的內容、可檢索文件、影像
        text_snippets: List[Tuple[str, str]] = []
        file_ids_for_search: List[str] = []
        image_file_ids: List[str] = []

        # 逐檔處理與上傳（全部用 purpose="assistants" 即可）
        for f in files or []:
            data = await f.read()
            await f.close()
            ext = _ext(f.filename)

            # 文字內容：拼進提示詞，並同時可做 file_search（若副檔名支援）
            if ext in TEXT_LIKE:
                try:
                    text = data.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
                if text.strip():
                    text_snippets.append((f.filename, text))

            # 上傳文件到 Files；是否加入 file_search 取決於副檔名是否在支援清單內
            import io
            bio = io.BytesIO(data)
            bio.name = f.filename
            file_resp = self.client.files.create(
                file=bio, purpose="assistants")
            file_id = file_resp.id

            if ext in SEARCHABLE_DOCS:
                file_ids_for_search.append(file_id)

            if ext in IMAGE_LIKE:
                # 影像不加入 file_search；僅作 vision 輸入
                image_file_ids.append(file_id)

        # 文字主體
        merged_text = self._build_input_text(user_id, user_message)
        if text_snippets:
            merged = "\n\n".join([f"\n{txt}" for name, txt in text_snippets])
            merged_text += f"\n[以下為使用者附檔文字內容]\n{merged}"

        # 準備 messages[0].content：先放文字，再逐張圖
        # ⚠️ Assistants Threads 的影像區塊需要 {"type":"image_file","image_file":{"file_id":"..."}}
        content_blocks: List[Dict[str, Any]] = [
            {"type": "text", "text": merged_text}
        ]
        for fid in image_file_ids:
            content_blocks.append(
                {"type": "image_file", "image_file": {"file_id": fid}})

        # 準備 attachments：僅給「可檢索文件」綁 file_search
        attachments = []
        for fid in file_ids_for_search:
            attachments.append(
                {"file_id": fid, "tools": [{"type": "file_search"}]})

        # 建立 thread 並送出含影像/附件的使用者訊息
        thread = self.client.beta.threads.create(messages=[
            {
                "role": "user",
                "content": content_blocks,
                # 若沒有可檢索文件則不要帶 attachments，避免空值序列化問題
                **({"attachments": attachments} if attachments else {})
            }
        ])

        # 執行 run（用你的 Assistant）
        assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=assistant_id)

        # 輪詢直到完成
        status = self._wait_run_completed(thread_id=thread.id, run_id=run.id)
        if status != "completed":
            answer_text = f"（Run 未完成，狀態：{status}）"
        else:
            answer_text = self._read_latest_assistant_text(thread.id)

        self.memory.add(user_id, "assistant", answer_text)
        return {"answer": answer_text, "raw": {"thread_id": thread.id, "run_id": run.id, "status": status}}
