# -*- coding: utf-8-sig -*-
"""
Firestore-based storage helpers for user accounts and chat histories.

Replaces the previous CSV/file-based implementation with Cloud Firestore so the
backend can run statelessly across instances.

Collection layout:
- /user-account/{username}/chats/{chat_id}
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from firebase_admin import firestore

from .firebase_client import get_firestore_client

# Firestore 路徑：/user-account/{username}/chats/{chat_id}
_ROOT_COLLECTION = "user-account"


def _account_collection():
    return get_firestore_client().collection(_ROOT_COLLECTION)


def _user_doc(username: str):
    username = username.strip()
    if not username:
        raise ValueError("username is required")
    return _account_collection().document(username)


def _chats_collection(username: str):
    return _user_doc(username).collection("chats")


def get_user(username: str) -> Optional[Dict[str, str]]:
    """Fetch a single user document."""
    snap = _user_doc(username).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["username"] = username
    return data


def create_user(username: str, password_hash: str) -> Dict[str, str]:
    """Create a Firestore user document."""
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    payload = {
        "username": username,
        "password_hash": password_hash,
        "created_at": now_iso,
    }
    _user_doc(username).set(payload, merge=False)
    return payload


def make_chat_id(dt: Optional[datetime] = None) -> tuple[str, str]:
    dt = dt or datetime.utcnow()
    chat_id = dt.strftime("%Y-%m-%d-%H%M%S")
    title = dt.strftime("%Y年%m月%d日%H時%M分")
    return chat_id, title


def save_chat(username: str, messages: List[Dict], title: Optional[str] = None) -> Dict:
    """Create a new chat doc for the user."""
    now = datetime.utcnow()
    chat_id, auto_title = make_chat_id(now)
    title = title or auto_title
    payload = {
        "chat_id": chat_id,
        "username": username,
        "title": title,
        "created_at": now.isoformat(timespec="seconds"),
        "created_at_epoch": now.timestamp(),
        "messages": messages,
    }
    _chats_collection(username).document(chat_id).set(payload)
    return payload


def upsert_chat(
    username: str,
    messages: List[Dict],
    chat_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict:
    """Insert or update a chat record."""
    if not chat_id:
        return save_chat(username, messages, title)

    doc_ref = _chats_collection(username).document(chat_id)
    snap = doc_ref.get()
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    if snap.exists:
        data = snap.to_dict() or {}
        data["messages"] = messages
        if title:
            data["title"] = title
        data["updated_at"] = now_iso
        doc_ref.set(data, merge=False)
        return data

    # Document missing → fallback to creating a fresh chat_id
    return save_chat(username, messages, title)


def list_chats(username: str) -> List[Dict]:
    """Return chat summaries sorted by creation time (desc)."""
    coll = _chats_collection(username)
    query = coll.order_by("created_at_epoch", direction=firestore.Query.DESCENDING)
    rows: List[Dict] = []
    for snap in query.stream():
        data = snap.to_dict() or {}
        rows.append(
            {
                "chat_id": data.get("chat_id", snap.id),
                "title": data.get("title", ""),
                "created_at": data.get("created_at", ""),
            }
        )
    return rows


def load_chat(username: str, chat_id: str) -> Optional[Dict]:
    """Load a chat document including all messages."""
    snap = _chats_collection(username).document(chat_id).get()
    if not snap.exists:
        return None
    return snap.to_dict()


def delete_chat(username: str, chat_id: str) -> Dict[str, object]:
    """Delete a chat document."""
    doc_ref = _chats_collection(username).document(chat_id)
    snap = doc_ref.get()
    if not snap.exists:
        return {
            "username": username,
            "chat_id": chat_id,
            "deleted": False,
            "doc_path": doc_ref.path,
        }
    doc_ref.delete()
    return {
        "username": username,
        "chat_id": chat_id,
        "deleted": True,
        "doc_path": doc_ref.path,
    }


__all__ = [
    "create_user",
    "get_user",
    "save_chat",
    "upsert_chat",
    "list_chats",
    "load_chat",
    "delete_chat",
    "make_chat_id",
]
