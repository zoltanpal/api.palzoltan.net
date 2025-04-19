from collections import Counter
from datetime import date
from http import HTTPStatus
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from nltk.corpus import stopwords
from palzlib.database.db_client import DBClient
from palzlib.database.db_mapper import DBMapper
from sqlalchemy import and_, asc, case, func, or_, select, text
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
        start_date=str(f"{start_date} 00:00:00"),
        end_date=str(f"{end_date} 23:59:59"),
        words=words or [],
        sources=sources or [],
        free_text=free_text or "",
    )
    filters.Feed = Feeds

    query = (
        db.query(Feeds, FeedSentiments, Sources)
        .join(
            FeedSentiments,
            and_(FeedSentiments.feed_id == Feeds.id, FeedSentiments.model_id == 1),
        )
        .join(Sources, Feeds.source_id == Sources.id)
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
            {
                "feed": to_dict(feed),
                "feed_sentiments": to_dict(sentiment),
                "source": to_dict(source),
            }
            for feed, sentiment, source in results
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
        start_date=str(f"{start_date} 00:00:00"),
        end_date=str(f"{end_date} 23:59:59"),
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
        start_date=str(f"{start_date} 00:00:00"),
        end_date=str(f"{end_date} 23:59:59"),
        sources=sources if sources else [],
    )
    filters.Feed = Feeds

    query = (
        select(
            Feeds.title,
            Sources.name.label("source"),
            func.DATE(Feeds.published),
            FeedSentiments.sentiment_key,
            FeedSentiments.sentiment_value,
            FeedSentiments.sentiment_compound,
        )
        .join(FeedSentiments, FeedSentiments.feed_id == Feeds.id)
        .join(Sources, Feeds.source_id == Sources.id)
        .where(
            or_(
                FeedSentiments.sentiment_value > 0.6,
                FeedSentiments.sentiment_value < -0.6,
            ),
            FeedSentiments.sentiment_key != "neutral",
            filters.conditions,
        )
        .order_by(FeedSentiments.sentiment_value.desc())
    )

    results = db.execute(query).mappings().all()

    return results


@router.get("/bias_detection")
async def bias_detection(
    start_date: str,
    end_date: str,
    words: List[str] = Query(None),
    sources: Optional[List[int]] = Query(None),
    db: Session = Depends(db_client.get_session),
):
    sql = text(
        """
            WITH input_words AS (
            SELECT unnest(:words) AS input_word
        ),
        matched_feeds AS (
            SELECT
                f.id AS feed_id,
                f.source_id,
                f.feed_date,
                s.name AS source_name,
                f.words,
                f.search_vector,
                fs.sentiment_key,
                fs.sentiment_value
            FROM feeds f
            JOIN feed_sentiments fs ON fs.feed_id = f.id
            JOIN sources s ON f.source_id = s.id
            WHERE
                f.published BETWEEN :start_date AND :end_date
                AND f.search_vector @@ to_tsquery('hungarian', :tsquery)
        ),
        word_match AS (
            SELECT
                mf.source_name,
                iw.input_word,
                mf.sentiment_key,
                mf.sentiment_value
            FROM matched_feeds mf
            JOIN input_words iw
                ON EXISTS (
                    SELECT 1
                    FROM unnest(mf.words) w
                    WHERE w ILIKE iw.input_word || '%'
                )
        )
        SELECT
            source_name,
            input_word AS keyword,
            COUNT(*) AS mention_count,
            -- Net Sentiment Score (Bias Indicator)
            (SUM(CASE WHEN sentiment_key = 'positive' THEN sentiment_value ELSE 0 END) -
             SUM(CASE WHEN sentiment_key = 'negative' THEN sentiment_value ELSE 0 END))
            / NULLIF(COUNT(*), 0) AS net_sentiment_score,
             ROUND(COALESCE(STDDEV(sentiment_value)::NUMERIC, 0), 2) AS sentiment_std_dev

        FROM word_match
        GROUP BY source_name, input_word
        ORDER BY input_word, net_sentiment_score DESC;
    """
    )

    # Create to_tsquery-compatible string from words
    tsquery_string = " | ".join(words)
    result = db.execute(
        sql,
        {
            "words": words,
            "start_date": f"{start_date} 00:00:00",
            "end_date": f"{end_date} 23:59:59",
            "tsquery": tsquery_string,
        },
    )

    rows = result.mappings().fetchall()
    return rows
