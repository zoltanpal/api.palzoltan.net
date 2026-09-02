from http import HTTPStatus

from fastapi import APIRouter, Depends

from app.models.sentio import (
    DashboardResponse,
    DetailedSourceResponse,
    PromptRequest,
    PromptResponse,
    QueryPromptRequest,
)
from app.repositories.sentio.repository import SentioRepository, get_sentio_repository
from app.services.sentio.ai_summarizer import summarize_what_happend_with_ai
from app.services.sentio.dashboard_service import SentioDashboardService
from app.services.sentio.prompt_parser import parse_user_query_with_ai

router = APIRouter(prefix="/sentio", tags=["sentio"])


def get_dashboard_service(
    repository: SentioRepository = Depends(get_sentio_repository),
) -> SentioDashboardService:
    return SentioDashboardService(repository, summary_provider=summarize_what_happend_with_ai)


@router.get(
    "/detailed_sources",
    response_model=list[DetailedSourceResponse],
    status_code=HTTPStatus.OK,
)
def detailed_sources_list(
    repository: SentioRepository = Depends(get_sentio_repository),
) -> list[DetailedSourceResponse]:
    return repository.fetch_detailed_sources()


@router.post("/parse_prompt", response_model=PromptResponse, status_code=HTTPStatus.OK)
def parse_prompt(payload: PromptRequest) -> PromptResponse:
    parsed = parse_user_query_with_ai(payload.prompt)
    return PromptResponse(
        prompt=payload.prompt,
        query=parsed.query or "",
        window_hours=parsed.window_hours,
        intent=parsed.intent,
    )

@router.post("/dashboard", response_model=DashboardResponse, status_code=HTTPStatus.OK)
def dashboard(
    payload: QueryPromptRequest,
    service: SentioDashboardService = Depends(get_dashboard_service),
) -> DashboardResponse:
    return service.build_dashboard(
        query=payload.query,
        window_hours=payload.window_hours,
        prompt=payload.prompt,
        use_ai=payload.use_ai,
    )
