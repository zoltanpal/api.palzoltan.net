from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from fastapi import APIRouter, Depends
from palzlib_db.db_client import DBClient
from palzlib_db.db_mapper import DBMapper
from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased
from starlette.responses import JSONResponse

from app.utils.api_factory import APIFactory
from app.utils.auth.bearer_token import BearerAuth
from app.utils.reponses import NOT_FOUND
from config import time_travelers_db_config

# -----------------------------
# DB / Models
# -----------------------------
db_client = DBClient(db_config=time_travelers_db_config)


@dataclass(frozen=True)
class TimeTravellersModels:
    persons: Any
    trips: Any
    trip_persons: Any
    dates: Any
    movies: Any
    devices: Any
    departure_dates: Any
    arrival_dates: Any


@lru_cache(maxsize=1)
def get_models() -> TimeTravellersModels:
    """Reflect the schema only when a Time Travellers endpoint is requested."""
    db_mapping = DBMapper(db_client=db_client)
    dates = db_mapping.get_model("dates")
    return TimeTravellersModels(
        persons=db_mapping.get_model("persons"),
        trips=db_mapping.get_model("trips"),
        trip_persons=db_mapping.get_model("trip_persons"),
        dates=dates,
        movies=db_mapping.get_model("movies"),
        devices=db_mapping.get_model("devices"),
        departure_dates=aliased(dates),
        arrival_dates=aliased(dates),
    )


router = APIRouter(
    prefix="/time_travellers",
    tags=["time_travellers"],
    dependencies=[Depends(BearerAuth())],
)


# -----------------------------
# Helpers
# -----------------------------
def not_found() -> JSONResponse:
    return JSONResponse(status_code=HTTPStatus.NOT_FOUND, content=NOT_FOUND.to_http_exception())


def trips_select_columns(models: TimeTravellersModels) -> Tuple[Any, ...]:
    """
    Central place for trips "DTO" columns so we don't duplicate.
    """
    trips = models.trips
    departure_dates = models.departure_dates
    arrival_dates = models.arrival_dates
    movies = models.movies
    devices = models.devices
    return (
        trips.id.label("trip_id"),
        departure_dates.id.label("departure_date_id"),
        departure_dates.date.label("departure_date"),
        departure_dates.time.label("departure_time"),
        arrival_dates.id.label("arrival_date_id"),
        arrival_dates.date.label("arrival_date"),
        arrival_dates.time.label("arrival_time"),
        movies.title.label("movie_title"),
        movies.original_title.label("movie_original_title"),
        movies.released.label("movie_released"),
        movies.imdb_url.label("movie_imdb_url"),
        movies.plot.label("movie_plot"),
        devices.name.label("timejump_device_name"),
        devices.description.label("timejump_device_description"),
        devices.more_info.label("timejump_device_link"),
        trips.memo,
    )


def base_trips_query(
    session: Session,
    models: TimeTravellersModels,
    where: Optional[Any] = None,
):
    trips = models.trips
    departure_dates = models.departure_dates
    arrival_dates = models.arrival_dates
    devices = models.devices
    movies = models.movies
    query = (
        session.query(*trips_select_columns(models))
        .join(departure_dates, departure_dates.id == trips.departure_date_id, isouter=True)
        .join(arrival_dates, arrival_dates.id == trips.arrival_date_id, isouter=True)
        .join(devices, devices.id == trips.device_id, isouter=True)
        .join(movies, movies.id == trips.movie_id, isouter=True)
    )
    if where is not None:
        query = query.filter(where)
    return query


def fetch_trip_persons_map(
    session: Session,
    models: TimeTravellersModels,
    trip_ids: Sequence[Union[int, str]],
) -> Dict[Union[int, str], List[Any]]:
    """
    Fetch all persons for all trips in one query, and group them by trip_id.
    """
    if not trip_ids:
        return {}

    trip_persons = models.trip_persons
    persons = models.persons
    rows = (
        session.query(trip_persons.trip_id, persons)
        .join(persons, persons.id == trip_persons.person_id)
        .filter(trip_persons.trip_id.in_(trip_ids))
        .all()
    )

    out: Dict[Union[int, str], List[Any]] = {}
    for trip_id, person in rows:
        out.setdefault(trip_id, []).append(person)
    return out


def get_trips(
    *,
    where: Optional[Callable[[TimeTravellersModels], Any]] = None,
    with_persons: bool = False,
) -> List[Dict[str, Any]]:
    """
    Returns trips as list of dicts.
    - where: SQLAlchemy filter expression
    - with_persons: adds `persons` array to each trip
    """
    models = get_models()
    where_clause = where(models) if where else None
    with db_client.get_db_session() as session:
        trip_rows = base_trips_query(session, models, where=where_clause).all()
        trips = [row._asdict() for row in trip_rows]

        if not with_persons or not trips:
            return trips

        trip_ids = [t["trip_id"] for t in trips]
        persons_map = fetch_trip_persons_map(session, models, trip_ids)

        for t in trips:
            t["persons"] = persons_map.get(t["trip_id"], [])

        return trips


# -----------------------------
# Routes: Persons
# -----------------------------
@router.get("/persons", status_code=HTTPStatus.OK)
async def persons(db: Session = Depends(db_client.get_session)):
    models = get_models()
    factory = APIFactory(models.persons, db)
    return factory.get_all(order=models.persons.role_name.asc())


@router.get("/persons/search", status_code=HTTPStatus.OK)
async def search_persons(name: str, db: Session = Depends(db_client.get_session)):
    persons = get_models().persons
    query = f"%{name}%"
    rows = (
        db.query(persons)
        .filter(
            or_(
                persons.actor_name.ilike(query),
                persons.short_role_name.ilike(query),
                persons.role_name.ilike(query),
            )
        )
        .all()
    )
    return rows if rows else not_found()


@router.get("/persons/list", status_code=HTTPStatus.OK)
async def persons_list(db: Session = Depends(db_client.get_session)):
    persons = get_models().persons
    rows = db.query(persons.id, persons.role_name).all()
    return {row[0]: row[1] for row in rows}


@router.get("/persons/{person_id}", status_code=HTTPStatus.OK)
async def get_person_by_id(person_id: int, db: Session = Depends(db_client.get_session)):
    factory = APIFactory(get_models().persons, db)
    return factory.get_by_id(person_id)


@router.get("/persons/{person_id}/trips", status_code=HTTPStatus.OK)
async def get_person_trips(person_id: int, db: Session = Depends(db_client.get_session)):
    models = get_models()
    trip_persons = models.trip_persons
    departure_dates = models.departure_dates
    arrival_dates = models.arrival_dates
    movies = models.movies
    persons = models.persons
    trips = models.trips
    select = (
        trip_persons.trip_id,
        departure_dates.id.label("departure_date_id"),
        departure_dates.date.label("departure_date"),
        departure_dates.time.label("departure_time"),
        arrival_dates.id.label("arrival_date_id"),
        arrival_dates.date.label("arrival_date"),
        arrival_dates.time.label("arrival_time"),
        movies.title.label("movie_title"),
        movies.original_title.label("movie_original_title"),
        movies.released.label("movie_released"),
        movies.imdb_url.label("movie_imdb_url"),
        persons.id.label("person_id"),
        persons.role_name,
        trip_persons.trip_order,
        trips.memo,
    )

    rows = (
        db.query(*select)
        .join(trips, trip_persons.trip_id == trips.id, isouter=True)
        .join(departure_dates, departure_dates.id == trips.departure_date_id, isouter=True)
        .join(arrival_dates, arrival_dates.id == trips.arrival_date_id, isouter=True)
        .join(movies, movies.id == trips.movie_id, isouter=True)
        .join(persons, persons.id == trip_persons.person_id)
        .filter(trip_persons.person_id == person_id)
        .order_by(trip_persons.trip_order.asc())
        .all()
    )

    return [r._asdict() for r in rows] if rows else not_found()


# -----------------------------
# Routes: Dates
# -----------------------------
@router.get("/dates", status_code=HTTPStatus.OK)
async def dates(db: Session = Depends(db_client.get_session)):
    factory = APIFactory(get_models().dates, db)
    return factory.get_all()


@router.get("/dates/{date_id}", status_code=HTTPStatus.OK)
async def get_date_by_id(date_id: int, db: Session = Depends(db_client.get_session)):
    factory = APIFactory(get_models().dates, db)
    return factory.get_by_id(date_id)


@router.get("/dates/{date_id}/trips", status_code=HTTPStatus.OK)
async def get_date_trips(date_id: int):
    trips = get_trips(
        where=lambda models: or_(
            models.departure_dates.id == date_id,
            models.arrival_dates.id == date_id,
        ),
        with_persons=True,
    )
    return trips if trips else not_found()


# -----------------------------
# Routes: Trips
# -----------------------------
@router.get("/trips", status_code=HTTPStatus.OK)
async def list_trips():
    trips = get_trips(with_persons=True)
    return trips if trips else not_found()


@router.get("/trips/{trip_id}", status_code=HTTPStatus.OK)
async def get_trip_by_id(trip_id: int):
    trips = get_trips(where=lambda models: models.trips.id == trip_id, with_persons=True)
    return trips[0] if trips else not_found()
