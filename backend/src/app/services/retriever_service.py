"""
檢索服務（基於 OpenAI Vector Store 的 file_search 工具）
- 若未設定 OPENAI_VECTOR_STORE_IDS，將自動偵測最新（created_at 最大）的向量庫，作為預設使用。
- 仍保留以環境變數指定多個向量庫 ID 的能力（逗號分隔）。
- 對新版/舊版 Python SDK 皆做相容處理（client.vector_stores.list 與 client.beta.vector_stores.list）。
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from openai import OpenAI
from ..llm.openai_client import get_openai_client


def _safe_list_vector_stores(client: OpenAI, limit: int = 50):
    """
    嘗試以新版路徑列出向量庫；若失敗則降級到 beta 路徑。
    回傳 (items, used_beta_api: bool)
      - items: 可迭代之 vector store 物件（需能取 id 與 created_at）
    """
    # 新版（正式）API
    try:
        page = client.vector_stores.list(limit=limit)  # 型別：OpenAIObjectPage
        items = getattr(page, "data", None) or page  # 保守取用
        if items:
            return items, False
    except Exception:
        pass

    # 舊版（beta）API
    try:
        beta_root = getattr(client, "beta", None)
        if beta_root is None:
            return [], True
        vs = getattr(beta_root, "vector_stores", None)
        if vs is None:
            return [], True
        page = vs.list(limit=limit)
        items = getattr(page, "data", None) or page
        return items or [], True
    except Exception:
        return [], True


def _pick_latest_vector_store(client: OpenAI) -> Optional[str]:
    """
    取用最新建立（created_at 最大）的向量庫 ID。
    若拿不到任何向量庫，回傳 None。
    """
    items, _used_beta = _safe_list_vector_stores(client, limit=100)
    if not items:
        return None

    def _extract_created_at(obj) -> float:
        # 多版本相容：created_at 可能是秒級 epoch、或 None
        ts = getattr(obj, "created_at", None)
        if ts is None:
            # 某些物件可能沒有 created_at；採最小值處理
            return float("-inf")
        try:
            # 若為 datetime 轉 epoch；若為 int/float 直接回傳
            if isinstance(ts, datetime):
                return ts.timestamp()
            return float(ts)
        except Exception:
            return float("-inf")

    # 以 created_at 降冪排序，取第一個
    items_sorted = sorted(items, key=_extract_created_at, reverse=True)
    latest = items_sorted[0] if items_sorted else None
    latest_id = getattr(latest, "id", None)
    return latest_id


class RetrieverService:
    def __init__(self, vector_store_ids: Optional[List[str]] = None, max_results: Optional[int] = 5):
        """
        :param vector_store_ids: 指定要使用的 vector store IDs；若為 None 則會以環境變數或自動偵測。
        :param max_results: file_search 的 max_num_results。
        """
        env_ids = []
        if vector_store_ids is None:
            env_val = os.getenv("OPENAI_VECTOR_STORE_IDS", "").strip()
            if env_val:
                env_ids = [x for x in (env_val.split(
                    ",") if env_val else []) if x]
        self._explicit_ids = vector_store_ids or env_ids  # 使用者/環境直接指定的 IDs
        self.max_results = max_results

        # 延後初始化：僅在第一次 build_tools 時才會實際探測最新向量庫
        self._auto_latest_id: Optional[str] = None

    def _ensure_latest_if_needed(self) -> None:
        """
        若未提供任何 ID，會呼叫 OpenAI API 列出向量庫並挑選最新的一個。
        """
        if self._explicit_ids:
            return  # 已指定，不需自動偵測
        if self._auto_latest_id:
            return  # 已偵測過

        client = get_openai_client()
        latest_id = _pick_latest_vector_store(client)
        if latest_id:
            self._auto_latest_id = latest_id
        else:
            # 找不到任何向量庫，維持 None；由上層決定是否照無檢索工具運作
            self._auto_latest_id = None

    def get_active_vector_store_ids(self) -> List[str]:
        """
        回傳最終要使用的 vector_store_ids。
        優先順序：顯式指定（參數/環境） > 自動偵測最新
        """
        self._ensure_latest_if_needed()
        if self._explicit_ids:
            return self._explicit_ids
        return [self._auto_latest_id] if self._auto_latest_id else []

    def build_tools(self) -> List[Dict[str, Any]]:
        """
        依據目前可用的 vector_store_ids 組出 Responses API 的 file_search 工具設定。
        若無可用 ID，回傳空清單（代表不啟用檢索）。
        """
        vector_ids = self.get_active_vector_store_ids()
        if not vector_ids:
            return []

        tool: Dict[str, Any] = {
            "type": "file_search",
            "vector_store_ids": vector_ids,
        }
        if self.max_results:
            tool["max_num_results"] = self.max_results
        return [tool]
