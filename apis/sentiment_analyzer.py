from http import HTTPStatus

from fastapi import APIRouter, Depends
from palzlib.sentiment_analyzers.factory.sentiment_factory import (
    SentimentAnalyzerFactory,
)
from pydantic import BaseModel
from starlette.responses import JSONResponse

from libs.auth.bearer_token import BearerAuth

router = APIRouter(
    prefix="/sentiment_analyzer",
    tags=["sentiment_analyzer"],
    dependencies=[Depends(BearerAuth())],
)


class InputData(BaseModel):
    lang: str
    text: str


@router.post("/analyze_text", status_code=HTTPStatus.OK)
async def analyze_text(item: InputData):
    analyzer = SentimentAnalyzerFactory.get_analyzer(item.lang)
    result = analyzer.analyze_text(item.text)

    return JSONResponse(status_code=200, content=result.asdict())
