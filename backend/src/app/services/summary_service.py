"""
Hot events summary service.

This module fetches trending news from configurable RSS feeds and lets an LLM
compose short Traditional Chinese summaries for "今日摘要"與"本週摘要".
"""
from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Literal, Optional
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from openai import OpenAI

from ..llm.openai_client import get_openai_client

logger = logging.getLogger(__name__)

SummaryRange = Literal["daily", "weekly"]


def _clean_text(value: Optional[str]) -> str:
    """Remove HTML tags + unescape entities."""
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _pick_child_text(node: ET.Element, name: str) -> str:
    """Return text of child tag w/ optional namespace support."""
    for child in list(node):
        tag = child.tag
        if tag.endswith(name):
            return _clean_text(child.text)
    return ""


@dataclass
class SummaryItem:
    id: str
    title: str
    link: str
    source: Optional[str]
    published_at: Optional[str]
    snippet: str
    llm_summary: Optional[str] = None


class SummaryService:
    """
    Fetch RSS headlines then ask the OpenAI Responses API for concise recaps.
    """

    DEFAULT_DAILY_RSS = os.getenv(
        "SUMMARY_DAILY_RSS",
        "https://news.google.com/rss/headlines/section/topic/WORLD?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    )
    DEFAULT_WEEKLY_RSS = os.getenv(
        "SUMMARY_WEEKLY_RSS",
        "https://news.google.com/rss/search?q=when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    )

    def __init__(
        self,
        *,
        max_items: int = 3,
        http_timeout: int = 10,
        cache_seconds: Optional[int] = None,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None,
    ) -> None:
        self.max_items = max_items
        self.http_timeout = http_timeout
        self.cache_seconds = cache_seconds if cache_seconds is not None else int(
            os.getenv("SUMMARY_CACHE_SECONDS", "0") or "0"
        )
        self._feeds: Dict[SummaryRange, str] = {
            "daily": self.DEFAULT_DAILY_RSS,
            "weekly": self.DEFAULT_WEEKLY_RSS,
        }
        self._model = model or os.getenv("SUMMARY_MODEL") or os.getenv(
            "OPENAI_CHAT_MODEL", "gpt-4o-mini"
        )
        self._client = client
        self._cache: Dict[str, Dict[str, object]] = {}

    # ---------------------- public APIs ---------------------- #
    def get_highlights(
        self, range_type: SummaryRange = "daily", limit: Optional[int] = None
    ) -> Dict[str, object]:
        rng = range_type if range_type in self._feeds else "daily"
        limit = limit or self.max_items
        cache_key = f"{rng}:{limit}"

        cached = self._cache.get(cache_key)
        if cached and self._cache_valid(cached):
            return cached["data"]  # type: ignore[return-value]

        url = self._feeds[rng]
        articles = self._fetch_feed(url, limit * 2)
        if not articles:
            raise RuntimeError("無法取得熱門事件，請稍後再試")

        selected = articles[:limit]
        enriched = self._summarize_events(selected, rng)
        overview = self._build_overview(enriched, rng)
        payload = {
            "range": rng,
            "generated_at": datetime.utcnow()
            .replace(tzinfo=timezone.utc)
            .isoformat(),
            "overview": overview,
            "items": [item.__dict__ for item in enriched],
        }
        if self.cache_seconds > 0:
            self._cache[cache_key] = {"ts": time.time(), "data": payload}
        return payload

    # ---------------------- feed helpers --------------------- #
    def _fetch_feed(self, url: str, limit: int) -> List[SummaryItem]:
        try:
            headers = {"User-Agent": "CurrentEventsBot/1.0"}
            req = Request(url, headers=headers)
            context = ssl.create_default_context()
            with urlopen(req, timeout=self.http_timeout, context=context) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                content = resp.read().decode(charset, errors="ignore")
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.warning("Failed to download RSS feed: %s", exc)
            return []

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            logger.warning("RSS parse error: %s", exc)
            return []

        items: List[SummaryItem] = []
        for item in root.findall(".//item"):
            title = _clean_text(item.findtext("title"))
            link = _clean_text(item.findtext("link"))
            source = _pick_child_text(item, "source")
            snippet = _clean_text(item.findtext("description"))

            pub_text = item.findtext("pubDate")
            published_at = None
            if pub_text:
                try:
                    dt = parsedate_to_datetime(pub_text)
                    if dt and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt:
                        published_at = dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    published_at = None

            digest_basis = (title or "") + (link or "")
            digest = hashlib.md5(digest_basis.encode("utf-8", errors="ignore")).hexdigest()
            items.append(
                SummaryItem(
                    id=digest,
                    title=title or "(無標題)",
                    link=link,
                    source=source or None,
                    published_at=published_at,
                    snippet=snippet,
                )
            )
            if len(items) >= limit:
                break
        return items

    # ---------------------- LLM helpers ---------------------- #
    def _summarize_events(
        self, items: List[SummaryItem], range_type: SummaryRange
    ) -> List[SummaryItem]:
        enriched: List[SummaryItem] = []
        for idx, item in enumerate(items, start=1):
            summary = self._summarize_single(item, range_type, idx)
            item.llm_summary = summary
            enriched.append(item)
        return enriched

    def _summarize_single(
        self, item: SummaryItem, range_type: SummaryRange, seq: int
    ) -> str:
        textual = (
            f"標題：{item.title}\n"
            f"來源：{item.source or '未知'}\n"
            f"時間：{item.published_at or '未知'}\n"
            f"連結：{item.link or '無'}\n"
            f"內容：{item.snippet or '（無描述）'}\n"
        )
        system_text = (
            "你是一位科技新聞編輯，請使用繁體中文，以精煉語氣整理事件亮點。"
        )
        task = "今日" if range_type == "daily" else "本週"
        user_text = (
            f"這是第 {seq} 則{task}熱門事件資訊，請濃縮成 2 句內的摘要，"
            "點出衝擊或趨勢，並保留專有名詞：\n"
            f"{textual}"
        )
        try:
            return self._call_llm(system_text, user_text)
        except Exception as exc:
            logger.warning("LLM summary failed (%s), fallback to snippet", exc)
            return item.snippet[:120] or item.title

    def _build_overview(self, items: List[SummaryItem], range_type: SummaryRange) -> str:
        joined = "\n".join(
            f"- {item.title}：{item.llm_summary or item.snippet}" for item in items
        )
        system_text = (
            "你是總編輯，需用繁體中文為讀者寫一段背景介紹，"
            "語氣平衡且專業。"
        )
        user_text = (
            f"請根據以下{ '今日' if range_type == 'daily' else '本週'}焦點，"
            "寫 50-80 字的綜覽段落，凸顯三件事的共通趨勢或影響：\n"
            f"{joined}"
        )
        try:
            return self._call_llm(system_text, user_text)
        except Exception as exc:
            logger.warning("LLM overview failed (%s), fallback text", exc)
            return f"{'今日' if range_type == 'daily' else '本週'}焦點： " + "; ".join(
                item.title for item in items
            )

    def _call_llm(self, system_text: str, user_text: str) -> str:
        client = self._client or get_openai_client()
        response = client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_text}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_text}],
                },
            ],
        )
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response) -> str:
        """Extract plain text from Responses output."""
        parts: List[str] = []
        for block in getattr(response, "output", []) or []:
            if getattr(block, "type", "") != "message":
                continue
            for piece in getattr(block, "content", []) or []:
                if getattr(piece, "type", "") == "output_text":
                    text = getattr(piece, "text", "")
                    if text:
                        parts.append(text)
        text = "\n".join(parts).strip()
        if not text:
            raise RuntimeError("LLM 無回覆內容")
        return text

    # ---------------------- cache helpers -------------------- #
    def _cache_valid(self, entry: Dict[str, object]) -> bool:
        if self.cache_seconds <= 0:
            return False
        ts = entry.get("ts")
        if not isinstance(ts, (int, float)):
            return False
        return (time.time() - ts) < self.cache_seconds

