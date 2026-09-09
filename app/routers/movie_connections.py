from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from fastapi import APIRouter, Query, Depends
from requests import Response

import config
from app.utils.reponses import BAD_REQUEST, NOT_FOUND
from app.utils.auth.bearer_token import BearerAuth


router = APIRouter(
    prefix="/movie_connections",
    tags=["movie_connections"],
    dependencies=[Depends(BearerAuth())],
)

# -----------------------------------
# HTTP client helpers
# -----------------------------------


@dataclass(frozen=True)
class ImdbClient:
    base_url: str
    api_key: str
    timeout_s: float = 10.0

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        q = {"api_key": self.api_key}
        if params:
            q.update(params)

        resp: Response = requests.get(url, params=q, timeout=self.timeout_s)
        try:
            payload = resp.json()
        except Exception:
            payload = {"status_message": resp.text or "Non-JSON response from upstream."}

        if resp.status_code != 200:
            raise requests.HTTPError(
                f"Upstream error {resp.status_code}: {payload.get('status_message') or payload}"
            )

        return payload


imdb = ImdbClient(base_url=config.IMDB_API_URL, api_key=config.IMDB_API_KEY)


def _ensure_non_empty(value: Any, err=BAD_REQUEST) -> None:
    if value is None or value == "" or value == []:
        raise err.to_http_exception()


def _unique_ints(values: Sequence[int]) -> List[int]:
    seen = set()
    out = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(int(v))
    return out


def _person_summary(person: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if person.get("gender", 0) <= 0:
        return None

    known_for_pairs = [
        (x.get("title"), x.get("original_title"))
        for x in person.get("known_for", [])
        if x.get("title") is not None
    ]

    return {
        "id": person.get("id"),
        "name": person.get("name"),
        "known_for_department": person.get("known_for_department"),
        "popularity": person.get("popularity"),
        "profile_path": person.get("profile_path"),
        "known_for": known_for_pairs,
    }


def _movie_credit_item(person_id: int, item: Dict[str, Any], role_key: str) -> Dict[str, Any]:
    return {
        "person_id": int(person_id),
        "movie_id": int(item["id"]),
        role_key: item.get(role_key),
        "title": item.get("title"),
        "original_title": item.get("original_title"),
        "popularity": item.get("popularity"),
        "overview": item.get("overview"),
        "poster_path": item.get("poster_path"),
    }


# -----------------------------------
# Domain functions
# -----------------------------------


def get_person_details(person_id: int) -> List[Dict[str, Any]]:
    payload = imdb.get(f"person/{person_id}")
    persons: List[Dict[str, Any]] = []

    for p in payload.get("results", []):
        summary = _person_summary(p)
        if summary:
            persons.append(summary)

    return persons


def get_person_movies(person_id: int) -> Dict[str, Any]:
    payload = imdb.get(f"person/{person_id}/movie_credits")

    movies: List[Dict[str, Any]] = []
    movies_list: List[int] = []

    for item in payload.get("cast", []):
        movies.append(_movie_credit_item(person_id, item, "character"))
        movies_list.append(int(item["id"]))

    for item in payload.get("crew", []):
        movies.append(_movie_credit_item(person_id, item, "job"))
        movies_list.append(int(item["id"]))

    return {"movies": movies, "movies_list": movies_list}


def search_persons_by_name(name: str) -> List[Dict[str, Any]]:
    payload = imdb.get("search/person", params={"query": name, "sort_by": "popularity.desc"})
    out: List[Dict[str, Any]] = []

    for r in payload.get("results", []):
        if r.get("gender", 0) <= 0:
            continue

        known_for_titles: List[str] = []
        for kf in r.get("known_for", []):
            if "title" in kf:
                title = kf["title"]
                if kf.get("original_title") and kf["original_title"] != title:
                    title += f" ({kf['original_title']})"
                known_for_titles.append(title)

        out.append(
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "known_for_department": r.get("known_for_department"),
                "popularity": r.get("popularity"),
                "profile_path": r.get("profile_path"),
                "known_for": ", ".join(known_for_titles),
            }
        )

    return out


def discover_common_movies(person_ids: Sequence[int]) -> List[Dict[str, Any]]:
    """
    Uses discover endpoint, then enriches each movie with per-person cast/crew info
    by calling /movie/{id}/credits.
    """
    person_ids = _unique_ints(person_ids)
    _ensure_non_empty(person_ids, BAD_REQUEST)

    ids_csv = ",".join(str(x) for x in person_ids)

    payload = imdb.get(
        "discover/movie",
        params={
            "with_people": ids_csv,
            "sort_by": "popularity.desc",
        },
    )

    movies_raw = payload.get("results", []) or []
    common_movies: List[Dict[str, Any]] = []

    for movie in movies_raw:
        movie_id = movie["id"]

        persons: List[Dict[str, Any]] = []
        try:
            credits = imdb.get(f"movie/{movie_id}/credits", params={"sort_by": "popularity.desc"})
        except requests.HTTPError:
            credits = {"cast": [], "crew": []}

        cast = credits.get("cast", []) or []
        crew = credits.get("crew", []) or []

        for pid in person_ids:
            as_cast = [c for c in cast if c.get("id") == pid]
            as_crew = [c for c in crew if c.get("id") == pid]
            persons.append(
                {
                    "person_id": pid,
                    "characters": as_cast,
                    "jobs": as_crew,
                }
            )

        release_date = movie.get("release_date") or ""
        common_movies.append(
            {
                "movie_id": movie_id,
                "poster_path": movie.get("backdrop_path"),
                "year": release_date[:4] if len(release_date) >= 4 else None,
                "title": movie.get("title"),
                "original_title": movie.get("original_title"),
                "original_language": movie.get("original_language"),
                "overview": movie.get("overview"),
                "release_date": release_date or None,
                "popularity": movie.get("popularity"),
                "persons": persons,
            }
        )

    return common_movies


# -----------------------------------
# Routes
# -----------------------------------


@router.get("/persons/search", status_code=HTTPStatus.OK)
async def person_search(name: str):
    _ensure_non_empty(name, BAD_REQUEST)
    try:
        return search_persons_by_name(name)
    except requests.HTTPError as e:
        raise BAD_REQUEST.to_http_exception()


@router.get("/person/{person_id}/movies", status_code=HTTPStatus.OK)
async def person_movies(person_id: int):
    try:
        result = get_person_movies(person_id)
    except requests.HTTPError:
        raise NOT_FOUND.to_http_exception()

    if not result["movies"]:
        raise NOT_FOUND.to_http_exception()

    return result


@router.put("/common_movies", status_code=HTTPStatus.OK)
async def common_movies(items: List[List[int]]):
    _ensure_non_empty(items, BAD_REQUEST)
    sets = [set(item) for item in items if item]
    _ensure_non_empty(sets, BAD_REQUEST)
    return list(sets[0].intersection(*sets[1:]))


@router.get("/persons/common_movies", status_code=HTTPStatus.OK)
async def common_movies_of_persons(
    person_ids: List[int] = Query(default=[]),
) -> List[Dict[str, Any]]:
    _ensure_non_empty(person_ids, BAD_REQUEST)
    try:
        return discover_common_movies(person_ids)
    except requests.HTTPError:
        raise NOT_FOUND.to_http_exception()
