import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from http import HTTPStatus
from typing import List, Optional

import httpx

# import requests  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, Query
from nltk.corpus import stopwords
from palzlib.database.db_client import DBClient
from palzlib.database.db_mapper import DBMapper
from palzlib.sentiment_analyzers.factory.sentiment_factory import (
    SentimentAnalyzerFactory,
)
from palzlib.sentiment_analyzers.models.sentiments import (
    LABEL_MAPPING_ROBERTA,
    Sentiments,
)
from sqlalchemy import and_, asc, case, func, or_, select, text
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

import config
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
FeedCategories = db_mapper.get_model("feed_categories")

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

@router.get("/raw_data")
async def raw_data(
    sources: Optional[List[int]] = Query(None),
    free_text: Optional[str] = Query(None),
    category_id: Optional[List[int]] = Query(None),
    page: int = 1,
    items_per_page: int = 30,
    db: Session = Depends(db_client.get_session),
):
    filters = FeedDBFilters(
        sources=sources or [],
        free_text=free_text or "",
    )
    filters.Feed = Feeds

    query = (
        db.query(Feeds, FeedSentiments, Sources, FeedCategories)
        .join(
            FeedSentiments,
            and_(FeedSentiments.feed_id == Feeds.id, FeedSentiments.model_id == 1),
        )
        .join(Sources, Feeds.source_id == Sources.id)
        .join(FeedCategories, Feeds.category_id == FeedCategories.id)
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
                "feed_categories": to_dict(category),
            }
            for feed, sentiment, source, category in results
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
            Feeds.published,
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


@router.get("/top_feeds")
async def top_feeds(
    start_date: str,
    end_date: str,
    pos_neg: str = "positive",
    limit: int = 5,
    db: Session = Depends(db_client.get_session),
):
    query = (
        db.query(
            Feeds.title,
            Feeds.published,
            Sources.name,
            FeedSentiments.sentiment_value,
            FeedSentiments.sentiment_compound,
        )
        .join(Feeds, FeedSentiments.feed_id == Feeds.id)
        .join(Sources, Feeds.source_id == Sources.id)
        .filter(
            Feeds.feed_date.between(start_date, end_date),
            FeedSentiments.sentiment_key == pos_neg.lower(),
        )
        .order_by(FeedSentiments.sentiment_value.desc())
        .limit(limit)
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


@router.get("/correlation_between_sources_avg_compound")
async def correlation_between_sources_avg_compound(
    start_date: str,
    end_date: str,
    words: List[str] = Query(None),
    sources: List[str] = Query(None),
    db: Session = Depends(db_client.get_session),
):
    sql = text(
        """
        SELECT
            s.name AS sourcename,
            date_trunc('month', f.published)::date AS month,
            AVG(fs.sentiment_compound) AS avg_compound
        FROM feeds AS f
        LEFT JOIN feed_sentiments AS fs ON f.id = fs.feed_id
        LEFT JOIN sources AS s ON f.source_id = s.id
        WHERE f.search_vector @@ to_tsquery('hungarian', :tsquery)
        AND f.published BETWEEN :start_date AND :end_date
        AND (:source_ids IS NULL OR f.source_id = ANY(:source_ids))
        GROUP BY s.name, month
        ORDER BY s.name, month;
        """
    )

    result = db.execute(
        sql,
        {
            "start_date": f"{start_date} 00:00:00",
            "end_date": f"{end_date} 23:59:59",
            "words_array": ",".join(words),
            "tsquery": " | ".join(words),
            "source_ids": sources if sources else None,
        },
    )

    rows = result.mappings().fetchall()
    return rows


@router.get("/correlation_between_sources")
async def correlation_between_sources(
    start_date: str,
    end_date: str,
    words: List[str] = Query(None),
    db: Session = Depends(db_client.get_session),
):

    sql = text(
        """
        SELECT
            word,
            s.name as sourcename,
            min(fs.sentiment_compound) AS min_compound,
            max(fs.sentiment_compound) AS max_compound,
            AVG(fs.sentiment_compound) AS avg_compound,
            -- Positive Sentiments
            sum(CASE WHEN fs.sentiment_key = 'positive' THEN 1 ELSE 0 END) AS nm_of_positive,
            MAX(CASE WHEN fs.sentiment_key = 'positive' THEN sentiment_value END) AS max_positive,
            MIN(CASE WHEN fs.sentiment_key = 'positive' THEN sentiment_value END) AS min_positive,
            AVG(CASE WHEN fs.sentiment_key = 'positive' THEN sentiment_value END) AS avg_positive,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY CASE WHEN fs.sentiment_key = 'positive'
                THEN sentiment_value END) AS median_positive,
            -- Negative Sentiments
            sum(CASE WHEN fs.sentiment_key = 'negative' THEN 1 ELSE 0 END) AS nm_of_negative,
            MAX(CASE WHEN fs.sentiment_key = 'negative' THEN sentiment_value END) AS max_negative,
            MIN(CASE WHEN fs.sentiment_key = 'negative' THEN sentiment_value END) AS min_negative,
            AVG(CASE WHEN fs.sentiment_key = 'negative' THEN sentiment_value END) AS avg_negative,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY CASE WHEN fs.sentiment_key = 'negative'
                THEN sentiment_value END) AS median_negative,
            -- Neutral Sentiments
            sum(CASE WHEN fs.sentiment_key = 'neutral' THEN 1 ELSE 0 END) AS nm_of_neutral,
            MAX(CASE WHEN fs.sentiment_key = 'neutral' THEN sentiment_value END) AS max_neutral,
            MIN(CASE WHEN fs.sentiment_key = 'neutral' THEN sentiment_value END) AS min_neutral,
            AVG(CASE WHEN fs.sentiment_key = 'neutral' THEN sentiment_value END) AS avg_neutral,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY CASE WHEN fs.sentiment_key = 'neutral'
                THEN sentiment_value END) AS median_neutral
        FROM feeds AS f
        LEFT JOIN feed_sentiments AS fs ON f.id = fs.feed_id
        LEFT JOIN sources AS s ON f.source_id = s.id
        LEFT JOIN LATERAL unnest(string_to_array(:words_array, ',')) AS word ON true
        WHERE f.search_vector @@ to_tsquery('hungarian', :tsquery)
        AND f.published BETWEEN :start_date AND :end_date
        GROUP BY word, s.name
        ORDER BY word, s.name;
    """
    )

    result = db.execute(
        sql,
        {
            "start_date": f"{start_date} 00:00:00",
            "end_date": f"{end_date} 23:59:59",
            "words_array": ",".join(words),
            "tsquery": " | ".join(words),
        },
    )

    rows = result.mappings().fetchall()
    return rows


# analyzer_hun = SentimentAnalyzerFactory.get_analyzer("hun")
executor = ThreadPoolExecutor(max_workers=4)


@router.get("/word_co_occurences")
async def word_co_occurences(
    start_date: str,
    end_date: str,
    word: str,
    sources: Optional[List[int]] = Query(None),
    db: Session = Depends(db_client.get_session),
):
    if not word:
        raise HTTPException(status_code=404, detail="Word parameter is required")

    sql = text(
        """
            WITH target_articles AS (
              SELECT f.id, f.words
              FROM feeds f
              WHERE :word = ANY(
                SELECT w FROM unnest(f.words) AS w
              )
                AND f.published BETWEEN :start_date AND :end_date
                AND (:source_ids IS NULL OR f.source_id = ANY(:source_ids))
            ),
            co_words AS (
              SELECT ta.id AS feed_id, w AS co_word
              FROM target_articles ta,
                   unnest(ta.words) AS w
              WHERE w <> :word
            ),
            sentiments AS (
              SELECT feed_id,
                     COUNT(*) FILTER (WHERE sentiment_key = 'positive') AS pos_count,
                     COUNT(*) FILTER (WHERE sentiment_key = 'negative') AS neg_count,
                     COUNT(*) FILTER (WHERE sentiment_key = 'neutral') AS neu_count
              FROM feed_sentiments
              GROUP BY feed_id
            )
            SELECT
              cw.co_word,
              COUNT(*) AS co_occurrence,
              COALESCE(SUM(s.pos_count), 0) AS positive_count,
              COALESCE(SUM(s.neg_count), 0) AS negative_count,
              COALESCE(SUM(s.neu_count), 0) AS neutral_count
            FROM co_words cw
            LEFT JOIN sentiments s ON cw.feed_id = s.feed_id
            GROUP BY cw.co_word
            HAVING COUNT(*) > 1
            ORDER BY co_occurrence DESC
            LIMIT 30;

        """
    )

    result = db.execute(
        sql,
        {
            "word": word,
            "start_date": f"{start_date} 00:00:00",
            "end_date": f"{end_date} 23:59:59",
            "source_ids": sources if sources else None,
        },
    )

    rows = result.mappings().fetchall()
    return rows


@router.get("/ondemand_feed_analyse")
async def ondemand_feed_analyse(start_date: str, word: str, lang: str = "hu"):
    if not word:
        raise HTTPException(status_code=404, detail="Word parameter is required")

    url = (
        f"https://newsapi.org/v2/everything?q={word}"
        f"&from={start_date}&sortBy=publishedAt"
        f"&apiKey={config.NEWS_API_KEY}&searchIn=title"
        f"&language={lang}"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        newsapi_result = await client.get(url)

    if newsapi_result.status_code != 200:
        raise HTTPException(
            status_code=newsapi_result.status_code, detail=newsapi_result.text
        )

    feeds = newsapi_result.json().get("articles", [])

    # Use executor to run sentiment analysis in a background thread
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        executor, analyze_with_details_sync, feeds, "hun"
    )

    return results


def analyze_with_details_sync(feeds: list, lang: str) -> List[dict]:
    """
    Synchronously analyzes sentiment for a list of feeds and returns results with metadata.
    """
    analyzer = SentimentAnalyzerFactory.get_analyzer(lang)
    titles = [feed["title"] for feed in feeds]
    predictions = analyzer.pipeline(titles)

    results = []
    for feed, prediction in zip(feeds, predictions):
        sentiments = {
            LABEL_MAPPING_ROBERTA[item["label"]]: round(item["score"], 4)
            for item in prediction
        }
        results.append(
            {
                "title": feed["title"],
                "source": feed["source"]["name"],
                "published": feed["publishedAt"],
                "sentiments": Sentiments(**sentiments).asdict(),
            }
        )

    return results
