
# -*- coding: utf-8 -*-
"""
OpenAI API 客戶端包裝
- 使用新版 Python SDK: `from openai import OpenAI`
- 主要提供：取得單例 client、健康檢查。
"""
import os
from typing import Optional
from openai import OpenAI

_client_singleton: Optional[OpenAI] = None

def get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    return _client_singleton
