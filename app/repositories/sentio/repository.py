from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

from palzlib_db.db_client import DBClient

from app.models.sentio import (
    DetailedSourceResponse,
    DriverResponse,
    HeadlineResponse,
    SentimentScoresPerHourResponse,
    TopEntityResponse,
    WhatDrivingResponse,
)
from app.repositories.sentio.sql import (
    AGGREGATED_QUERY,
    DETAILED_SOURCES_QUERY,
    HEADLINES_QUERY,
    SENTIMENT_CHANGE_QUERY,
    SENTIMENT_SCORES_PER_HOUR_QUERY,
    TOP_ENTITIES_QUERY,
    WHAT_DRIVING_QUERY,
)
from config import pow_live_db_config


@dataclass(frozen=True)
class DashboardData:
    aggregated: Mapping[str, Any]
    headlines: list[HeadlineResponse]
    sentiment_change_rows: list[Mapping[str, Any]]
    what_driving: WhatDrivingResponse | None
    top_entities: list[TopEntityResponse]
    sentiment_scores_per_hour: list[SentimentScoresPerHourResponse]


class SentioRepository:
    def __init__(self, db_client: DBClient):
        self._db_client = db_client

    def fetch_dashboard_data(
        self,
        *,
        query: str,
        window_hours: int,
        headline_limit: int,
        entity_limit: int,
        driver_limit: int,
        bucket_interval: str,
    ) -> DashboardData:
        params = {"query": query, "window_hours": window_hours}
        with self._db_client.get_db_session() as session:
            aggregated = dict(session.execute(AGGREGATED_QUERY, params).mappings().one())
            headlines = self._headline_models(
                session.execute(
                    HEADLINES_QUERY, {**params, "limit": headline_limit}
                ).mappings().all()
            )
            change_rows = [
                dict(row)
                for row in session.execute(SENTIMENT_CHANGE_QUERY, params).mappings().all()
            ]
            what_driving = self._what_driving_models(
                session.execute(
                    WHAT_DRIVING_QUERY, {**params, "limit": driver_limit}
                ).mappings().all()
            )
            top_entities = self._top_entity_models(
                session.execute(
                    TOP_ENTITIES_QUERY, {**params, "limit": entity_limit}
                ).mappings().all()
            )
            scores = self._score_models(
                session.execute(
                    SENTIMENT_SCORES_PER_HOUR_QUERY,
                    {**params, "bucket_interval": bucket_interval},
                ).mappings().all()
            )

        return DashboardData(
            aggregated=aggregated,
            headlines=headlines,
            sentiment_change_rows=change_rows,
            what_driving=what_driving,
            top_entities=top_entities,
            sentiment_scores_per_hour=scores,
        )

    def fetch_what_driving(
        self, *, query: str, window_hours: int, limit: int
    ) -> WhatDrivingResponse | None:
        with self._db_client.get_db_session() as session:
            rows = session.execute(
                WHAT_DRIVING_QUERY,
                {"query": query, "window_hours": window_hours, "limit": limit},
            ).mappings().all()

        return self._what_driving_models(rows)

    def fetch_detailed_sources(self) -> list[DetailedSourceResponse]:
        with self._db_client.get_db_session() as session:
            rows = session.execute(DETAILED_SOURCES_QUERY).mappings().all()
        return [DetailedSourceResponse(**dict(row)) for row in rows]

    @staticmethod
    def _headline_models(rows: list[Mapping[str, Any]]) -> list[HeadlineResponse]:
        return [HeadlineResponse(**dict(row)) for row in rows]

    @staticmethod
    def _what_driving_models(rows: list[Mapping[str, Any]]) -> WhatDrivingResponse | None:
        if not rows:
            return None

        first_row = rows[0]

        main_reason = (
            first_row.get("driver_label")
            or first_row.get("representative_title")
        )

        drivers = []
        for row in rows:
            driver_data = dict(row)
            driver_data.pop("driver_label", "")
            drivers.append(
                DriverResponse(**driver_data)
            )

        return WhatDrivingResponse(
            main_reason=main_reason,
            drivers=drivers,
        )

    @staticmethod
    def _top_entity_models(rows: list[Mapping[str, Any]]) -> list[TopEntityResponse]:
        return [TopEntityResponse(**dict(row)) for row in rows]

    @staticmethod
    def _score_models(rows: list[Mapping[str, Any]]) -> list[SentimentScoresPerHourResponse]:
        return [SentimentScoresPerHourResponse(**dict(row)) for row in rows]


@lru_cache
def get_sentio_repository() -> SentioRepository:
    return SentioRepository(DBClient(db_config=pow_live_db_config))
