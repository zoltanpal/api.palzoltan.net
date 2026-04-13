from app.models.sentio import (
    AggregatedResponse,
    AvgSentimentResponse,
    ChangeWindowResponse,
    DistributionResponse,
    DriversResponse,
    HeadlineResponse,
    LiveQueryResponse,
    SentimentChangeResponse,
    SentimentLabel,
    SummaryLabel,
    SummaryResponse,
)
from app.repositories.sentio.repository import sentio_repository

MIN_WINDOW_HOURS = 1
MAX_WINDOW_HOURS = 168
DEFAULT_WINDOW_HOURS = 6
POSITIVE_SENTIMENT_THRESHOLD = 0.05
NEGATIVE_SENTIMENT_THRESHOLD = -0.05
MIXED_SENTIMENT_THRESHOLD = 0.10
MAX_DRIVER_HEADLINES = 5


def normalize_window(window_hours: int) -> int:
    return max(MIN_WINDOW_HOURS, min(window_hours, MAX_WINDOW_HOURS))


def get_score_label(avg_score: float) -> SentimentLabel:
    if avg_score >= POSITIVE_SENTIMENT_THRESHOLD:
        return SentimentLabel.positive
    if avg_score <= NEGATIVE_SENTIMENT_THRESHOLD:
        return SentimentLabel.negative
    return SentimentLabel.neutral


def get_summary(
    avg_score: float,
    positive_pct: float,
    neutral_pct: float,
    negative_pct: float,
) -> SummaryResponse:
    distribution = {
        SentimentLabel.positive: positive_pct,
        SentimentLabel.neutral: neutral_pct,
        SentimentLabel.negative: negative_pct,
    }
    dominant_label = max(distribution, key=distribution.get)
    dominant_pct = distribution[dominant_label]

    if (
        dominant_label == SentimentLabel.positive
        and dominant_pct >= 70
        and avg_score >= POSITIVE_SENTIMENT_THRESHOLD
    ):
        summary_label = SummaryLabel.positive
    elif (
        dominant_label == SentimentLabel.negative
        and dominant_pct >= 70
        and avg_score <= NEGATIVE_SENTIMENT_THRESHOLD
    ):
        summary_label = SummaryLabel.negative
    elif dominant_label == SentimentLabel.positive and dominant_pct >= 55:
        summary_label = SummaryLabel.mostly_positive
    elif dominant_label == SentimentLabel.negative and dominant_pct >= 55:
        summary_label = SummaryLabel.mostly_negative
    elif neutral_pct >= 60 and abs(avg_score) < POSITIVE_SENTIMENT_THRESHOLD:
        summary_label = SummaryLabel.neutral
    elif positive_pct >= 30 and negative_pct >= 30 and abs(avg_score) < MIXED_SENTIMENT_THRESHOLD:
        summary_label = SummaryLabel.mixed
    elif avg_score >= POSITIVE_SENTIMENT_THRESHOLD:
        summary_label = SummaryLabel.mostly_positive
    elif avg_score <= NEGATIVE_SENTIMENT_THRESHOLD:
        summary_label = SummaryLabel.mostly_negative
    else:
        summary_label = SummaryLabel.neutral

    return SummaryResponse(
        label=summary_label,
        dominant_label=dominant_label,
        dominant_pct=round(dominant_pct, 2),
    )


def fetch_aggregated(query: str, window_hours: int) -> AggregatedResponse:
    row = sentio_repository.fetch_aggregated_row(query, window_hours)

    total_articles = row["total_articles"] or 0
    positive_count = row["positive_count"] or 0
    neutral_count = row["neutral_count"] or 0
    negative_count = row["negative_count"] or 0
    avg_sentiment_score = float(row["avg_sentiment_score"] or 0)

    if total_articles:
        positive_pct = round((positive_count / total_articles) * 100, 2)
        neutral_pct = round((neutral_count / total_articles) * 100, 2)
        negative_pct = round((negative_count / total_articles) * 100, 2)
    else:
        positive_pct = neutral_pct = negative_pct = 0.0

    return AggregatedResponse(
        article_count=total_articles,
        avg_sentiment=AvgSentimentResponse(
            score=round(avg_sentiment_score, 4),
            label=get_score_label(avg_sentiment_score),
        ),
        distribution=DistributionResponse(
            positive_count=positive_count,
            neutral_count=neutral_count,
            negative_count=negative_count,
            positive_pct=positive_pct,
            neutral_pct=neutral_pct,
            negative_pct=negative_pct,
        ),
        summary=get_summary(
            avg_score=avg_sentiment_score,
            positive_pct=positive_pct,
            neutral_pct=neutral_pct,
            negative_pct=negative_pct,
        ),
    )


def fetch_headlines(query: str, window_hours: int) -> list[HeadlineResponse]:
    return sentio_repository.fetch_headlines(query, window_hours)


def fetch_sentiment_change(query: str, window_hours: int) -> SentimentChangeResponse:
    rows = sentio_repository.fetch_sentiment_change_rows(query, window_hours)

    current = {"article_count": 0, "avg_sentiment_score": 0.0}
    previous = {"article_count": 0, "avg_sentiment_score": 0.0}

    for row in rows:
        payload = {
            "article_count": row["article_count"] or 0,
            "avg_sentiment_score": float(row["avg_sentiment_score"] or 0),
        }
        if row["window_name"] == "current":
            current = payload
        elif row["window_name"] == "previous":
            previous = payload

    delta = current["avg_sentiment_score"] - previous["avg_sentiment_score"]

    if delta > POSITIVE_SENTIMENT_THRESHOLD:
        direction = "improving"
    elif delta < NEGATIVE_SENTIMENT_THRESHOLD:
        direction = "worsening"
    else:
        direction = "stable"

    return SentimentChangeResponse(
        current=ChangeWindowResponse(**current),
        previous=ChangeWindowResponse(**previous),
        delta=round(delta, 4),
        direction=direction,
    )


def is_meaningful_change(change: SentimentChangeResponse) -> bool:
    abs_delta = abs(change.delta)
    article_count = change.current.article_count

    return (abs_delta >= 0.10 and article_count >= 3) or (
        abs_delta >= 0.07 and article_count >= 5
    )


def get_driver_label(change: SentimentChangeResponse) -> str | None:
    if change.direction == "worsening":
        return "negative"
    if change.direction == "improving":
        return "positive"
    return None


def fetch_drivers(
    query: str,
    window_hours: int,
    driver_label: str,
    limit: int = MAX_DRIVER_HEADLINES,
) -> list[HeadlineResponse]:
    return sentio_repository.fetch_drivers(
        query=query,
        window_hours=window_hours,
        driver_label=driver_label,
        limit=limit,
    )


def get_bucket_interval(window_hours: int) -> str:
    if window_hours <= 12:
        return "30 minutes"
    if window_hours >= 48:
        return "2 hours"
    return "1 hour"


def build_live_query_response(
    query: str,
    window_hours: int,
    use_ai: bool,
    prompt: str | None = None,
) -> LiveQueryResponse:
    from app.services.sentio.summarizer import summarize_headlines_with_ai

    normalized_query = query.strip()
    normalized_window = normalize_window(window_hours)

    aggregated = fetch_aggregated(normalized_query, normalized_window)
    headlines = fetch_headlines(normalized_query, normalized_window)
    change = fetch_sentiment_change(normalized_query, normalized_window)

    drivers_payload: DriversResponse | None = None
    driver_label = None

    if is_meaningful_change(change):
        driver_label = get_driver_label(change)
        drivers = []
        if driver_label:
            drivers = fetch_drivers(
                query=normalized_query,
                window_hours=normalized_window,
                driver_label=driver_label,
            )

        drivers_payload = DriversResponse(
            label=driver_label,
            is_meaningful=True,
            headlines=drivers,
        )

    ai_summary = None
    if use_ai and headlines:
        ai_summary = summarize_headlines_with_ai(
            query=normalized_query,
            prompt=prompt,
            window_hours=normalized_window,
            headlines=[headline.title for headline in headlines],
        )

    sentiment_scores_per_hour = sentio_repository.fetch_sentiment_scores_per_hour(
        query=normalized_query,
        window_hours=normalized_window,
        bucket_interval=get_bucket_interval(normalized_window),
    )

    return LiveQueryResponse(
        query=normalized_query,
        window_hours=normalized_window,
        aggregated=aggregated,
        headlines=headlines,
        change=change,
        ai_summary=ai_summary,
        drivers=drivers_payload,
        sentiment_scores_per_hour=sentiment_scores_per_hour,
    )
