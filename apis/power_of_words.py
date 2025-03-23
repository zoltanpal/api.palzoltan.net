from collections import Counter
from datetime import date
from http import HTTPStatus
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from nltk.corpus import stopwords
from palzlib.database.db_client import DBClient
from palzlib.database.db_mapper import DBMapper
from sqlalchemy import and_, asc, case, func, or_, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import pow_db_config
from libs.auth.bearer_token import BearerAuth
from libs.functions import generate_sentiment_by_source_series, to_dict
from libs.responses import responses
from models.feed_db_filters import FeedDBFilters

db_client = DBClient(db_config=pow_db_config)
db_mapper = DBMapper(db_client=db_client)
Feeds = db_mapper.get_model("feeds")
FeedSentiments = db_mapper.get_model("feed_sentiments")
Sources = db_mapper.get_model("sources")

router = APIRouter(
    prefix="/power_of_words",
    tags=["power_of_words"],
    dependencies=[Depends(BearerAuth())],
)

STOPWORDS = stopwords.words("hungarian")


@router.get("/feeds")
async def feeds(
    start_date: date,
    end_date: date,
    sources: Optional[List[int]] = Query(None),
    words: Optional[List[str]] = Query(None),
    free_text: Optional[str] = Query(None),
    page: int = 1,
    items_per_page: int = 30,
    db: Session = Depends(db_client.get_session),
):
    filters = FeedDBFilters(
        start_date=str(start_date),
        end_date=str(end_date),
        words=words or [],
        sources=sources or [],
        free_text=free_text or "",
    )
    filters.Feed = Feeds

    query = (
        db.query(Feeds, FeedSentiments)
        .join(
            FeedSentiments,
            and_(FeedSentiments.feed_id == Feeds.id, FeedSentiments.model_id == 1),
        )
        .filter(filters.conditions)
        .order_by(Feeds.published.desc())
    )

    total_items = query.count()
    results = db.execute(
        query.limit(items_per_page).offset((page - 1) * items_per_page)
    ).all()

    return {
        "total": total_items,
        "page": page,
        "feeds": [
            {"feed": to_dict(feed), "feed_sentiments": to_dict(sentiment)}
            for feed, sentiment in results
        ],
    }


@router.get("/get_sentiment_grouped")
async def get_sentiment_grouped(
    start_date: date,
    end_date: date,
    words: Optional[List[str]] = Query(None),
    free_text: Optional[str] = Query(None),
    group_by: str = "source",
    db: Session = Depends(db_client.get_session),
):
    filters = FeedDBFilters(
        start_date=str(start_date),
        end_date=str(end_date),
        words=words or [],
        free_text=free_text or "",
    )
    filters.Feed = Feeds

    group_by_column = Feeds.source_id if group_by == "source" else Feeds.feed_date
    query = (
        select(
            group_by_column.label("group_by"),
            func.count(Feeds.id).label("count"),
            FeedSentiments.sentiment_key,
        )
        .join(
            FeedSentiments,
            (Feeds.id == FeedSentiments.feed_id) & (FeedSentiments.model_id == 1),
            isouter=True,
        )
        .where(filters.conditions)
        .group_by(group_by_column, FeedSentiments.sentiment_key)
        .order_by(asc(group_by_column))
    )
    return generate_sentiment_by_source_series(db.execute(query).all())


@router.get("/most_common_words", status_code=HTTPStatus.OK)
async def most_common_words(
    start_date: str,
    end_date: str,
    nm_common: int = 20,
    db: Session = Depends(db_client.get_session),
):
    cursor_result = db.query(Feeds.words).filter(
        Feeds.feed_date.between(start_date, end_date)
    )
    words: List[str] = []
    for row_words in list(cursor_result):
        words.extend(word for word in row_words[0] if word not in STOPWORDS)

    return Counter(words).most_common(nm_common)


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


@router.get("/extreme_sentiments")
async def get_extreme_sentiments(
    start_date: str,
    end_date: str,
    sources: Optional[List[int]] = Query(None),
    db: Session = Depends(db_client.get_session),
):
    filters = FeedDBFilters(
        start_date=start_date, end_date=end_date, sources=sources if sources else []
    )
    filters.Feed = Feeds

    query = (
        select(
            Feeds.title,
            Sources.name.label("source"),
            func.DATE(Feeds.published),
            FeedSentiments.sentiment_key,
            FeedSentiments.sentiment_value,
        )
        .join(FeedSentiments, FeedSentiments.feed_id == Feeds.id)
        .join(Sources, Feeds.source_id == Sources.id)
        .where(
            or_(
                FeedSentiments.sentiment_value > 0.8,
                FeedSentiments.sentiment_value < -0.8,
            ),
            FeedSentiments.sentiment_key != "neutral",
            filters.conditions,
        )
        .order_by(FeedSentiments.sentiment_value.desc())
    )

    results = db.execute(query).mappings().all()

    return results
