from http import HTTPStatus
from config import FIREBASE_SA

from app.models.sentio.dashboard import TopEntityResponse
from app.utils.auth.bearer_token import BearerAuth
from app.utils.auth.firebase_auth import FirebaseAuth
from fastapi import APIRouter, Query, Depends, Path, HTTPException
from typing import List
import firebase_admin
from app.utils.reponses import BAD_REQUEST, NOT_FOUND
from firebase_admin import credentials


from app.models.sentio import (
    DashboardResponse,
    DetailedSourceResponse,
    PromptRequest,
    PromptResponse,
    QueryPromptRequest,
)
from app.repositories.sentio.repository import SentioRepository, get_sentio_repository
from app.repositories.sentio.validation_repository import (
    ValidationRepository,
    get_validation_repository,
)
from app.repositories.sentio.user_repository import UserRepository, get_user_repository
from app.services.sentio.ai_summarizer import summarize_what_happend_with_ai
from app.services.sentio.dashboard_service import SentioDashboardService
from app.services.sentio.prompt_parser import parse_user_query_with_ai
from app.services.sentio.validation_service import ValidationService
from app.services.sentio.user_service import UserService

from app.services.sentio.exceptions import (
    EntityNotFoundError,
    UserNotFoundError,
)

router = APIRouter(
    prefix="/sentio", 
    tags=["sentio"],
    #dependencies=[Depends(BearerAuth())],
)

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(
        credentials.Certificate(FIREBASE_SA)
    )

firebase_auth = FirebaseAuth()

def get_dashboard_service(repository: SentioRepository = Depends(get_sentio_repository)) -> SentioDashboardService:
    return SentioDashboardService(repository, summary_provider=summarize_what_happend_with_ai)


def get_validation_service(repository: ValidationRepository = Depends(get_validation_repository)) -> ValidationService:
    return ValidationService(repository=repository)


def get_user_service(repository: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repository=repository)


@router.get(
    "/detailed_sources",
    response_model=list[DetailedSourceResponse],
    dependencies=[Depends(BearerAuth())],
    status_code=HTTPStatus.OK,
)
def detailed_sources_list(
    repository: SentioRepository = Depends(get_sentio_repository),
) -> list[DetailedSourceResponse]:
    return repository.fetch_detailed_sources()


@router.post("/parse_prompt", response_model=PromptResponse, status_code=HTTPStatus.OK, dependencies=[Depends(BearerAuth())])
def parse_prompt(payload: PromptRequest) -> PromptResponse:
    parsed = parse_user_query_with_ai(payload.prompt)
    return PromptResponse(
        prompt=payload.prompt,
        query=parsed.query or "",
        window_hours=parsed.window_hours,
        window_parsed=parsed.window_parsed,
        intent=parsed.intent,
    )


@router.post("/dashboard", response_model=DashboardResponse, status_code=HTTPStatus.OK, dependencies=[Depends(BearerAuth())])
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

@router.get("/top_entities", status_code=HTTPStatus.OK, dependencies=[Depends(BearerAuth())])
def top_entities(
    service: SentioDashboardService = Depends(get_dashboard_service),
    time_window: int = 24,
    max_top_entities: int = 5,
    excluded_entity_types: List[str] = Query(default=["location"], 
                                             description="Comma-separated list of entity types to exclude"),
) -> List[TopEntityResponse]:

    return service.get_top_entities(
        time_window=time_window, 
        max_top_entities=max_top_entities,
        excluded_entity_types=excluded_entity_types)


@router.get("/user/me", status_code=HTTPStatus.OK)
def user_me(service: UserService = Depends(get_user_service), firebase_user: dict = Depends(firebase_auth)):
    return {
        "firebase_uid": firebase_user["uid"],
        "email": firebase_user.get("email"),
        "nickname": firebase_user.get("name"),
        "watchlist": service.user_watchlist(user_obj=firebase_user)
    }

@router.get("/entities/search", status_code=HTTPStatus.OK)
def search_entity(q: str, limit: int=10, service: UserService = Depends(get_user_service), firebase_user: dict = Depends(firebase_auth)):
    return service.search_entity(query=q, limit=limit)

@router.put("/user", status_code=HTTPStatus.OK)
def create_user(
    service: UserService = Depends(get_user_service),
    firebase_user: dict = Depends(firebase_auth),
):
    return service.create_user(firebase_user)


@router.put("/user/watchlist/{entity_id}", status_code=HTTPStatus.OK)
def create_user_watchlist(
    entity_id: int = Path(..., gt=0),
    service: UserService = Depends(get_user_service),
    firebase_user: dict = Depends(firebase_auth)
):
    try:
        return service.create_user_watchlist(firebase_user, entity_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="User not found",
        ) from exc
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Entity not found",
        ) from exc

@router.delete("/user/watchlist/{entity_id}", status_code=HTTPStatus.OK)
def remove_user_watchlist(
    entity_id: int = Path(..., gt=0),
    service: UserService = Depends(get_user_service),
    firebase_user: dict = Depends(firebase_auth)
):
    try:
        return service.remove_user_watchlist(firebase_user, entity_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="User not found",
        ) from exc
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Entity not found",
        ) from exc



@router.get("/user/watchlist", status_code=HTTPStatus.OK)
def user_watchlist(service: UserService = Depends(get_user_service), firebase_user: dict = Depends(firebase_auth)):
    return service.user_watchlist(user_obj=firebase_user)




@router.get("/health", status_code=HTTPStatus.OK, dependencies=[Depends(BearerAuth())])
def system_health(service: ValidationService = Depends(get_validation_service)):
    return service.system_health()


@router.get("/health/sentiment",status_code=HTTPStatus.OK, dependencies=[Depends(BearerAuth())])
def sentiment_health(service: ValidationService = Depends(get_validation_service)):
    return service.sentiment()


@router.get("/health/entity",status_code=HTTPStatus.OK, dependencies=[Depends(BearerAuth())])
def entity_health(service: ValidationService = Depends(get_validation_service)):
    return service.entity()


@router.get("/health/clustering",status_code=HTTPStatus.OK, dependencies=[Depends(BearerAuth())])
def clustering_health(service: ValidationService = Depends(get_validation_service)):
    return service.clustering()