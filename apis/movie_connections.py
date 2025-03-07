from http import HTTPStatus
from typing import Tuple, List, Annotated
from urllib.parse import quote

import requests
from fastapi import APIRouter, Depends, Query
from starlette.responses import JSONResponse

import config
from libs.auth.bearer_token import BearerAuth
from libs.responses import responses

router = APIRouter(
    prefix="/movie_connections",
    tags=["movie_connections"]
)

bearer_security = BearerAuth()


def get_data_from_url(url: str) -> Tuple:
    resp = requests.get(url)

    if int(resp.status_code) == 200:
        return resp.status_code, resp.json()
    else:
        return resp.status_code, resp.json()["status_message"]


def parse_person_ids(person_ids: str) -> List[int]:
    try:
        return [int(id.strip()) for id in person_ids.split(",")]
    except ValueError:
        raise ValueError("Invalid person_ids format. Expected comma-separated integers.")


def get_person_details(person_id: int):
    url = '{url}/person/{person_id}?api_key={key}'.format(url=config.IMDB_API_URL,
                                                          person_id=person_id,
                                                          key=config.IMDB_API_KEY)

    status_code, result = get_data_from_url(url)
    if status_code == 200:
        persons = []
        if len(result['results']) > 0:
            for result in result['results']:
                if result['gender'] > 0:
                    known_for = [(x['title'], x['original_title']) for x in result['known_for']]
                    person = {
                        "id": result['id'],
                        "name": result['name'],
                        "known_for_department": result['known_for_department'],
                        "popularity": result['popularity'],
                        "profile_path": result['profile_path'],
                        "known_for": known_for
                    }
                    persons.append(person)
        return persons
    else:
        responses[status_code]["error_message"] = result
        return JSONResponse(status_code=status_code, content=responses[status_code])


def get_person_movies(person_id: int):
    url = '{url}/person/{person_id}/movie_credits?api_key={key}'.format(url=config.IMDB_API_URL,
                                                                        person_id=person_id,
                                                                        key=config.IMDB_API_KEY)
    movies = []
    movies_list = []

    status_code, result = get_data_from_url(url)
    if status_code != 200:
        return []

    if len(result) == 0:
        return JSONResponse(
            status_code=HTTPStatus.NOT_FOUND,
            content=responses[HTTPStatus.NOT_FOUND],
        )
    else:
        for item in result['cast']:
            movie = {
                'person_id': int(person_id),
                'movie_id': int(item['id']),
                'character': item['character'],
                'title': item['title'],
                'original_title': item['original_title'],
                'popularity': item['popularity'],
                'overview': item['overview'],
                'poster_path': item['poster_path']
            }
            movies.append(movie)
            movies_list.append(item['id'])

        for item in result['crew']:
            movie = {
                'person_id': int(person_id),
                'movie_id': int(item['id']),
                'job': item['job'],
                'title': item['title'],
                'original_title': item['original_title'],
                'popularity': item['popularity'],
                'overview': item['overview'],
                'poster_path': item['poster_path']
            }
            movies.append(movie)
            movies_list.append(item['id'])

        result = {
            'movies': movies,
            'movies_list': movies_list
        }

        return result


@router.get('/persons/search', status_code=HTTPStatus.OK, dependencies=[Depends(bearer_security)])
async def person_search(name: str):
    if not name:
        return JSONResponse(status_code=HTTPStatus.BAD_REQUEST, content=responses[HTTPStatus.BAD_REQUEST])

    query = quote(name)
    url = '{url}/search/person?api_key={key}&query={q}&sort_by=popularity.desc'.format(url=config.IMDB_API_URL,
                                                                                       key=config.IMDB_API_KEY, q=query)

    status_code, result = get_data_from_url(url)

    if status_code == 200:
        persons = []
        if len(result['results']) > 0:
            for result in result['results']:
                if result['gender'] > 0:
                    known_for = []
                    for kf in result["known_for"]:
                        if "title" in kf:
                            movie_title = kf["title"]
                            if kf["original_title"] != movie_title:
                                movie_title += f'({kf["original_title"]})'
                            known_for.append(movie_title)
                    person = {"id": result['id'],
                              "name": result['name'],
                              "known_for_department": result['known_for_department'],
                              "popularity": result['popularity'],
                              "profile_path": result['profile_path'],
                              "known_for": ", ".join(list(known_for))}
                    persons.append(person)
        return persons
    else:
        responses[status_code]["error_message"] = result
        return JSONResponse(status_code=status_code, content=responses[status_code])


@router.get('/person/{person_id}/movies', dependencies=[Depends(bearer_security)])
async def person_movies(person_id: int):
    results = get_person_movies(person_id)

    if len(results) > 0:
        return JSONResponse(status_code=HTTPStatus.OK, content=results)
    else:
        return JSONResponse(
            status_code=HTTPStatus.NOT_FOUND,
            content=responses[HTTPStatus.NOT_FOUND],
        )


@router.put('/common_movies', dependencies=[Depends(bearer_security)])
async def common_movies(items: list):
    if items is None or not items:
        return JSONResponse(status_code=HTTPStatus.BAD_REQUEST, content=responses[HTTPStatus.BAD_REQUEST])

    items_set = [set(item) for item in items]
    return items_set[0].intersection(*items_set)


@router.get('/persons/common_movies', dependencies=[Depends(bearer_security)])
async def common_movies_of_persons(person_ids: Annotated[list, Query()] = []) -> list:
    common_movies: list = []
    person_ids_list = ",".join(str(x) for x in person_ids)

    url = '{url}/discover/movie?with_people={person_ids_list}?with_cast={person_ids_list}?with_crew={person_ids_list}&api_key={key}&sort_by=popularity.desc'.format(
        url=config.IMDB_API_URL,
        person_ids_list=person_ids_list,
        key=config.IMDB_API_KEY)

    status_code, result = get_data_from_url(url)
    if status_code == 200:
        common_movies_raw = result['results']
        if len(common_movies_raw) > 0:

            for movie in common_movies_raw:
                persons = []
                credit_url = '{url}/movie/{movie_id}/credits?api_key={key}&sort_by=popularity.desc'.format(
                    url=config.IMDB_API_URL,
                    movie_id=movie["id"],
                    key=config.IMDB_API_KEY)
                credit_status_code, credits = get_data_from_url(credit_url)
                if credit_status_code == 200:
                    for person_id in person_ids:
                        as_cast = list(filter(lambda cast: cast['id'] == person_id, credits['cast']))
                        as_crew = list(filter(lambda crew: crew['id'] == person_id, credits['crew']))
                        person_data = {
                            "person_id": person_id,
                            "jobs": as_cast,
                            "characters": as_crew
                        }

                        persons.append(person_data)

                common_movies.append(
                    {"movie_id": movie['id'],
                     "poster_path": movie['backdrop_path'],
                     "year": movie['release_date'][:4],
                     "title": movie['title'],
                     "original_title": movie['original_title'],
                     "original_language": movie['original_language'],
                     "overview": movie['overview'],
                     "release_date": movie['release_date'],
                     "popularity": movie['popularity'],
                     "persons": persons})

    return common_movies
