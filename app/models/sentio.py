from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Intent(str, Enum):
    SUMMARY = "summary"
    REASON = "reason"
    TREND = "trend"
    COMPARISON = "comparison"
    UNKNOWN = "unknown"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SummaryLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MOSTLY_POSITIVE = "mostly_positive"
    MOSTLY_NEGATIVE = "mostly_negative"
    MIXED = "mixed"


class ChangeDirection(str, Enum):
    IMPROVING = "improving"
    WORSENING = "worsening"
    STABLE = "stable"


class ParsedQuery(BaseModel):
    query: str | None = None
    window_hours: int = Field(6, ge=1, le=168)
    intent: Intent = Intent.UNKNOWN


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
    published_at: datetime
    source_name: str
    sentiment_label: SentimentLabel | None = None
    sentiment_score: float | None = None
    sentiment_raw: dict[str, object] | str | None = None


class WhatDrivingResponse(BaseModel):
    article_count: int
    source_count: int
    avg_sentiment_score: float
    positive_count: int
    neutral_count: int
    negative_count: int
    dominant_sentiment: SentimentLabel
    representative_title: str
    representative_source: str
    representative_published_at: datetime


class SentimentScoresPerHourResponse(BaseModel):
    bucket_start: datetime
    article_count: int
    avg_sentiment_score: float | None = None
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0


class ChangeWindowResponse(BaseModel):
    article_count: int
    avg_sentiment_score: float


class SentimentChangeResponse(BaseModel):
    current: ChangeWindowResponse
    previous: ChangeWindowResponse
    delta: float
    direction: ChangeDirection


class DriversResponse(BaseModel):
    label: SentimentLabel | None = None
    is_meaningful: bool
    headlines: list[HeadlineResponse] = Field(default_factory=list)


class TopEntityResponse(BaseModel):
    entity_text: str
    entity_type: str
    article_count: int


class DashboardResponse(BaseModel):
    query: str
    window_hours: int
    aggregated: AggregatedResponse
    headlines: list[HeadlineResponse] = Field(default_factory=list)
    change: SentimentChangeResponse
    what_driving: list[WhatDrivingResponse] = Field(default_factory=list)
    top_entities: list[TopEntityResponse] = Field(default_factory=list)
    sentiment_scores_per_hour: list[SentimentScoresPerHourResponse] = Field(default_factory=list)
    drivers: DriversResponse | None = None
    ai_summary: str | None = None


class PromptResponse(BaseModel):
    prompt: str
    query: str
    window_hours: int
    intent: Intent = Intent.UNKNOWN


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2_000)

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prompt cannot be empty")
        return value


class QueryPromptRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    window_hours: int = Field(6, ge=1, le=168)
    prompt: str | None = Field(default=None, max_length=2_000)
    use_ai: bool = True

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query cannot be empty")
        return value

    @field_validator("prompt")
    @classmethod
    def strip_optional_prompt(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class DriversRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    window_hours: int = Field(6, ge=1, le=168)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query cannot be empty")
        return value


class DetailedSourcesResponse(BaseModel):
    name: str
    site_url: str
    current_article_count: int
    category: str | None = None
