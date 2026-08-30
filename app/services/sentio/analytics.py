import logging
from collections.abc import Callable, Mapping
from typing import Any

from app.models.sentio import (
    AggregatedResponse,
    AvgSentimentResponse,
    ChangeDirection,
    ChangeWindowResponse,
    DashboardResponse,
    DistributionResponse,
    DriversResponse,
    # HeadlineResponse,
    SentimentChangeResponse,
    SentimentLabel,
    SummaryLabel,
    SummaryResponse,
    WhatDrivingResponse,
)
from app.repositories.sentio.repository import SentioRepository

logger = logging.getLogger(__name__)

MIN_WINDOW_HOURS = 1
MAX_WINDOW_HOURS = 168
DEFAULT_WINDOW_HOURS = 6
POSITIVE_SENTIMENT_THRESHOLD = 0.05
NEGATIVE_SENTIMENT_THRESHOLD = -0.05
MIXED_SENTIMENT_THRESHOLD = 0.10
MAX_HEADLINES = 30
MAX_DRIVER_HEADLINES = 5
MAX_TOP_ENTITIES = 5

SummaryProvider = Callable[[str, int, list[str], str | None], str | None]


def normalize_window(window_hours: int) -> int:
    return max(MIN_WINDOW_HOURS, min(window_hours, MAX_WINDOW_HOURS))


def get_score_label(avg_score: float) -> SentimentLabel:
    if avg_score >= POSITIVE_SENTIMENT_THRESHOLD:
        return SentimentLabel.POSITIVE
    if avg_score <= NEGATIVE_SENTIMENT_THRESHOLD:
        return SentimentLabel.NEGATIVE
    return SentimentLabel.NEUTRAL


def get_summary(
    *, avg_score: float, positive_pct: float, neutral_pct: float, negative_pct: float
) -> SummaryResponse:
    distribution = {
        SentimentLabel.POSITIVE: positive_pct,
        SentimentLabel.NEUTRAL: neutral_pct,
        SentimentLabel.NEGATIVE: negative_pct,
    }
    dominant_label = max(distribution, key=distribution.__getitem__)
    dominant_pct = distribution[dominant_label]

    if dominant_label is SentimentLabel.POSITIVE and dominant_pct >= 70 and avg_score >= 0.05:
        label = SummaryLabel.POSITIVE
    elif dominant_label is SentimentLabel.NEGATIVE and dominant_pct >= 70 and avg_score <= -0.05:
        label = SummaryLabel.NEGATIVE
    elif dominant_label is SentimentLabel.POSITIVE and dominant_pct >= 55:
        label = SummaryLabel.MOSTLY_POSITIVE
    elif dominant_label is SentimentLabel.NEGATIVE and dominant_pct >= 55:
        label = SummaryLabel.MOSTLY_NEGATIVE
    elif neutral_pct >= 60 and abs(avg_score) < POSITIVE_SENTIMENT_THRESHOLD:
        label = SummaryLabel.NEUTRAL
    elif positive_pct >= 30 and negative_pct >= 30 and abs(avg_score) < MIXED_SENTIMENT_THRESHOLD:
        label = SummaryLabel.MIXED
    elif avg_score >= POSITIVE_SENTIMENT_THRESHOLD:
        label = SummaryLabel.MOSTLY_POSITIVE
    elif avg_score <= NEGATIVE_SENTIMENT_THRESHOLD:
        label = SummaryLabel.MOSTLY_NEGATIVE
    else:
        label = SummaryLabel.NEUTRAL

    return SummaryResponse(
        label=label,
        dominant_label=dominant_label,
        dominant_pct=round(dominant_pct, 2),
    )


def build_aggregated_response(row: Mapping[str, Any]) -> AggregatedResponse:
    total = int(row["total_articles"] or 0)
    counts = {
        "positive": int(row["positive_count"] or 0),
        "neutral": int(row["neutral_count"] or 0),
        "negative": int(row["negative_count"] or 0),
    }
    score = float(row["avg_sentiment_score"] or 0)
    percentages = {
        label: round((count / total) * 100, 2) if total else 0.0
        for label, count in counts.items()
    }
    return AggregatedResponse(
        article_count=total,
        avg_sentiment=AvgSentimentResponse(score=round(score, 4), label=get_score_label(score)),
        distribution=DistributionResponse(
            positive_count=counts["positive"],
            neutral_count=counts["neutral"],
            negative_count=counts["negative"],
            positive_pct=percentages["positive"],
            neutral_pct=percentages["neutral"],
            negative_pct=percentages["negative"],
        ),
        summary=get_summary(
            avg_score=score,
            positive_pct=percentages["positive"],
            neutral_pct=percentages["neutral"],
            negative_pct=percentages["negative"],
        ),
    )


def build_sentiment_change(rows: list[Mapping[str, Any]]) -> SentimentChangeResponse:
    windows = {
        "current": {"article_count": 0, "avg_sentiment_score": 0.0},
        "previous": {"article_count": 0, "avg_sentiment_score": 0.0},
    }
    for row in rows:
        window_name = row["window_name"]
        if window_name in windows:
            windows[window_name] = {
                "article_count": int(row["article_count"] or 0),
                "avg_sentiment_score": float(row["avg_sentiment_score"] or 0),
            }

    delta = windows["current"]["avg_sentiment_score"] - windows["previous"]["avg_sentiment_score"]
    direction = (
        ChangeDirection.IMPROVING
        if delta > POSITIVE_SENTIMENT_THRESHOLD
        else ChangeDirection.WORSENING
        if delta < NEGATIVE_SENTIMENT_THRESHOLD
        else ChangeDirection.STABLE
    )
    return SentimentChangeResponse(
        current=ChangeWindowResponse(**windows["current"]),
        previous=ChangeWindowResponse(**windows["previous"]),
        delta=round(delta, 4),
        direction=direction,
    )


def is_meaningful_change(change: SentimentChangeResponse) -> bool:
    return (abs(change.delta) >= 0.10 and change.current.article_count >= 3) or (
        abs(change.delta) >= 0.07 and change.current.article_count >= 5
    )


def get_bucket_interval(window_hours: int) -> str:
    return "30 minutes" if window_hours <= 12 else "2 hours" if window_hours >= 48 else "1 hour"


class SentioDashboardService:
    def __init__(
        self,
        repository: SentioRepository,
        summary_provider: SummaryProvider | None = None,
    ):
        self._repository = repository
        self._summary_provider = summary_provider

    def build_dashboard(
        self, *, query: str, window_hours: int, use_ai: bool, prompt: str | None = None
    ) -> DashboardResponse:
        normalized_query = query.strip()
        normalized_window = normalize_window(window_hours)
        data = self._repository.fetch_dashboard_data(
            query=normalized_query,
            window_hours=normalized_window,
            headline_limit=MAX_HEADLINES,
            entity_limit=MAX_TOP_ENTITIES,
            driver_limit=MAX_DRIVER_HEADLINES,
            bucket_interval=get_bucket_interval(normalized_window),
        )
        change = build_sentiment_change(data.sentiment_change_rows)
        # drivers = self._build_drivers(normalized_query, normalized_window, change)
        ai_summary = (
            self._summarize(
                query=normalized_query,
                window_hours=normalized_window,
                drivers=data.what_driving,
                prompt=prompt,
            )
            if use_ai
            else None
        )
        return DashboardResponse(
            query=normalized_query,
            window_hours=normalized_window,
            aggregated=build_aggregated_response(data.aggregated),
            headlines=data.headlines,
            change=change,
            what_driving=data.what_driving,
            top_entities=data.top_entities,
            sentiment_scores_per_hour=data.sentiment_scores_per_hour,
            # drivers=drivers, this doesn't need anymore and the what_driving will be drivers
            ai_summary=ai_summary,
        )

    def build_drivers(self, *, query: str, window_hours: int) -> WhatDrivingResponse:
        return self._repository.fetch_what_driving(
            query=query.strip(),
            window_hours=normalize_window(window_hours),
            limit=MAX_DRIVER_HEADLINES,
        )

    def _build_drivers(
        self, query: str, window_hours: int, change: SentimentChangeResponse
    ) -> DriversResponse | None:
        if not is_meaningful_change(change):
            return None
        label = (
            SentimentLabel.POSITIVE if change.direction is ChangeDirection.IMPROVING
            else SentimentLabel.NEGATIVE if change.direction is ChangeDirection.WORSENING else None
        )
        headlines = self._repository.fetch_drivers(
            query=query, window_hours=window_hours, label=label.value, limit=MAX_DRIVER_HEADLINES
        ) if label else []
        return DriversResponse(label=label, is_meaningful=True, headlines=headlines)

    def _summarize(
        self,
        *,
        query: str,
        window_hours: int,
        drivers: list,
        prompt,
    ) -> str | None:
        if not drivers or self._summary_provider is None:
            return None
        try:
            return self._summary_provider(
                query,
                window_hours,
                drivers,
                prompt,
            )
        except Exception:
            logger.exception("Sentio AI summary failed")
            return None
