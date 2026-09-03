from functools import lru_cache

from requests import session

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
    RECENT_ENTITY_TYPE_DISTRIBUTION_SQL,
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
    RECENT_RESULT_DISTRIBUTION_SQL,
    SENTIMENT_VALIDATION_SQL,
    STATISTICS_LAST_24_HOURS_SQL,
)
from config import pow_live_db_config


class ValidationRepository:

    def __init__(self, db_client: DBClient):
        self._db_client = db_client


    def _fetch_validation_results(self, queries: dict[str, str]):
        with self._db_client.get_db_session() as session:
            return {
                name: [dict(row) for row in session.execute(query).mappings().all()]
                for name, query in queries.items()
            }



    def global_health_check(self) -> dict:
        queries = {
            "health_check": HEALTH_CHECK_SQL,
            "current_pipeline_queue": CURRENT_PIPELINE_QUEUE_SQL,
        }

        return self._fetch_validation_results(queries=queries)


    def sentiment_validation_check(self) -> dict:
        queries = {
            "sentiment_validation": SENTIMENT_VALIDATION_SQL,
            "statistics_last_24_hours": STATISTICS_LAST_24_HOURS_SQL,
            # "recent_sentiment_distribution": RECENT_RESULT_DISTRIBUTION_SQL,
            "incomplete_sentiment_articles": INCOMPLETE_SENTIMENT_ARTICLES_SQL,
        }

        return self._fetch_validation_results(queries=queries)


    def entity_validation_check(self) -> dict:
        queries = {
            "entity_validation": ENTITY_VALIDATION_SQL,
            "entity_queue_and_coverage": ENTITY_QUEUE_AND_COVERAGE_SQL,
            # "recent_entity_type_distribution": RECENT_ENTITY_TYPE_DISTRIBUTION_SQL,
            "incomplete_entity_articles": INCOMPLETE_ENTITY_ARTICLES_SQL,
        }

        return self._fetch_validation_results(queries=queries)
    

    def clustering_validation_check(self) -> dict:
        queries = {
            "clustering_queue_and_coverage": CLUSTERING_QUEUE_AND_COVERAGE_SQL,
            "cluster_activity": CLUSTER_ACTIVITY_SQL,
            "clustering_integrity": CLUSTERING_INTEGRITY_SQL,
            "unmarked_clustered_articles": UNMARKED_CLUSTERED_ARTICLES_SQL,
            "unlabeled_multi_article_clusters": UNLABELED_MULTI_ARTICLE_CLUSTERS_SQL,
            "cluster_article_count_mismatches": CLUSTER_ARTICLE_COUNT_MISMATCHES_SQL,
            "recent_multi_article_clusters": RECENT_MULTI_ARTICLE_CLUSTERS_SQL,
        }

        return self._fetch_validation_results(queries=queries)
    

    def ingestion_cleanup_validation_check(self) -> dict:
        queries = {
            "ingestion_cleanup_validation": INGESTION_CLEANUP_VALIDATION_SQL,
            "ingestion_volume_and_source_status": INGESTION_VOLUME_AND_SOURCE_STATUS_SQL,
            "unhealthy_active_sources": UNHEALTHY_ACTIVE_SOURCES_SQL,
            "articles_past_retention_grace": ARTICLES_PAST_RETENTION_GRACE_SQL,
        }

        return self._fetch_validation_results(queries=queries)
        


@lru_cache
def get_validation_repository() -> ValidationRepository:
    return ValidationRepository(DBClient(db_config=pow_live_db_config))
