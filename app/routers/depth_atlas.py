from fastapi import APIRouter, Depends
from http import HTTPStatus

from app.utils.auth.bearer_token import BearerAuth

from app.repositories.depth_atlas.depth_atlas_repository import DepthAtlasRepository, get_validation_repository


router = APIRouter(
    prefix="/depth_atlas",
    tags=["depth_atlas"],
    dependencies=[Depends(BearerAuth())],
)


@router.get("/datasets", status_code=HTTPStatus.OK)
def datasets(repository: DepthAtlasRepository = Depends(get_validation_repository)) -> list:
    return repository.get_datasets()
