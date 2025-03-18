from collections import Counter
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends
from nltk.corpus import stopwords
from palzlib.database.db_client import DBClient
from palzlib.database.db_mapper import DBMapper
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import pow_db_config
from libs.auth.bearer_token import BearerAuth
from libs.responses import responses

db_client = DBClient(db_config=pow_db_config)
db_mapper = DBMapper(db_client=db_client)
Feeds = db_mapper.get_model("feeds")
FeedSentiments = db_mapper.get_model("feed_sentiments")

router = APIRouter(
    prefix="/power_of_words",
    tags=["power_of_words"],
    dependencies=[Depends(BearerAuth())],
)

STOPWORDS = stopwords.words("hungarian")


@router.get("/most_common_words", status_code=HTTPStatus.OK)
async def most_common_words(
    start_date: str, end_date: str, db: Session = Depends(db_client.get_session)
):
    cursor_result = db.query(Feeds.words).filter(
        Feeds.feed_date.between(start_date, end_date)
    )
    words: List[str] = []
    for row_words in list(cursor_result):
        words.extend(word for word in row_words[0] if word not in STOPWORDS)

    return Counter(words).most_common(20)


@router.get("/count_sentiments", status_code=HTTPStatus.OK)
async def count_sentiments(
    start_date: str, end_date: str, db: Session = Depends(db_client.get_session)
):
    query = (
        db.query(
            func.sum(
                case((FeedSentiments.sentiment_key == "positive", 1), else_=0)
            ).label("positive_sentiments"),
            func.sum(
                case((FeedSentiments.sentiment_key == "negative", 1), else_=0)
            ).label("negative_sentiments"),
            func.sum(
                case((FeedSentiments.sentiment_key == "neutral", 1), else_=0)
            ).label("neutral_sentiments"),
        )
        .join(Feeds, FeedSentiments.feed_id == Feeds.id)
        .filter(
            FeedSentiments.model_id == 1, Feeds.feed_date.between(start_date, end_date)
        )
    )

    result = query.one()

    if result is None:
        JSONResponse(status_code=404, content=responses[404])

    return {
        "positive_sentiments": result.positive_sentiments or 0,
        "negative_sentiments": result.negative_sentiments or 0,
        "neutral_sentiments": result.neutral_sentiments or 0,
    }