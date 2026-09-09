from typing import Any

from app.repositories.sentio.validation_repository import ValidationRepository


ValidationResponse = dict[str, Any]


class ValidationService:

    def __init__(self, repository: ValidationRepository):
        self._repository = repository

    def system_health(self) -> ValidationResponse:
        data = self._repository.get_system_health_data()

        return {
            "overview": {
                "current_pipeline_queue": data["current_pipeline_queue"],
                "ingestion_activity": data["ingestion_activity"],
            },
            "validation": {
                "system": data["system_validation"],
                "ingestion_cleanup": data["ingestion_cleanup_validation"],
            },
            "issues": {
                "articles_past_retention_grace": data["articles_past_retention_grace"],
            },
            "source_metadata": {
                "sources_without_success_metadata": data["source_status_metadata"],
            },
        }

    def sentiment(self) -> ValidationResponse:
        data = self._repository.get_sentiment_data()

        return {
            "overview": {
                "last_24_hours": data["last_24_hours"],
            },
            "validation": data["validation"],
            "issues": {
                "incomplete_articles": data["incomplete_articles"],
            },
        }

    def entity(self) -> ValidationResponse:
        data = self._repository.get_entity_data()

        return {
            "overview": {
                "queue_and_coverage": data["queue_and_coverage"],
            },
            "validation": data["validation"],
            "issues": {
                "incomplete_articles": data["incomplete_articles"],
            },
        }

    def clustering(self) -> ValidationResponse:
        data = self._repository.get_clustering_data()

        return {
            "overview": {
                "queue_and_coverage": data["queue_and_coverage"],
                "activity": data["activity"],
            },
            "validation": data["validation"],
            "issues": {
                "unmarked_articles": data["unmarked_articles"],
                "unlabeled_multi_article_clusters": data["unlabeled_multi_article_clusters"],
                "article_count_mismatches": data["article_count_mismatches"],
            },
            "inspection": {
                "recent_multi_article_clusters": data["recent_multi_article_clusters"],
            },
        }