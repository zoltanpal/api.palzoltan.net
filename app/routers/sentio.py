from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from app.models.sentio import (
    LiveQueryResponse,
    PromptRequest,
    PromptResponse,
    QueryPromptRequest,
)
from app.services.sentio.analytics import build_live_query_response
from app.services.sentio.query_parser import parse_user_query_with_ai

router = APIRouter(
    prefix="/sentio",
    tags=["sentio"],
    # dependencies=[Depends(BearerAuth())],
)


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
