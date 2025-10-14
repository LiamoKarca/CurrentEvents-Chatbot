# -*- coding: utf-8 -*-
"""
對話記憶管理（單一使用者 Session 內的上下文）
- 預設用 in-memory dict；可替換為 Redis/DB。
- 另含「上傳檔案登記簿」：清除時可刪除使用者剛上傳到 OpenAI Files 的檔案。
"""
from typing import Dict, List, Tuple


class MemoryService:
    def __init__(self, max_turns: int = 12):
        # histories[user_id] = [(role, content), ...]，role ∈ {"user", "assistant"}
        self.histories: Dict[str, List[Tuple[str, str]]] = {}
        self.max_turns = max_turns
        # 追蹤使用者本次會話上傳過的 OpenAI Files 檔案 id
        self._uploads: Dict[str, List[str]] = {}

    def add(self, user_id: str, role: str, content: str) -> None:
        self.histories.setdefault(user_id, []).append((role, content))
        # 控制長度：只保留最後 N turns
        if len(self.histories[user_id]) > self.max_turns * 2:
            self.histories[user_id] = self.histories[user_id][-self.max_turns*2:]

    def get(self, user_id: str) -> List[Tuple[str, str]]:
        return self.histories.get(user_id, [])

    def clear(self, user_id: str) -> None:
        """清除單一使用者的歷史。"""
        if user_id in self.histories:
            del self.histories[user_id]
        # 不主動清 self._uploads，避免誤刪仍在使用的檔案
        # 刪檔由上層服務主動呼叫

    def clear_all(self) -> None:
        """⚠️ 清除全部使用者的歷史。"""
        self.histories.clear()

    def render_history(self, user_id: str) -> str:
        """將歷史記錄轉為簡單文字，供系統內部除錯或日後做摘要。"""
        hist = self.get(user_id)
        if not hist:
            return ""
        lines = []
        for role, content in hist:
            prefix = "使用者" if role == "user" else "系統回覆"
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)

    # ---------- 上傳檔案登記簿 ----------
    def register_upload(self, user_id: str, file_id: str) -> None:
        """在使用者上傳後，記錄該 OpenAI Files 的 file_id。"""
        if not file_id:
            return
        self._uploads.setdefault(user_id, [])
        if file_id not in self._uploads[user_id]:
            self._uploads[user_id].append(file_id)

    def pop_uploads(self, user_id: str) -> List[str]:
        """取出並移除使用者已登記的全部 file_id。"""
        return self._uploads.pop(user_id, [])

    def pop_all_uploads(self) -> Dict[str, List[str]]:
        """取出並清空所有使用者的 file_id 紀錄。"""
        all_ = self._uploads
        self._uploads = {}
        return all_
