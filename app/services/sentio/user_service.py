from typing import Any

from app.repositories.sentio.user_repository import UserRepository
from app.services.sentio.exceptions import (
    EntityNotFoundError,
    UserNotFoundError,
)


class UserService:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return self._repository.create_user(user_obj=user)

    def check_user_entity(func):
        def wrapper():
            pass

        return wrapper


    def search_entity(self, query: str, limit: int = 10):
        if len(query) > 2:
            result = self._repository.search_entity(query, limit)
            return result


    def create_user_watchlist(
        self,
        user_obj: dict[str, Any],
        entity_id: int,
    ) -> dict[str, Any]:
        user = self._repository.get_db_user(user_obj["uid"])
        if user is None:
            raise UserNotFoundError()

        entity = self._repository.get_entity(entity_id)
        if entity is None:
            raise EntityNotFoundError()

        created = self._repository.add_watchlist_to_user(
            user_id=user["id"],
            entity_id=entity_id,
        )

        return {
            "entity_id": entity_id,
            "created": created,
        }

    def user_watchlist(self, user_obj: dict[str, Any]):
        user = self._repository.get_db_user(user_obj["uid"])
        if user is None:
            raise UserNotFoundError()

        return self._repository.get_user_watchlist(user_id=user["id"])


    def remove_user_watchlist(self, user_obj: dict, entity_id: int):
        user = self._repository.get_db_user(user_obj["uid"])
        if user is None:
            raise UserNotFoundError()

        entity = self._repository.get_entity(entity_id)
        if entity is None:
            raise EntityNotFoundError()

        deleted = self._repository.remove_watchlist_from_user(
            user_id=user["id"],
            entity_id=entity_id
            )

        return {
            "entity_id": entity_id,
            "deleted": deleted
        }