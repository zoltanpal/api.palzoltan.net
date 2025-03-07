from urllib.request import Request

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

import config
from apis import time_travellers, movie_connections, earthquakes
from libs.middlewares.query_flattening_middleware import QueryStringFlatteningMiddleware
from libs.middlewares.request_context_middleware import RequestContextMiddleware
from libs.responses import responses

app = FastAPI(
    title=config.API_NAME,
    debug=config.API_DEBUG,
    version="0.1",
    openapi_url="/swagger.json",
)

origins = config.AWS_CORS_ALLOWED_LIST

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(AuthenticationMiddleware)
app.add_middleware(QueryStringFlatteningMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(earthquakes.router)
app.include_router(time_travellers.router)
app.include_router(movie_connections.router)


@app.exception_handler(HTTPException)
async def http_event_handler(request: Request, exc: HTTPException):
    """Custom messages for HTTP requests

    @param request: HTTP request
    @param exc: HTTP Exception
    @return: JSON formatted response
    """

    # Authentication response messages come from HTTPException
    if exc.status_code in [401, 403]:
        response_content = {"status_code": exc.status_code, "message": exc.detail}
        return JSONResponse(status_code=exc.status_code, content=response_content)

    if exc.status_code == 404:
        return JSONResponse(status_code=404, content=responses["PAGE_NOT_FOUND"])

    if exc.status_code in [405, 500]:
        return JSONResponse(
            status_code=exc.status_code, content=responses[exc.status_code]
        )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    response_content = {"status_code": 400, "message": str(exc)}
    return JSONResponse(status_code=400, content=response_content)
