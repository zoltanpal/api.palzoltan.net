from collections import Counter
from datetime import date
from http import HTTPStatus
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from nltk.corpus import stopwords
from palzlib.database.db_client import DBClient
from palzlib.database.db_mapper import DBMapper
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import pow_db_config
from libs.auth.bearer_token import BearerAuth
from libs.functions import generate_sentiment_by_source_series, to_dict
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


@router.get("/feeds")
async def feeds(
    start_date: date,
    end_date: date,
    sources: Optional[List[int]] = Query(
        None, description="Comma-separated list of source IDs"
    ),
    words: Optional[List[str]] = Query(
        None, description="Comma-separated list of words"
    ),
    free_text: Optional[str] = Query(None, description="Optional free text search"),
    page: int = 1,
    items_per_page: int = 30,
    db: Session = Depends(db_client.get_session),
):

    query_cond = []

    if start_date:
        query_cond.append(Feeds.feed_date >= start_date)
    if end_date:
        query_cond.append(Feeds.feed_date <= end_date)
    if words:
        words_cond = [word.lower().strip() for word in words]
        query_cond.append(Feeds.words.contains(words_cond))
    if sources:
        query_cond.append(Feeds.source_id.in_(sources))
    if free_text:
        query_cond.append(Feeds.title.ilike(f"%{free_text}%"))

    conditions = and_(*query_cond) if query_cond else None

    query = (
        db.query(Feeds, FeedSentiments)
        .join(
            FeedSentiments,
            and_(
                FeedSentiments.feed_id == Feeds.id,
                FeedSentiments.model_id == 1,
            ),
        )
        .filter(conditions)
        .order_by(Feeds.published.desc())
    )

    total_items = query.count()
    paginated_query = query.limit(items_per_page).offset((page - 1) * items_per_page)

    results = db.execute(paginated_query).all()

    feeds = [
        {"feed": to_dict(feed), "feed_sentiments": to_dict(sentiment)}
        for feed, sentiment in results
    ]

    return {"total": total_items, "page": page, "feeds": feeds}


@router.get("/get_sentiment_grouped", status_code=HTTPStatus.OK)
async def get_sentiment_grouped(
    start_date: date,
    end_date: date,
    words: Optional[List[str]] = Query(
        None, description="Comma-separated list of words"
    ),
    free_text: Optional[str] = Query(None, description="Optional free text search"),
    group_by="source",
    db: Session = Depends(db_client.get_session),
):

    group_by = Feeds.source_id if group_by == "source" else Feeds.feed_date
    order_by = Feeds.source_id.asc() if group_by == "source" else Feeds.feed_date.asc()

    query = (
        select(
            group_by,
            func.count(Feeds.id).label("count"),
            FeedSentiments.sentiment_key.label("max_sentiment_column"),
        )
        .join(
            FeedSentiments,
            (Feeds.id == FeedSentiments.feed_id) & (FeedSentiments.model_id == 1),
            isouter=True,
        )
        .where(Feeds.published.between(start_date, end_date))
        .group_by(group_by, FeedSentiments.sentiment_key)
        .order_by(order_by)
    )

    # Apply additional filters if present
    if words:
        query = query.where(Feeds.words.op("@>")(words))
    if free_text:
        query = query.where(func.lower(Feeds.title).ilike(f"%{free_text.lower()}%"))

    raw_results = db.execute(query).all()
    results = generate_sentiment_by_source_series(raw_results)

    return results


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
