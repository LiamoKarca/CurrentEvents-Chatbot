# -*- coding: utf-8-sig -*-
"""
File-based storage utilities for accounts and chat histories.

All files are stored under backend/data/account/.
- users.csv: username,password_hash,created_at
- per-user chat JSON: backend/data/account/{username}/chats/{chat_id}.json
- per-user chat index CSV: backend/data/account/{username}/chats_index.csv
"""

import csv
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

DATA_ROOT = os.path.join("backend", "data", "account")


def ensure_dirs(username: Optional[str] = None) -> None:
    """Ensure base directory and optional user subdirectories exist.

    Args:
        username: Username to ensure chat directory exists for.
    """
    os.makedirs(DATA_ROOT, exist_ok=True)
    if username:
        os.makedirs(os.path.join(DATA_ROOT, username, "chats"), exist_ok=True)


# ---------- Users (CSV) ----------

def users_csv_path() -> str:
    """Get users.csv path."""
    ensure_dirs()
    return os.path.join(DATA_ROOT, "users.csv")


def load_users() -> Dict[str, Dict[str, str]]:
    """Load all users from CSV.

    Returns:
        Dict keyed by username with fields: password_hash, created_at.
    """
    path = users_csv_path()
    if not os.path.exists(path):
        return {}
    users: Dict[str, Dict[str, str]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            users[row["username"]] = {
                "password_hash": row["password_hash"],
                "created_at": row.get("created_at", ""),
            }
    return users


def save_user(username: str, password_hash: str) -> None:
    """Append a new user to users.csv.

    Args:
        username: New username (must be unique).
        password_hash: Bcrypt hash.
    """
    path = users_csv_path()
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["username", "password_hash", "created_at"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "username": username,
                "password_hash": password_hash,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )


# ---------- Chats (per user) ----------

def chats_index_path(username: str) -> str:
    """Get per-user chats index CSV path."""
    ensure_dirs(username)
    return os.path.join(DATA_ROOT, username, "chats_index.csv")


def make_chat_id(dt: Optional[datetime] = None) -> Tuple[str, str]:
    """Create chat_id (yyyy-mm-dd-hhmmss) and title (YYYY年MM月DD日HH時MM分).

    Args:
        dt: Optional datetime; default now.

    Returns:
        (chat_id, title_str)
    """
    dt = dt or datetime.now()
    chat_id = dt.strftime("%Y-%m-%d-%H%M%S")
    title = dt.strftime("%Y年%m月%d日%H時%M分")
    return chat_id, title


def save_chat(username: str, messages: List[Dict], title: Optional[str] = None) -> Dict:
    """Save a chat JSON and append an index row.

    Args:
        username: Owner.
        messages: Whole conversation turns (e.g., [{'role':'user','content':'hi'}, ...]).
        title: Optional custom title; default to date-title.

    Returns:
        Metadata dict including chat_id, title, created_at, json_path.
    """
    ensure_dirs(username)
    now = datetime.now()
    chat_id, auto_title = make_chat_id(now)
    title = title or auto_title

    chat_json_path = os.path.join(DATA_ROOT, username, "chats", f"{chat_id}.json")
    payload = {
        "chat_id": chat_id,
        "username": username,
        "title": title,
        "created_at": now.isoformat(timespec="seconds"),
        "messages": messages,
    }
    with open(chat_json_path, "w", encoding="utf-8-sig") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # append index
    idx_path = chats_index_path(username)
    exists = os.path.exists(idx_path)
    with open(idx_path, "a", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["chat_id", "title", "created_at", "json_path"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "chat_id": chat_id,
                "title": title,
                "created_at": payload["created_at"],
                "json_path": chat_json_path,
            }
        )
    return payload


def list_chats(username: str) -> List[Dict]:
    """List chats for a user from index CSV (most recent first)."""
    idx_path = chats_index_path(username)
    if not os.path.exists(idx_path):
        return []
    rows: List[Dict] = []
    with open(idx_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


def load_chat(username: str, chat_id: str) -> Optional[Dict]:
    """Load chat JSON by id.

    Args:
        username: Owner.
        chat_id: Chat id (yyyy-mm-dd-hhmmss).

    Returns:
        JSON dict or None if not found.
    """
    json_path = os.path.join(DATA_ROOT, username, "chats", f"{chat_id}.json")
    if not os.path.exists(json_path):
        return None
    with open(json_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def _index_rows(username: str) -> List[Dict]:
    idx = chats_index_path(username)
    if not os.path.exists(idx):
        return []
    rows: List[Dict] = []
    with open(idx, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows

def _write_index(username: str, rows: List[Dict]) -> None:
    idx = chats_index_path(username)
    os.makedirs(os.path.dirname(idx), exist_ok=True)
    with open(idx, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["chat_id", "title", "created_at", "json_path"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def update_index_row_title(username: str, chat_id: str, new_title: Optional[str]) -> None:
    """更新 index 中某列的 title（若存在）。"""
    if not new_title:
        return
    rows = _index_rows(username)
    changed = False
    for r in rows:
        if r.get("chat_id") == chat_id:
            r["title"] = new_title
            changed = True
            break
    if changed:
        _write_index(username, rows)

def upsert_chat(username: str, messages: List[Dict], chat_id: Optional[str] = None,
                title: Optional[str] = None) -> Dict:
    """
    若帶 chat_id：覆寫/續寫同一檔（不新增 index 列）；
    未帶 chat_id：等同 save_chat() 新建一筆並追加 index。
    """
    ensure_dirs(username)
    if not chat_id:
        return save_chat(username=username, messages=messages, title=title)

    json_path = os.path.join(DATA_ROOT, username, "chats", f"{chat_id}.json")
    now_iso = datetime.now().isoformat(timespec="seconds")
    if os.path.exists(json_path):
        # 覆寫既有檔（保留 created_at；title 可選擇覆蓋）
        with open(json_path, "r", encoding="utf-8-sig") as f:
            payload = json.load(f)
        payload["messages"] = messages
        if title:
            payload["title"] = title
            update_index_row_title(username, chat_id, title)
        # 仍維持原 created_at；如需更新可自行調整
        with open(json_path, "w", encoding="utf-8-sig") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return payload
    else:
        # index 可能先有/先無。不存在檔案就當新建。
        meta = save_chat(username=username, messages=messages, title=title)
        # 但強制沿用呼叫者提供的 chat_id？除非你有業務需求，否則保留自動生成的 chat_id 較安全。
        return meta