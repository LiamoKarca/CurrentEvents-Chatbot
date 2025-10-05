# -*- coding: utf-8 -*-
"""
聊天服務：整合 記憶 + RAG（file_search）+ OpenAI Responses API
- 支援兩種模式：
  (A) ask()：純文字訊息
  (B) ask_with_attachments()：文字 + 附件（multipart）
"""
import os
import base64
from typing import Optional, Dict, Any, List, Tuple
from openai import OpenAI
from fastapi import UploadFile
from ..llm.openai_client import get_openai_client
from .memory_service import MemoryService
from .retriever_service import RetrieverService

DEFAULT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

SYSTEM_INSTRUCTION = (
    "你是一位專業的中文助理。"
    "必須結合向量檢索到的文件內容（若有），並忠實引用事實。"
    "若文件不足以回答，請坦誠說明不足並詢問使用者是否要提供更多資訊。"
)

TEXT_LIKE = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
IMAGE_LIKE = {".png", ".jpg", ".jpeg", ".webp"}


def _ext(name: str) -> str:
    name = (name or "").lower()
    idx = name.rfind(".")
    return name[idx:] if idx >= 0 else ""


class ChatService:
    def __init__(self, memory: MemoryService, retriever: RetrieverService, client: Optional[OpenAI] = None):
        self.memory = memory
        self.retriever = retriever
        self.client = client or get_openai_client()

    def _build_input_text(self, user_id: str, user_message: str) -> str:
        """
        將 system + history + 本次訊息 合併成一段 input（簡潔易控 tokens）。
        """
        history_block = self.memory.render_history(user_id)
        parts = [f"[系統指令]\n{SYSTEM_INSTRUCTION}"]
        if history_block:
            parts.append(f"[對話歷史]\n{history_block}")
        parts.append(f"[使用者訊息]\n{user_message}")
        return "\n\n".join(parts)

    def _parse_output_text(self, resp) -> str:
        try:
            answer_text = getattr(resp, "output_text", None)
            if not answer_text and hasattr(resp, "output") and resp.output:
                for item in resp.output:
                    if getattr(item, "type", None) == "message":
                        if item.content and len(item.content) > 0:
                            maybe = getattr(item.content[0], "text", None) or getattr(
                                item.content[0], "content", None)
                            if isinstance(maybe, str) and maybe.strip():
                                answer_text = maybe
                                break
            return answer_text or "（未取得文字輸出）"
        except Exception as e:
            return f"發生解析錯誤：{e!r}"

    # ------ A) 純文字 ------
    def ask(self, user_id: str, user_message: str) -> Dict[str, Any]:
        self.memory.add(user_id, "user", user_message)

        input_text = self._build_input_text(user_id, user_message)
        tools = self.retriever.build_tools()

        resp = self.client.responses.create(
            model=DEFAULT_MODEL,
            input=input_text,
            tools=tools if tools else None,
        )
        answer_text = self._parse_output_text(resp)
        self.memory.add(user_id, "assistant", answer_text)
        return {"answer": answer_text, "raw": resp.to_dict() if hasattr(resp, "to_dict") else None}

    # ------ B) 文字 + 附件（影像/文字/PDF）------
    def ask_with_attachments(self, user_id: str, user_message: str, files: List[UploadFile]) -> Dict[str, Any]:
        self.memory.add(user_id, "user", user_message)

        # 準備多模態 content
        content_blocks: List[Dict[str, Any]] = [
            {"type": "input_text", "text": self._build_input_text(user_id, user_message)}]

        text_accumulator: List[Tuple[str, str]] = []  # (filename, text)
        for f in files or []:
            data = f.file.read()
            f.file.close()
            ext = _ext(f.filename)

            # 1) 純文字類：直接拼進去
            if ext in TEXT_LIKE:
                try:
                    text = data.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
                if text.strip():
                    text_accumulator.append((f.filename, text))

            # 2) 影像類：用 input_image（base64）
            elif ext in IMAGE_LIKE:
                b64 = base64.b64encode(data).decode("utf-8")
                mime = "image/png" if ext == ".png" else "image/jpeg"
                content_blocks.append({
                    "type": "input_image",
                    "image": {"data": b64, "mime_type": mime}
                })
            # 3) PDF / 其他：先嘗試當文字（很多 PDF 其實可直接解碼），解不出來就交給模型視覺能力
            else:
                try:
                    text = data.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
                if text.strip():
                    text_accumulator.append((f.filename, text))
                else:
                    # 無法解碼成文字，就當成通用二進位文件交給模型（以 input_image 流程處理會失真）
                    # 保守做法：附上提示，請模型說它看到了什麼（若模型支援文件理解會自行處理）
                    b64 = base64.b64encode(data).decode("utf-8")
                    content_blocks.append({
                        "type": "input_file",
                        "file": {"data": b64, "mime_type": "application/octet-stream", "name": f.filename}
                    })

        # 如果有收集到可讀文字檔，把它們合成一段附註文字
        if text_accumulator:
            merged = "\n\n".join(
                [f"【{name}】\n{txt}" for name, txt in text_accumulator])
            content_blocks.append({
                "type": "input_text",
                "text": f"[以下為使用者附檔文字內容]\n{merged}"
            })

        tools = self.retriever.build_tools()
        resp = self.client.responses.create(
            model=DEFAULT_MODEL,
            input=[{"role": "user", "content": content_blocks}],
            tools=tools if tools else None,
        )
        answer_text = self._parse_output_text(resp)
        self.memory.add(user_id, "assistant", answer_text)
        return {"answer": answer_text, "raw": resp.to_dict() if hasattr(resp, "to_dict") else None}
