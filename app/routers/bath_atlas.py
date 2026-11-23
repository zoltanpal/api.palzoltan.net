from fastapi import APIRouter, Depends
from http import HTTPStatus

from app.utils.auth.bearer_token import BearerAuth

from app.repositories.bath_atlas.bath_atlas_repository import DepthAtlasRepository, get_validation_repository


router = APIRouter(
    prefix="/portfolio/bath_atlas",
    tags=["bath_atlas"],
    dependencies=[Depends(BearerAuth())],
)


@router.get("/datasets", status_code=HTTPStatus.OK)
def datasets(repository: DepthAtlasRepository = Depends(get_validation_repository)) -> list:
    return repository.get_datasets()
