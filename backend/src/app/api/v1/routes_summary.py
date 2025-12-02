from typing import List, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ...services.summary_service import SummaryService

router = APIRouter()

summary_service = SummaryService()


class SummaryCard(BaseModel):
    id: str
    title: str
    link: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    snippet: Optional[str] = None
    llm_summary: Optional[str] = Field(
        default=None, description="LLM produced short recap for the event."
    )


class HighlightsResponse(BaseModel):
    range: Literal["daily", "weekly"]
    generated_at: str
    overview: str
    items: List[SummaryCard]


@router.get("/highlights", response_model=HighlightsResponse)
def get_hot_events(
    range_type: Literal["daily", "weekly"] = Query("daily", alias="range"),
    limit: int = Query(3, ge=1, le=6),
):
    """
    提供「今日 / 本週摘要」：預設回傳三則熱門事件卡片。
    """
    return summary_service.get_highlights(range_type=range_type, limit=limit)
