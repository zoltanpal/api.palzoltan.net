# https://bl.ocks.org/vasturiano/ded69192b8269a78d2d97e24211e64e0
from fastapi import APIRouter, Depends

from libs.auth.bearer_token import BearerAuth

router = APIRouter(
    prefix="/power_of_words",
    tags=["power_of_words"],
    dependencies=[Depends(BearerAuth())],
)
