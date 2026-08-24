from http import HTTPStatus

from fastapi import APIRouter, Depends

from app.models.sentio import (
    DashboardResponse,
    DetailedSourcesResponse,
    DriversRequest,
    PromptRequest,
    PromptResponse,
    QueryPromptRequest,
    WhatDrivingResponse,
)
from app.repositories.sentio.repository import SentioRepository, get_sentio_repository
from app.services.sentio.analytics import SentioDashboardService
from app.services.sentio.query_parser import parse_user_query_with_ai
from app.services.sentio.summarizer import summarize_headlines_with_ai

router = APIRouter(prefix="/sentio", tags=["sentio"])


def get_dashboard_service(
    repository: SentioRepository = Depends(get_sentio_repository),
) -> SentioDashboardService:
    return SentioDashboardService(repository, summary_provider=summarize_headlines_with_ai)


@router.get(
    "/detailed_sources",
    response_model=list[DetailedSourcesResponse],
    status_code=HTTPStatus.OK,
)
def detailed_sources_list(
    repository: SentioRepository = Depends(get_sentio_repository),
) -> list[DetailedSourcesResponse]:
    return repository.fetch_detailed_sources()


@router.post("/live/parse_prompt", response_model=PromptResponse, status_code=HTTPStatus.OK)
def parse_prompt(payload: PromptRequest) -> PromptResponse:
    parsed = parse_user_query_with_ai(payload.prompt)
    return PromptResponse(
        prompt=payload.prompt,
        query=parsed.query or "",
        window_hours=parsed.window_hours,
        intent=parsed.intent,
    )


@router.post("/live/query", response_model=DashboardResponse, status_code=HTTPStatus.OK)
def live_query(
    payload: QueryPromptRequest,
    service: SentioDashboardService = Depends(get_dashboard_service),
) -> DashboardResponse:
    return service.build_dashboard(
        query=payload.query,
        window_hours=payload.window_hours,
        prompt=payload.prompt,
        use_ai=payload.use_ai,
    )


@router.post(
    "/live/drivers",
    response_model=list[WhatDrivingResponse],
    status_code=HTTPStatus.OK,
)
def live_drivers(
    payload: DriversRequest,
    service: SentioDashboardService = Depends(get_dashboard_service),
) -> list[WhatDrivingResponse]:
    return service.build_drivers(query=payload.query, window_hours=payload.window_hours)
