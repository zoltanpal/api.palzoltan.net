from http import HTTPStatus

import requests
from fastapi import APIRouter
from starlette.responses import JSONResponse

import config
from libs.responses import responses

router = APIRouter(
    prefix="/earthquakes",
    tags=["earthquakes"]
)


@router.get('', status_code=HTTPStatus.OK)
async def get_data(start_date: str, end_date: str, min_magnitude: float, max_magnitude: float, max_lat: float = None,
                   max_long: float = None, min_lat: float = None, min_long: float = None):
    obj = {
        'starttime': str(start_date),
        'endtime': str(end_date),
        'minmagnitude': float(min_magnitude),
        'maxmagnitude': float(max_magnitude)
    }

    if max_lat is not None:
        obj.update({'maxlatitude': max_lat})
    if max_long is not None:
        obj.update({'maxlongitude': max_long})
    if min_lat is not None:
        obj.update({'minlatitude': min_lat})
    if min_long is not None:
        obj.update({'minlongitude': min_long})

    parameters = '&'.join(['{}={}'.format(e, obj[e]) for e in obj])
    url = "{api_host}&{params}".format(api_host=config.USGS_API_HOST, params=parameters)
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        return JSONResponse(status_code=response.status_code, content=responses[response.status_code])
