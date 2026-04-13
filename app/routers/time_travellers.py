from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from fastapi import APIRouter, Depends
from palzlib_db.db_client import DBClient
from palzlib_db.db_mapper import DBMapper
from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased
from starlette.responses import JSONResponse

from config import time_travelers_db_config
from app.utils.api_factory import APIFactory

from app.utils.auth.bearer_token import BearerAuth
from app.utils.reponses import NOT_FOUND


# -----------------------------
# DB / Models
# -----------------------------
db_client = DBClient(db_config=time_travelers_db_config)
db_mapping = DBMapper(db_client=db_client)

Persons = db_mapping.get_model("persons")
Trips = db_mapping.get_model("trips")
TripPersons = db_mapping.get_model("trip_persons")
Dates = db_mapping.get_model("dates")
Movies = db_mapping.get_model("movies")
Devices = db_mapping.get_model("devices")

DepartureDates = aliased(Dates)
ArrivalDates = aliased(Dates)

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


def trips_select_columns() -> Tuple[Any, ...]:
    """
    Central place for trips "DTO" columns so we don't duplicate.
    """
    return (
        Trips.id.label("trip_id"),
        DepartureDates.id.label("departure_date_id"),
        DepartureDates.date.label("departure_date"),
        DepartureDates.time.label("departure_time"),
        ArrivalDates.id.label("arrival_date_id"),
        ArrivalDates.date.label("arrival_date"),
        ArrivalDates.time.label("arrival_time"),
        Movies.title.label("movie_title"),
        Movies.original_title.label("movie_original_title"),
        Movies.released.label("movie_released"),
        Movies.imdb_url.label("movie_imdb_url"),
        Movies.plot.label("movie_plot"),
        Devices.name.label("timejump_device_name"),
        Devices.description.label("timejump_device_description"),
        Devices.more_info.label("timejump_device_link"),
        Trips.memo,
    )


def base_trips_query(
    session: Session,
    where: Optional[Any] = None,
):
    query = (
        session.query(*trips_select_columns())
        .join(DepartureDates, DepartureDates.id == Trips.departure_date_id, isouter=True)
        .join(ArrivalDates, ArrivalDates.id == Trips.arrival_date_id, isouter=True)
        .join(Devices, Devices.id == Trips.device_id, isouter=True)
        .join(Movies, Movies.id == Trips.movie_id, isouter=True)
    )
    if where is not None:
        query = query.filter(where)
    return query


def fetch_trip_persons_map(
    session: Session,
    trip_ids: Sequence[Union[int, str]],
) -> Dict[Union[int, str], List[Any]]:
    """
    Fetch all persons for all trips in one query, and group them by trip_id.
    """
    if not trip_ids:
        return {}

    rows = (
        session.query(TripPersons.trip_id, Persons)
        .join(Persons, Persons.id == TripPersons.person_id)
        .filter(TripPersons.trip_id.in_(trip_ids))
        .all()
    )

    out: Dict[Union[int, str], List[Any]] = {}
    for trip_id, person in rows:
        out.setdefault(trip_id, []).append(person)
    return out


def get_trips(
    *,
    where: Optional[Any] = None,
    with_persons: bool = False,
) -> List[Dict[str, Any]]:
    """
    Returns trips as list of dicts.
    - where: SQLAlchemy filter expression
    - with_persons: adds `persons` array to each trip
    """
    with db_client.get_db_session() as session:
        trip_rows = base_trips_query(session, where=where).all()
        trips = [row._asdict() for row in trip_rows]

        if not with_persons or not trips:
            return trips

        trip_ids = [t["trip_id"] for t in trips]
        persons_map = fetch_trip_persons_map(session, trip_ids)

        for t in trips:
            t["persons"] = persons_map.get(t["trip_id"], [])

        return trips


# -----------------------------
# Routes: Persons
# -----------------------------
@router.get("/persons", status_code=HTTPStatus.OK)
async def persons(db: Session = Depends(db_client.get_session)):
    factory = APIFactory(Persons, db)
    return factory.get_all(order=Persons.role_name.asc())


@router.get("/persons/search", status_code=HTTPStatus.OK)
async def search_persons(name: str, db: Session = Depends(db_client.get_session)):
    query = f"%{name}%"
    rows = (
        db.query(Persons)
        .filter(
            or_(
                Persons.actor_name.ilike(query),
                Persons.short_role_name.ilike(query),
                Persons.role_name.ilike(query),
            )
        )
        .all()
    )
    return rows if rows else not_found()


@router.get("/persons/list", status_code=HTTPStatus.OK)
async def persons_list(db: Session = Depends(db_client.get_session)):
    rows = db.query(Persons.id, Persons.role_name).all()
    return {row[0]: row[1] for row in rows}


@router.get("/persons/{person_id}", status_code=HTTPStatus.OK)
async def get_person_by_id(person_id: int, db: Session = Depends(db_client.get_session)):
    factory = APIFactory(Persons, db)
    return factory.get_by_id(person_id)


@router.get("/persons/{person_id}/trips", status_code=HTTPStatus.OK)
async def get_person_trips(person_id: int, db: Session = Depends(db_client.get_session)):
    select = (
        TripPersons.trip_id,
        DepartureDates.id.label("departure_date_id"),
        DepartureDates.date.label("departure_date"),
        DepartureDates.time.label("departure_time"),
        ArrivalDates.id.label("arrival_date_id"),
        ArrivalDates.date.label("arrival_date"),
        ArrivalDates.time.label("arrival_time"),
        Movies.title.label("movie_title"),
        Movies.original_title.label("movie_original_title"),
        Movies.released.label("movie_released"),
        Movies.imdb_url.label("movie_imdb_url"),
        Persons.id.label("person_id"),
        Persons.role_name,
        TripPersons.trip_order,
        Trips.memo,
    )

    rows = (
        db.query(*select)
        .join(Trips, TripPersons.trip_id == Trips.id, isouter=True)
        .join(DepartureDates, DepartureDates.id == Trips.departure_date_id, isouter=True)
        .join(ArrivalDates, ArrivalDates.id == Trips.arrival_date_id, isouter=True)
        .join(Movies, Movies.id == Trips.movie_id, isouter=True)
        .join(Persons, Persons.id == TripPersons.person_id)
        .filter(TripPersons.person_id == person_id)
        .order_by(TripPersons.trip_order.asc())
        .all()
    )

    return [r._asdict() for r in rows] if rows else not_found()


# -----------------------------
# Routes: Dates
# -----------------------------
@router.get("/dates", status_code=HTTPStatus.OK)
async def dates(db: Session = Depends(db_client.get_session)):
    factory = APIFactory(Dates, db)
    return factory.get_all()


@router.get("/dates/{date_id}", status_code=HTTPStatus.OK)
async def get_date_by_id(date_id: int, db: Session = Depends(db_client.get_session)):
    factory = APIFactory(Dates, db)
    return factory.get_by_id(date_id)


@router.get("/dates/{date_id}/trips", status_code=HTTPStatus.OK)
async def get_date_trips(date_id: int):
    where = or_(DepartureDates.id == date_id, ArrivalDates.id == date_id)
    trips = get_trips(where=where, with_persons=True)
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
    trips = get_trips(where=(Trips.id == trip_id), with_persons=True)
    return trips[0] if trips else not_found()
