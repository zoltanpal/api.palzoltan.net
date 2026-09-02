from app.models.sentio import ChangeDirection, SentimentLabel, SummaryLabel
from app.services.sentio.dashboard_service import (
    build_aggregated_response,
    build_sentiment_change,
    get_bucket_interval,
    normalize_window,
)


def test_build_aggregated_response_handles_empty_result() -> None:
    response = build_aggregated_response(
        {
            "total_articles": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "avg_sentiment_score": 0,
        }
    )

    assert response.article_count == 0
    assert response.avg_sentiment.label is SentimentLabel.NEUTRAL
    assert response.distribution.positive_pct == 0.0
    assert response.summary.label is SummaryLabel.NEUTRAL


def test_build_aggregated_response_classifies_strong_positive_coverage() -> None:
    response = build_aggregated_response(
        {
            "total_articles": 10,
            "positive_count": 8,
            "neutral_count": 1,
            "negative_count": 1,
            "avg_sentiment_score": 0.4,
        }
    )

    assert response.avg_sentiment.label is SentimentLabel.POSITIVE
    assert response.distribution.positive_pct == 80.0
    assert response.summary.label is SummaryLabel.POSITIVE


def test_sentiment_change_defaults_missing_previous_window_to_zero() -> None:
    change = build_sentiment_change(
        [{"window_name": "current", "article_count": 5, "avg_sentiment_score": -0.2}]
    )

    assert change.previous.article_count == 0
    assert change.delta == -0.2
    assert change.direction is ChangeDirection.WORSENING


def test_window_normalization_and_bucket_selection() -> None:
    assert normalize_window(-1) == 1
    assert normalize_window(999) == 168
    assert get_bucket_interval(12) == "30 minutes"
    assert get_bucket_interval(24) == "1 hour"
    assert get_bucket_interval(48) == "2 hours"
