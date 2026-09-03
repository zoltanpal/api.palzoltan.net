from app.repositories.sentio.validation_repository import ValidationRepository


class ValidationService:
    def __init__(self, repository: ValidationRepository):
        self._repository = repository

    def global_health_check(self) -> list:
        return self._repository.global_health_check()

    def sentiment_validation_check(self) -> dict:
        return self._repository.sentiment_validation_check()

    def entity_validation_check(self) -> dict:
        return self._repository.entity_validation_check()

    def clustering_validation_check(self) -> dict:
        return self._repository.clustering_validation_check()

    def ingestion_cleanup_validation_check(self) -> dict:
        return self._repository.ingestion_cleanup_validation_check()
