# -*- coding: utf-8-sig -*-
"""
Chat Deletion Service (File-based)

職責:
    - 依帳號與 chat_id 刪除對應 JSON 檔案
    - 自該使用者的 chats_index.csv 移除對應列
    - 回傳刪除動作的結果與相關後設資料

設計原則:
    - SoC / SRP：僅處理「檔案層刪除」與「索引清理」，不碰驗證/路由。
    - 無副作用 API：所有路徑來自 file_store 的集中定義，利於維護。

相依:
    - backend/src/app/services/file_store.py

注意:
    - 不直接拋出 HTTP 相關錯誤，交由路由層決策。
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Optional, Tuple

# 與既有檔案儲存工具對齊
from .file_store import DATA_ROOT, chats_index_path, ensure_dirs


def _safe_remove(path: str) -> bool:
    """Safely remove a file path.

    Args:
        path: Absolute or relative file path.

    Returns:
        True if a file existed and was removed; False if file absent.
    """
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except OSError:
        # 權限或 I/O 錯誤時，保守回傳 False，由上層決策是否回報
        return False


def _read_index(idx_path: str) -> List[Dict[str, str]]:
    """Read chats_index.csv into a list of dict rows.

    Args:
        idx_path: Index CSV path.

    Returns:
        List of rows (可能為空).
    """
    if not os.path.exists(idx_path):
        return []
    rows: List[Dict[str, str]] = []
    with open(idx_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _write_index(idx_path: str, rows: List[Dict[str, str]]) -> None:
    """Rewrite chats_index.csv with given rows.

    Args:
        idx_path: Index CSV path.
        rows: Rows to write back (已過濾欲刪除項目).
    """
    os.makedirs(os.path.dirname(idx_path), exist_ok=True)
    fieldnames = ["chat_id", "title", "created_at", "json_path"]
    with open(idx_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "chat_id": r.get("chat_id", ""),
                    "title": r.get("title", ""),
                    "created_at": r.get("created_at", ""),
                    "json_path": r.get("json_path", ""),
                }
            )


def _locate_json_path(username: str, chat_id: str) -> Tuple[str, bool]:
    """從 index 嘗試找出 json_path；若缺少，回退至預設路徑推斷。

    Args:
        username: 帳號
        chat_id: 會話 ID（yyyy-mm-dd-hhmmss）

    Returns:
        (json_path, inferred)
        - json_path: 目標 JSON 路徑（存在與否不保證）
        - inferred: True 表示為推斷路徑（index 無該列）
    """
    idx_path = chats_index_path(username)
    rows = _read_index(idx_path)
    for r in rows:
        if r.get("chat_id") == chat_id:
            jp = r.get("json_path", "")
            if jp:
                return jp, False

    # 兼容：index 缺失時，用慣例推斷
    inferred = os.path.join(DATA_ROOT, username, "chats", f"{chat_id}.json")
    return inferred, True


def delete_chat(username: str, chat_id: str) -> Dict[str, object]:
    """刪除指定帳號的聊天記錄（JSON + 索引列）。

    Args:
        username: 擁有者帳號
        chat_id: 會話 ID（yyyy-mm-dd-hhmmss）

    Returns:
        結果字典:
            {
                "username": <str>,
                "chat_id": <str>,
                "json_removed": <bool>,
                "index_removed": <bool>,
                "json_path": <str>,
                "index_path": <str>,
                "existed_in_index": <bool>,
                "remaining_count": <int>
            }
    """
    ensure_dirs(username)
    idx_path = chats_index_path(username)

    # 1) 找 JSON 檔路徑
    json_path, inferred = _locate_json_path(username, chat_id)

    # 2) 刪除 JSON 檔（存在才刪）
    json_removed = _safe_remove(json_path)

    # 3) 清理 index
    existed_in_index = False
    index_removed = False
    rows = _read_index(idx_path)
    if rows:
        new_rows: List[Dict[str, str]] = []
        for r in rows:
            if r.get("chat_id") == chat_id:
                existed_in_index = True
                index_removed = True  # 標記為將移除
                continue
            new_rows.append(r)
        _write_index(idx_path, new_rows)
        remaining = len(new_rows)
    else:
        remaining = 0

    return {
        "username": username,
        "chat_id": chat_id,
        "json_removed": json_removed,
        "index_removed": index_removed,
        "json_path": json_path,
        "index_path": idx_path,
        "existed_in_index": existed_in_index and not inferred,
        "remaining_count": remaining,
    }
