"""Main FastAPI application factory."""

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, earthquakes, sentio, time_travellers, movie_connections, sentiment_analyzer
from app.utils.middlewares.query_flattening_middleware import QueryStringFlatteningMiddleware
from app.utils.middlewares.request_context_middleware import RequestContextMiddleware
# from app.utils.middlewares.authentication_middleware import AuthenticationMiddleware


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="api-palzoltan-net", version="0.1.0")

    app.add_middleware(QueryStringFlatteningMiddleware)
    app.add_middleware(RequestContextMiddleware)
    # app.add_middleware(AuthenticationMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(earthquakes.router)
    app.include_router(time_travellers.router)
    app.include_router(movie_connections.router)
    app.include_router(sentiment_analyzer.router)
    app.include_router(sentio.router)

    return app
