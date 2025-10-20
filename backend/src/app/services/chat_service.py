"""
聊天服務（Responses 版：同時啟用 Web Search + File Search）
- /chat：使用 Responses API，一次請求同時啟 `web_search` 與 `file_search`
- /chat/with-attachments：暫時沿用 Assistants 版本（上傳檔案綁 thread 附件，供 file_search 檢索）
- /memory/clear：與既有相同

參考：
- Web Search（Responses 工具）：https://platform.openai.com/docs/guides/tools-web-search
- File Search（Responses 工具）：https://cookbook.openai.com/examples/file_search_responses
- Assistants 附件掛載（file_search）：https://platform.openai.com/docs/assistants/tools/file-search
"""

import io
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import UploadFile
from openai import OpenAI

from .memory_service import MemoryService
from .retriever_service import RetrieverService

# 讀取 .env（OPENAI_API_KEY / OPENAI_CHAT_MODEL / OPENAI_VECTOR_STORE_IDS 等）
load_dotenv()

OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o").strip()
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID", "").strip()

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
    """取得副檔名（含點），若沒有則回空字串。"""
    name = (name or "").lower()
    i = name.rfind(".")
    return name[i:] if i >= 0 else ""


class ChatService:
    """聊天服務核心，使用 Responses API（同時啟用 web_search + file_search）。"""

    def __init__(
        self,
        memory: MemoryService,
        retriever: RetrieverService,
        client: Optional[OpenAI] = None,
    ):
        """初始化服務。

        Args:
            memory: 對話記憶服務。
            retriever: 檢索服務（提供 file_search 所需之 vector_store_ids）。
            client: OpenAI SDK 用戶端，預設從環境變數建立。
        """
        self.memory = memory
        self.retriever = retriever
        self.client = client or OpenAI()
        # 僅使用專案內指定的系統提示詞：backend/src/app/prompts/system/bot.md
        # 注意：目前檔案位於 services/，因此需回到上一層再進入 prompts/
        bot_md_path = (Path(__file__).parents[1] / "prompts" / "system" / "bot.md").resolve()
        try:
            self._bot_instructions = bot_md_path.read_text(encoding="utf-8-sig")
        except Exception:
            self._bot_instructions = ""

    # ----------------- 工具：Responses 輸出整理 -----------------
    def _format_response_text(self, response) -> str:
        """整理 Responses API 的輸出（文字 + 來源引用）。

        - 合併 `response.output` 內所有 message/output_text 為主文本。
        - 擷取 annotations：
            * web search: 類型為 `url_citation` → 以來源站名映射（TFC/Cofacts/MyGoPen/來源）
            * file search: 嘗試讀取 annotation 的 `filename` 或類型 `file_citation`

        Returns:
            已整理之最終輸出文字。
        """
        # 取主要文字
        text_chunks: List[str] = []
        for block in getattr(response, "output", []) or []:
            if getattr(block, "type", "") == "message":
                for c in getattr(block, "content", []) or []:
                    if getattr(c, "type", "") == "output_text":
                        text_chunks.append(getattr(c, "text", "") or "")
        main_text = "\n".join([t for t in text_chunks if t]).strip() or "（沒有內容輸出）"

        # ----------------------------------------------------------------------
        # 移除所有 Python 端的 citation 處理邏輯 (cites_web, cites_files)。
        # 根據 bot.md 的規範，模型 (LLM) 本身 "必須" 在 main_text 中自行產生
        # "行內" (inline) 的引用標註 (例如 [ TFC, 連結 ] 或 [ file_search ... ])。
        #
        # 現在 100% 交給 AI (bot.md) 處理格式。
        # ----------------------------------------------------------------------
        return main_text

    def _delete_file_safe(self, file_id: str) -> bool:
        """刪除單一 OpenAI File（失敗不拋例外）。"""
        try:
            self.client.files.delete(file_id)
            return True
        except Exception:
            return False

    # ----------------- 文字聊天（Web + File Search） -----------------
    def ask(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """處理純文字聊天：使用 Responses + web_search + file_search。

        策略：
        1) 使用 `bot.md` 作為系統規範（含站點限制等）。
        2) 啟用 `web_search`（官方 hosted tool）。  # noqa
        3) 同時啟用 `file_search`，向量庫 ID 由 retriever 提供（.env 或自動偵測最新）。  # noqa
        4) 將模型輸出中的 `annotations` 萃取為網址與檔案來源清單。

        Returns:
            dict：包含 `answer`（文字）與 `raw.response_id`。
        """
        self.memory.add(user_id, "user", user_message)

        # 僅使用 bot.md 作為系統提示詞，不再拼接任何內建規則或模板
        system_text = (self._bot_instructions or "")

        # ----------------------------------------------------------------------
        # 解決 Web Search 未觸發的問題。
        # bot.md 中的 "優先使用 file_search" 指令會讓模型偷懶 (找到即停止)。
        # 在程式碼中 "動態修正" 這個指令，強迫它 "同時" 使用兩種工具。
        # ----------------------------------------------------------------------
        system_text = system_text.replace("優先使用本地向量庫與上傳檔案（file_search）。", "必須同時使用「本地向量庫 (file_search)」和「網路檢索 (web_search)」來進行交叉查核。", 1)

        # 準備工具：web_search + file_search（若 retriever 有可用 vector stores）
        tools: List[Dict[str, Any]] = [{"type": "web_search"}]
        fs_tools = self.retriever.build_tools()
        if fs_tools:
            tools.extend(fs_tools)

        # 官方：Responses 直接傳 tools，API 會自動決定如何檢索與引用
        # - web_search: https://platform.openai.com/docs/guides/tools-web-search
        # - file_search: https://cookbook.openai.com/examples/file_search_responses
        response = self.client.responses.create(
            model=OPENAI_CHAT_MODEL,
            tools=tools,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_text}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            # 只把使用者輸入原封不動交給模型，其餘規範皆由 bot.md 決定
                            "text": user_message,
                        }
                    ],
                },
            ],
        )

        answer_text = self._format_response_text(response)

        # 若 retriever 沒有任何向量庫可用，補一段提示在 raw（不干擾主回答）
        raw = {"response_id": response.id}
        if not fs_tools:
            raw["file_search"] = "（檢索未啟用）目前沒有可用的 Vector Store。請在 .env 設定 OPENAI_VECTOR_STORE_IDS，或建立向量庫後再試。"

        self.memory.add(user_id, "assistant", answer_text)
        return {"answer": answer_text, "raw": raw}

    # ----------------- 附件聊天（沿用 Assistants，支援可檢索附件） -----------------
    async def ask_with_attachments(
        self, user_id: str, user_message: str, files: List[UploadFile]
    ) -> Dict[str, Any]:
        """處理文字 + 影像/文件上傳（暫沿用 Assistants 流程）。

        流程：
        - 將檔案上傳到 OpenAI Files（purpose="assistants"）
        - 可檢索文件以 `attachments=[{"file_id":..., "tools":[{"type":"file_search"}]}]` 掛入訊息
        - 交由既有 Assistant 執行（需在平台上已啟用 file_search）

        參考：Assistants + attachments（file_search）官方示例。  # noqa
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

            # 登記以便 /memory/clear 刪除
            self.memory.register_upload(user_id, file_id)

            # 分流：可檢索文件 vs 影像
            if ext in SEARCHABLE_DOCS:
                file_ids_for_search.append(file_id)
            if ext in IMAGE_LIKE:
                image_file_ids.append(file_id)

        # 準備 content blocks（避免空字串 text 觸發 400）
        content_blocks: List[Dict[str, Any]] = []
        if user_message and user_message.strip():
            content_blocks.append({"type": "text", "text": user_message.strip()})
        for fid in image_file_ids:
            content_blocks.append({"type": "image_file", "image_file": {"file_id": fid}})
        if text_snippets:
            merged = "\n\n".join([f"\n{txt}" for name, txt in text_snippets])
            content_blocks.append({"type": "text", "text": f"[以下為附檔文字內容]\n{merged}"})
        if not content_blocks:
            content_blocks.append({"type": "text", "text": "（內容見附件）"})

        # 可檢索附件（file_search）
        attachments = [{"file_id": fid, "tools": [{"type": "file_search"}]} for fid in file_ids_for_search]

        # 使用現有 Assistant（平台端須已啟 file_search，才能檢索 attachments）
        thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": content_blocks,
                    **({"attachments": attachments} if attachments else {}),
                }
            ]
        )
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=OPENAI_ASSISTANT_ID
        )

        # 等 run 完成
        start, status = time.time(), "queued"
        while time.time() - start < 120:
            r = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            status = r.status
            if status in ("completed", "failed", "cancelled", "expired"):
                break
            time.sleep(0.8)

        # 取回文字
        msgs = self.client.beta.threads.messages.list(thread_id=thread.id)
        answer_text = "（未取得模型回覆）"
        for m in reversed(getattr(msgs, "data", [])):
            if m.role == "assistant" and m.content:
                for c in m.content:
                    if hasattr(c, "text") and c.text and getattr(c.text, "value", ""):
                        answer_text = c.text.value
                        break

        self.memory.add(user_id, "assistant", answer_text)
        return {"answer": answer_text, "raw": {"thread_id": thread.id, "run_id": run.id, "status": status}}

    # ----------------- 檔案清理 -----------------
    def cleanup_user_uploads(self, user_id: str) -> Dict[str, Any]:
        """刪除某使用者於本服務期間上傳到 OpenAI Files 的所有檔案。"""
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