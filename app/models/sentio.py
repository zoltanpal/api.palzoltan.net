from pydantic import BaseModel, Field
from enum import Enum

from typing import Any

class Intent(str, Enum):
    summary = "summary"
    reason = "reason"
    trend = "trend"
    comparison = "comparison"
    unknown = "unknown"


class SentimentLabel(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class SummaryLabel(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"
    mostly_positive = "mostly_positive"
    mostly_negative = "mostly_negative"
    mixed = "mixed"


class ParsedQuery(BaseModel):
    query: str | None
    window_hours: int = Field(6, ge=1, le=168)
    intent: Intent = Intent.unknown


class AvgSentimentResponse(BaseModel):
    score: float
    label: SentimentLabel


class DistributionResponse(BaseModel):
    positive_count: int
    neutral_count: int
    negative_count: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float


class SummaryResponse(BaseModel):
    label: SummaryLabel
    dominant_label: SentimentLabel
    dominant_pct: float


class AggregatedResponse(BaseModel):
    article_count: int
    avg_sentiment: AvgSentimentResponse
    distribution: DistributionResponse
    summary: SummaryResponse


class HeadlineResponse(BaseModel):
    id: int | str
    title: str
    title_hash: str | None = None
    summary: str | None = None
    link: str | None = None
    published_at: Any
    source_name: str
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    sentiment_raw: dict[str, Any] | str | None = None

class WhatDrivingResponse(BaseModel):
    article_count: int
    source_count: int
    avg_sentiment_score: float
    positive_count: int
    neutral_count: int
    negative_count: int
    dominant_sentiment: str
    representative_title: str
    representative_source: str
    representative_published_at: Any

class SentimentScoresPerHourResponse(BaseModel):
    bucket_start: Any
    article_count: int
    avg_sentiment_score: float | None = None
    positive_count: int | None = None
    neutral_count: int | None = None
    negative_count: int | None = None

class ChangeWindowResponse(BaseModel):
    article_count: int
    avg_sentiment_score: float


class SentimentChangeResponse(BaseModel):
    current: ChangeWindowResponse
    previous: ChangeWindowResponse
    delta: float
    direction: str


class DriversResponse(BaseModel):
    label: str | None = None
    is_meaningful: bool
    headlines: list[HeadlineResponse] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    query: str
    window_hours: int
    aggregated: AggregatedResponse
    headlines: list[HeadlineResponse] = Field(default_factory=list)
    change: SentimentChangeResponse | None = None
    what_driving: list[WhatDrivingResponse] = Field(default_factory=list)
    ai_summary: str | None = None
    drivers: DriversResponse | None = None
    sentiment_scores_per_hour: list[SentimentScoresPerHourResponse] = Field(default_factory=list)
    top_entities: list[dict[str, Any]] = Field(default_factory=list)


class PromptResponse(BaseModel):
    prompt: str
    query: str
    window_hours: int
    intent: Intent = Intent.unknown

class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    use_ai: bool = True

class QueryPromptRequest(BaseModel):
    query: str
    window_hours: int
    prompt: str | None = None
    use_ai: bool = True

class DetailedSourcesResponse(BaseModel):
    name: str
    site_url: str
    current_article_count: int
    category: str | None = None
    
    