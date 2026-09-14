from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping
from nltk.corpus import stopwords
from datetime import datetime, timedelta

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
    PREVIOUS_DRIVERS_QUERY,
)
from config import pow_live_db_config

stop_words = list(stopwords.words('english'))
stop_words.extend([
    "$100"
])
        

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

            # All the headlines
            headlines = self._headline_models(
                session.execute(
                    HEADLINES_QUERY, {**params, "limit": headline_limit}
                ).mappings().all()
            )

            # Changes
            change_rows = [
                dict(row)
                for row in session.execute(SENTIMENT_CHANGE_QUERY, params).mappings().all()
            ]

            # Collect What's driving data
            what_driving_rows = session.execute(
                WHAT_DRIVING_QUERY, {**params, "limit": driver_limit}
            ).mappings().all()

            cluster_ids = [row["cluster_id"] for row in what_driving_rows]

            what_driving_prev = self.fetch_what_driving_prev(
                query=query,
                cluster_ids=cluster_ids,
                window_hours=window_hours,
            )
            what_driving = self.what_driving_models(what_driving_rows, what_driving_prev)

            # Fetch top entities of the time period
            top_entities = self._top_entity_models(
                session.execute(
                    TOP_ENTITIES_QUERY, {**params, "limit": entity_limit, "stop_words": stop_words}
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


    def fetch_top_entities_dashboard_data(
        self, window_hours: int, max_top_entities: int, 
        excluded_entity_types: list[str]
    ) -> list[TopEntityResponse]:

        with self._db_client.get_db_session() as session:
            rows = session.execute(
                TOP_ENTITIES_QUERY,
                { 
                    "window_hours": window_hours, 
                    "excluded_entity_types": excluded_entity_types,
                    "limit": max_top_entities,
                    "stop_words": stop_words
                },
            ).mappings().all()
        return self._top_entity_models(rows)

    def fetch_what_driving_prev(
        self, *, query: str, cluster_ids: list[int], window_hours: int
    ) -> dict:
        if not cluster_ids:
            return {}

        with self._db_client.get_db_session() as session:
            current_from = datetime.now() - timedelta(hours=window_hours)

            previous_to = current_from
            previous_from = current_from - timedelta(hours=window_hours)

            rows = session.execute(
                PREVIOUS_DRIVERS_QUERY, {
                    "current_driver_ids": cluster_ids,
                    "previous_from": previous_from,
                    "previous_to": previous_to,
                    "query": query
                }
            ).mappings().all()

        if rows:
            return {row["cluster_id"]: dict(row) for row in rows}

        return {}

    @staticmethod
    def _headline_models(rows: list[Mapping[str, Any]]) -> list[HeadlineResponse]:
        return [HeadlineResponse(**dict(row)) for row in rows]


    # @staticmethod
    def what_driving_models(
        self,
        rows: list[Mapping[str, Any]],
        previous: dict[int, Mapping[str, Any]],
    ) -> WhatDrivingResponse | None:
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
            driver_data.pop("driver_label", None)

            prev = previous.get(row["cluster_id"], {})

            driver_data["comparison"] = {
                "status": self._calculate_driver_status(
                    current_article_count=driver_data["article_count"],
                    previous_article_count=prev.get("previous_article_count", 0),
                ),
                "previous_article_count": prev.get("previous_article_count", 0),
                "previous_source_count": prev.get("previous_source_count", 0),
            }

            drivers.append(DriverResponse(**driver_data))

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

    @staticmethod
    def _calculate_driver_status(current_article_count: int, previous_article_count: int) -> str | None:
        if (
            previous_article_count == 0
            and current_article_count >= 2
        ):
            return "new"

        # Require both a relative and absolute increase.
        if (
            previous_article_count > 0
            and current_article_count >= previous_article_count + 2
            and current_article_count >= previous_article_count * 1.5
        ):
            return "gaining"

        return ""


@lru_cache
def get_sentio_repository() -> SentioRepository:
    return SentioRepository(DBClient(db_config=pow_live_db_config))
