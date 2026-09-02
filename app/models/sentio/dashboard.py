from datetime import datetime

from pydantic import BaseModel, Field

from app.models.sentio.enums import ChangeDirection, SentimentLabel, SummaryLabel


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


class DriverHeadlineResponse(BaseModel):
    article_id: int | str
    title: str
    source: str
    published_at: datetime
    sentiment_label: SentimentLabel
    sentiment_score: float | None = None


class DriverResponse(BaseModel):
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
    headlines: list[DriverHeadlineResponse]


class WhatDrivingResponse(BaseModel):
    main_reason: str
    drivers: list[DriverResponse]


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


class TopEntityResponse(BaseModel):
    entity_text: str
    entity_type: str
    article_count: int


class DashboardResponse(BaseModel):
    query: str
    window_hours: int
    ai_summary: str | None = None
    aggregated: AggregatedResponse
    change: SentimentChangeResponse
    what_driving: WhatDrivingResponse | None
    top_entities: list[TopEntityResponse] = Field(default_factory=list)
    headlines: list[HeadlineResponse] = Field(default_factory=list)
    sentiment_scores_per_hour: list[SentimentScoresPerHourResponse] = Field(default_factory=list)
