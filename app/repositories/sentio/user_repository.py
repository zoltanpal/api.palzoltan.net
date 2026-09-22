from functools import lru_cache
from typing import Any

from palzlib_db.db_client import DBClient

from app.repositories.sentio.sql import (
    CREATE_USER,
    CREATE_USER_WATCHLIST,
    DELETE_USER_WATCHLIST,
    GET_DB_USER,
    GET_ENTITY,
    USER_WATCHLISTS,
    SEARCH_ENTITY_BY_NAME,
)
from config import sentio_db_config


class UserRepository:
    def __init__(self, db_client: DBClient):
        self._db_client = db_client

    def get_db_user(self, uid: str) -> dict[str, Any] | None:
        with self._db_client.get_db_session() as session:
            row = session.execute(
                GET_DB_USER,
                {"firebase_uid": uid},
            ).mappings().one_or_none()

            return dict(row) if row is not None else None

    def get_entity(self, entity_id: int) -> dict[str, Any] | None:
        with self._db_client.get_db_session() as session:
            row = session.execute(
                GET_ENTITY,
                {"entity_id": entity_id},
            ).mappings().one_or_none()

            return dict(row) if row is not None else None

    def search_entity(self, query: str, limit: str = 10):
        with self._db_client.get_db_session() as session:
            rows = session.execute(SEARCH_ENTITY_BY_NAME, {
                "prefix": f"{query}%",
                "limit": limit
            }).mappings().all()


            return rows



    def create_user(self, user_obj: dict[str, Any]) -> dict[str, Any]:
        with self._db_client.get_db_session() as session:
            row = session.execute(
                CREATE_USER,
                {
                    "firebase_uid": user_obj["uid"],
                    "email": user_obj["email"],
                    "nickname": user_obj.get("name") or "",
                },
            ).mappings().one()

            user = dict(row)
            session.commit()

            return user

    def get_user_watchlist(self, user_id: int) -> list[dict[str, Any]]:
        with self._db_client.get_db_session() as session:
            rows = session.execute(
                USER_WATCHLISTS,
                {"user_id": user_id},
            ).mappings().all()

            return [dict(row) for row in rows]

    def add_watchlist_to_user(self, user_id: int, entity_id: int) -> bool:
        with self._db_client.get_db_session() as session:
            inserted_id = session.execute(
                CREATE_USER_WATCHLIST,
                {"user_id": user_id, "entity_id": entity_id},
            ).scalar_one_or_none()

            session.commit()

            return inserted_id is not None

    def remove_watchlist_from_user(self, user_id: int, entity_id: int) -> bool:
        with self._db_client.get_db_session() as session:
            deleted_id = session.execute(
                DELETE_USER_WATCHLIST,
                {"user_id": user_id, "entity_id": entity_id},
            ).scalar_one_or_none()

            session.commit()

            return deleted_id is not None


@lru_cache
def get_user_repository() -> UserRepository:
    return UserRepository(DBClient(db_config=sentio_db_config))