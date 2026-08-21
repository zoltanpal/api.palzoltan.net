from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from app.models.sentio import (
    DetailedSourcesResponse,
    LiveQueryResponse,
    PromptRequest,
    PromptResponse,
    QueryPromptRequest,
)
from app.services.sentio.analytics import build_live_query_response, build_drivers_response
from app.services.sentio.query_parser import parse_user_query_with_ai
from app.repositories.sentio.repository import sentio_repository

router = APIRouter(
    prefix="/sentio",
    tags=["sentio"],
    # dependencies=[Depends(BearerAuth())],
)

@router.get(
    "/detailed_sources",
    response_model=list[DetailedSourcesResponse],
    status_code=HTTPStatus.OK
)
async def detalied_sources_list() -> list[DetailedSourcesResponse]:
    return sentio_repository.fetch_detailed_sources()

@router.post(
    "/live/parse_prompt",
    response_model=PromptResponse,
    status_code=HTTPStatus.OK,
)
async def parse_prompt(payload: PromptRequest) -> PromptResponse:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Prompt cannot be empty",
        )

    parsed = parse_user_query_with_ai(prompt)

    return PromptResponse(
        prompt=prompt,
        query=parsed.query or "",
        window_hours=parsed.window_hours,
        intent=parsed.intent,
    )


@router.post("/live/query", response_model=LiveQueryResponse, status_code=HTTPStatus.OK)
async def live_query(
    payload: QueryPromptRequest,
) -> LiveQueryResponse:
    return build_live_query_response(
        query=payload.query,
        window_hours=payload.window_hours,
        prompt=payload.prompt,
        use_ai=payload.use_ai,
    )

@router.post("/live/drivers",  status_code=HTTPStatus.OK)
async def live_drivers(
    payload: QueryPromptRequest,
) -> list:
    return build_drivers_response(
        query=payload.query,
        window_hours=payload.window_hours,
        use_ai=payload.use_ai,
    )