from collections.abc import Mapping
from functools import lru_cache
from typing import Any
from palzlib_db.db_client import DBClient
from sqlalchemy.sql.elements import TextClause
from config import depth_atlas_db_config


from app.repositories.depth_atlas.sql import (
    GET_DATASETS
)


QueryResults = dict[str, list[dict[str, Any]]]

class DepthAtlasRepository:
    def __init__(self, db_client: DBClient):
        self._db_client = db_client


    def _fetch_query_results(self, query: str) -> QueryResults:
        with self._db_client.get_db_session() as db_session:
            return [
                    dict(row)
                    for row in db_session.execute(query).mappings().all()
            ]

    def get_datasets(self) -> QueryResults:
        return self._fetch_query_results(GET_DATASETS)

@lru_cache
def get_validation_repository() -> DepthAtlasRepository:
    return DepthAtlasRepository(DBClient(db_config=depth_atlas_db_config))