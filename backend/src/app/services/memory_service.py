# -*- coding: utf-8 -*-
"""
對話記憶管理（單一使用者 Session 內的上下文）
- 預設使用 in-memory dict；可替換為 Redis/DB。
- 提供「渲染為提示文字」的工具，避免 tokens 爆炸（可做截斷）。
"""
from typing import Dict, List, Tuple


class MemoryService:
    def __init__(self, max_turns: int = 12):
        # histories[user_id] = [(role, content), ...]，role ∈ {"user", "assistant"}
        self.histories: Dict[str, List[Tuple[str, str]]] = {}
        self.max_turns = max_turns

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

    def clear_all(self) -> None:
        """⚠️ 清除全部使用者的歷史。"""
        self.histories.clear()

    def render_history(self, user_id: str) -> str:
        """
        將歷史記錄轉為可讀的對話文字區塊，讓 Responses API 一次讀取。
        如需更緊湊，可改為摘要（另建 summarize() 流程）。
        """
        hist = self.get(user_id)
        if not hist:
            return ""
        lines = []
        for role, content in hist:
            prefix = "使用者" if role == "user" else "系統回覆"
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)
