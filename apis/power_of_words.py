# https://bl.ocks.org/vasturiano/ded69192b8269a78d2d97e24211e64e0
from fastapi import APIRouter, Depends

from config import time_travelers_db_config
from libs.auth.bearer_token import BearerAuth
from libs.db.db_client import SQLDBClient
from libs.db.db_mapping import SQLDBMapping

db_client = SQLDBClient(db_config=time_travelers_db_config)
db_mapping = SQLDBMapping(db_client=db_client)

router = APIRouter(
    prefix="/power_of_words",
    tags=["power_of_words"],
    dependencies=[Depends(BearerAuth())]
)
