from typing import Any

from palzlib_db.db_client import DBClient

from app.models.sentio import DetailedSourcesResponse, HeadlineResponse, SentimentScoresPerHourResponse
from app.repositories.sentio.queries import (
    AGGREGATED_QUERY,
    DRIVERS_QUERY,
    HEADLINES_QUERY,
    SENTIMENT_CHANGE_QUERY,
    SENTIMENT_SCORES_PER_HOUR_QUERY,
    DETAILED_SOURCES,
    WHAT_DRIVING
)
from config import pow_live_db_config


class SentioRepository:
    def __init__(self, db_client: DBClient):
        self.db_client = db_client

    def fetch_aggregated_row(self, query: str, window_hours: int) -> dict[str, Any]:
        with self.db_client.get_db_session() as session:
            row = session.execute(
                AGGREGATED_QUERY,
                {"query": query, "window_hours": window_hours},
            ).mappings().one()

        return dict(row)

    def fetch_headlines(self, query: str, window_hours: int) -> list[HeadlineResponse]:
        with self.db_client.get_db_session() as session:
            rows = session.execute(
                HEADLINES_QUERY,
                {"query": query, "window_hours": window_hours},
            ).mappings().all()

        return [HeadlineResponse(**dict(row)) for row in rows]

    def fetch_sentiment_change_rows(self, query: str, window_hours: int) -> list[dict[str, Any]]:
        with self.db_client.get_db_session() as session:
            rows = session.execute(
                SENTIMENT_CHANGE_QUERY,
                {"query": query, "window_hours": window_hours},
            ).mappings().all()

        return [dict(row) for row in rows]

    def fetch_drivers(
        self,
        query: str,
        window_hours: int,
        driver_label: str,
        limit: int,
    ) -> list[HeadlineResponse]:
        with self.db_client.get_db_session() as session:
            rows = session.execute(
                DRIVERS_QUERY,
                {
                    "query": query,
                    "window_hours": window_hours,
                    "driver_label": driver_label,
                    "limit": limit,
                },
            ).mappings().all()

        return [HeadlineResponse(**dict(row)) for row in rows]

    def fetch_sentiment_scores_per_hour(
        self,
        query: str,
        window_hours: int,
        bucket_interval: str = "1 hour",
    ) -> list[SentimentScoresPerHourResponse]:
        with self.db_client.get_db_session() as session:
            rows = session.execute(
                SENTIMENT_SCORES_PER_HOUR_QUERY,
                {
                    "query": query,
                    "window_hours": window_hours,
                    "bucket_interval": bucket_interval,
                },
            ).mappings().all()

        return [SentimentScoresPerHourResponse(**dict(row)) for row in rows]


    def fetch_detailed_sources(self) -> list[DetailedSourcesResponse]:
        with self.db_client.get_db_session() as session:
            rows = session.execute(DETAILED_SOURCES).mappings().all()

        return [DetailedSourcesResponse(**dict(row)) for row in rows]


    def fetch_what_driving(self, query: str, window_hours: int, limit: int) -> list[dict[str, Any]]:
        with self.db_client.get_db_session() as session:
            rows = session.execute(
                WHAT_DRIVING,
                {
                    "query": query,
                    "window_hours": window_hours,
                    "limit": limit,
                },
            ).mappings().all()
        return [dict(row) for row in rows]


sentio_repository = SentioRepository(DBClient(db_config=pow_live_db_config))
