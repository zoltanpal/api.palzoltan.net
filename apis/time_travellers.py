from http import HTTPStatus

# https://bl.ocks.org/vasturiano/ded69192b8269a78d2d97e24211e64e0
from fastapi import APIRouter, Depends
from palzlib.database.db_client import DBClient
from palzlib.database.db_mapper import DBMapper
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased
from starlette.responses import JSONResponse

from config import time_travelers_db_config
from libs.api_factory import APIFactory
from libs.auth.bearer_token import BearerAuth
from libs.responses import responses

db_client = DBClient(db_config=time_travelers_db_config)
db_mapping = DBMapper(db_client=db_client)
Persons = db_mapping.get_model("persons")
Trips = db_mapping.get_model("trips")
TripPersons = db_mapping.get_model("trip_persons")
Dates = db_mapping.get_model("dates")
Movies = db_mapping.get_model("movies")
Devices = db_mapping.get_model("devices")

# Aliases for the Dates
DepartureDates = aliased(Dates)
ArrivalDates = aliased(Dates)

router = APIRouter(
    prefix="/time_travellers",
    tags=["time_travellers"],
    dependencies=[Depends(BearerAuth())]
)


def get_trips_query(where: tuple = None, with_persons: bool = False) -> dict:
    result = []

    select = (
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
        Trips.memo
    )

    with db_client.get_db_session() as session:
        query = session.query(*select) \
            .join(DepartureDates, DepartureDates.id == Trips.departure_date_id, isouter=True) \
            .join(ArrivalDates, ArrivalDates.id == Trips.arrival_date_id, isouter=True) \
            .join(Devices, Devices.id == Trips.device_id, isouter=True) \
            .join(Movies, Movies.id == Trips.movie_id, isouter=True)

        if where is not None:
            query = query.filter(where)

        result = query.all()

        if with_persons:
            result_trips = []
            for trip in result:
                trip_dict = trip._asdict()

                trip_persons = session.query(Persons).join(TripPersons, Persons.id == TripPersons.person_id).filter(
                    TripPersons.trip_id == trip.trip_id).all()
                trip_dict['persons'] = trip_persons

                result_trips.append(trip_dict)
            result = result_trips

    return result


@router.get('/persons', status_code=HTTPStatus.OK)
async def persons(db: Session = Depends(db_client.get_session)):
    """
    Get all the documents in persons collection

    :return: persons json
    """
    factory = APIFactory(Persons, db)
    order = Persons.role_name.asc()
    return factory.get_all(order=order)


@router.get('/persons/search', status_code=HTTPStatus.OK)
async def search(name: str, db_session: Session = Depends(db_client.get_session)):
    """ Search person for name, role name """

    query = "%{}%".format(name)
    persons = db_session.query(Persons).filter(or_(Persons.actor_name.ilike(query),
                                                   Persons.short_role_name.ilike(query),
                                                   Persons.role_name.ilike(query))).all()

    if persons is not None:
        return persons
    else:
        return JSONResponse(status_code=404, content=responses[404])


@router.get('/persons/list', status_code=HTTPStatus.OK)
async def persons_list(db_session: Session = Depends(db_client.get_session)):
    """
    List of persons
    :return: ID:PersonName list
    """

    return db_session.query(Persons.id, Persons.role_name).all()


@router.get('/persons/{person_id}', status_code=HTTPStatus.OK)
async def get_person_by_id(person_id: int, db: Session = Depends(db_client.get_session)):
    """
    Return person object by ID

    :param db: DB session
    :param person_id: Person ObjectId
    :return:
    """

    factory = APIFactory(Persons, db)
    return factory.get_by_id(person_id)


@router.get('/dates', status_code=HTTPStatus.OK)
async def dates(db: Session = Depends(db_client.get_session)):
    """
    Get all the documents in persons collection

    :return: persons json
    """
    factory = APIFactory(Dates, db)

    return factory.get_all()


@router.get('/dates/{date_id}', status_code=HTTPStatus.OK)
async def get_date_by_id(date_id: int, db: Session = Depends(db_client.get_session)):
    """
    Return date object by ID

    :param date_id: Date ObjectId
    :return:
    """
    factory = APIFactory(Dates, db)

    return factory.get_by_id(date_id)


@router.get('/dates/{date_id}/trips', status_code=HTTPStatus.OK)
async def get_person_trips(date_id: int):
    """
    Get person's trips

    :param person_id: Person ObjectId
    :return:
    """
    where = (or_(DepartureDates.id == date_id, ArrivalDates.id == date_id))
    trips = get_trips_query(where=where, with_persons=True)

    if len(trips) == 0:
        return JSONResponse(status_code=404, content=responses[404])

    return trips


@router.get('/persons/{person_id}/trips', status_code=HTTPStatus.OK)
async def get_person_trips(person_id: int, db_session: Session = Depends(db_client.get_session)):
    """
    Get person's trips

    :param db_session:
    :param person_id: Person ObjectId
    :return:
    """

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
        TripPersons.trip_order, Trips.memo
    )

    trips = db_session.query(*select) \
        .join(Trips, TripPersons.trip_id == Trips.id, isouter=True) \
        .join(DepartureDates, DepartureDates.id == Trips.departure_date_id, isouter=True) \
        .join(ArrivalDates, ArrivalDates.id == Trips.arrival_date_id, isouter=True) \
        .join(Movies, Movies.id == Trips.movie_id, isouter=True) \
        .join(Persons, Persons.id == TripPersons.person_id) \
        .filter(TripPersons.person_id == person_id) \
        .order_by(TripPersons.trip_order.asc()) \
        .all()

    if len(trips) == 0:
        return JSONResponse(status_code=404, content=responses[404])

    result_trips = [trip._asdict() for trip in trips]
    return result_trips


@router.get('/trips', status_code=HTTPStatus.OK)
async def get_trips():
    trips = get_trips_query(with_persons=True)

    if len(trips) == 0:
        return JSONResponse(status_code=404, content=responses[404])

    return trips


@router.get('/trips/{trip_id}', status_code=HTTPStatus.OK)
async def get_trips_by_id(trip_id: int):
    where = (Trips.id == trip_id)
    trips = get_trips_query(where=where, with_persons=True)

    if len(trips) == 0:
        return JSONResponse(status_code=404, content=responses[404])

    return trips[0]
