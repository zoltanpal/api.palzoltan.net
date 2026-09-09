from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from sqlalchemy.sql.elements import TextClause

from palzlib_db.db_client import DBClient

from app.repositories.sentio.validation_sql.clustering_validation import (
    CLUSTER_ACTIVITY_SQL,
    CLUSTER_ARTICLE_COUNT_MISMATCHES_SQL,
    CLUSTERING_INTEGRITY_SQL,
    CLUSTERING_QUEUE_AND_COVERAGE_SQL,
    RECENT_MULTI_ARTICLE_CLUSTERS_SQL,
    UNLABELED_MULTI_ARTICLE_CLUSTERS_SQL,
    UNMARKED_CLUSTERED_ARTICLES_SQL,
)
from app.repositories.sentio.validation_sql.entity_validation import (
    ENTITY_QUEUE_AND_COVERAGE_SQL,
    ENTITY_VALIDATION_SQL,
    INCOMPLETE_ENTITY_ARTICLES_SQL,
)
from app.repositories.sentio.validation_sql.health_check import (
    CURRENT_PIPELINE_QUEUE_SQL,
    HEALTH_CHECK_SQL,
)
from app.repositories.sentio.validation_sql.ingestion_cleanup_validation import (
    ARTICLES_PAST_RETENTION_GRACE_SQL,
    INGESTION_CLEANUP_VALIDATION_SQL,
    INGESTION_VOLUME_AND_SOURCE_STATUS_SQL,
    UNHEALTHY_ACTIVE_SOURCES_SQL,
)
from app.repositories.sentio.validation_sql.sentiment_validation import (
    INCOMPLETE_SENTIMENT_ARTICLES_SQL,
    SENTIMENT_VALIDATION_SQL,
    STATISTICS_LAST_24_HOURS_SQL,
)
from config import pow_live_db_config


SYSTEM_HEALTH_QUERIES = {
    "current_pipeline_queue": CURRENT_PIPELINE_QUEUE_SQL,
    "ingestion_activity": INGESTION_VOLUME_AND_SOURCE_STATUS_SQL,
    "system_validation": HEALTH_CHECK_SQL,
    "ingestion_cleanup_validation": INGESTION_CLEANUP_VALIDATION_SQL,
    "articles_past_retention_grace": ARTICLES_PAST_RETENTION_GRACE_SQL,
    "source_status_metadata": UNHEALTHY_ACTIVE_SOURCES_SQL,
}

SENTIMENT_QUERIES = {
    "last_24_hours": STATISTICS_LAST_24_HOURS_SQL,
    "validation": SENTIMENT_VALIDATION_SQL,
    "incomplete_articles": INCOMPLETE_SENTIMENT_ARTICLES_SQL,
}

ENTITY_QUERIES = {
    "queue_and_coverage": ENTITY_QUEUE_AND_COVERAGE_SQL,
    "validation": ENTITY_VALIDATION_SQL,
    "incomplete_articles": INCOMPLETE_ENTITY_ARTICLES_SQL,
}

CLUSTERING_QUERIES = {
    "queue_and_coverage": CLUSTERING_QUEUE_AND_COVERAGE_SQL,
    "activity": CLUSTER_ACTIVITY_SQL,
    "validation": CLUSTERING_INTEGRITY_SQL,
    "unmarked_articles": UNMARKED_CLUSTERED_ARTICLES_SQL,
    "unlabeled_multi_article_clusters": UNLABELED_MULTI_ARTICLE_CLUSTERS_SQL,
    "article_count_mismatches": CLUSTER_ARTICLE_COUNT_MISMATCHES_SQL,
    "recent_multi_article_clusters": RECENT_MULTI_ARTICLE_CLUSTERS_SQL,
}


QueryResults = dict[str, list[dict[str, Any]]]


class ValidationRepository:

    def __init__(self, db_client: DBClient):
        self._db_client = db_client

    def _fetch_query_results(self, queries: Mapping[str, TextClause]) -> QueryResults:
        with self._db_client.get_db_session() as db_session:
            return {
                name: [
                    dict(row)
                    for row in db_session.execute(query).mappings().all()
                ]
                for name, query in queries.items()
            }

    def get_system_health_data(self) -> QueryResults:
        return self._fetch_query_results(SYSTEM_HEALTH_QUERIES)

    def get_sentiment_data(self) -> QueryResults:
        return self._fetch_query_results(SENTIMENT_QUERIES)

    def get_entity_data(self) -> QueryResults:
        return self._fetch_query_results(ENTITY_QUERIES)

    def get_clustering_data(self) -> QueryResults:
        return self._fetch_query_results(CLUSTERING_QUERIES)


@lru_cache
def get_validation_repository() -> ValidationRepository:
    return ValidationRepository(DBClient(db_config=pow_live_db_config))