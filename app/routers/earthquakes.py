from http import HTTPStatus

import httpx
from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

import config
from app.utils.auth.bearer_token import BearerAuth

router = APIRouter(
    prefix="/earthquakes",
    tags=["earthquakes"],
    dependencies=[Depends(BearerAuth())],
)


@router.get("", status_code=HTTPStatus.OK)
async def get_data(
    start_date: str,
    end_date: str,
    min_magnitude: float,
    max_magnitude: float,
    max_lat: float | None = None,
    max_long: float | None = None,
    min_lat: float | None = None,
    min_long: float | None = None,
):
    """
    Fetches earthquake data from the USGS API based on the provided parameters.

    Parameters:
    - start_date (str): Start date of the earthquake data range (YYYY-MM-DD format).
    - end_date (str): End date of the earthquake data range (YYYY-MM-DD format).
    - min_magnitude (float): Minimum magnitude of the earthquake.
    - max_magnitude (float): Maximum magnitude of the earthquake.
    - max_lat (Optional[float]): Maximum latitude for filtering results.
    - max_long (Optional[float]): Maximum longitude for filtering results.
    - min_lat (Optional[float]): Minimum latitude for filtering results.
    - min_long (Optional[float]): Minimum longitude for filtering results.

    Returns:
    - JSONResponse: The response from the USGS API or an error message.
    """
    query_params = {
        "starttime": start_date,
        "endtime": end_date,
        "minmagnitude": min_magnitude,
        "maxmagnitude": max_magnitude,
    }

    optional_params = {
        "maxlatitude": max_lat,
        "maxlongitude": max_long,
        "minlatitude": min_lat,
        "minlongitude": min_long,
    }

    # Add optional parameters if they are provided
    query_params |= {k: v for k, v in optional_params.items() if v is not None}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(config.USGS_API_HOST, params=query_params)
    except httpx.RequestError:
        return JSONResponse(
            status_code=HTTPStatus.BAD_GATEWAY,
            content={"error": "Earthquake data service is unavailable"},
        )

    if response.status_code == HTTPStatus.OK:
        return response.json()
    return JSONResponse(status_code=response.status_code, content={"error": response.reason})
