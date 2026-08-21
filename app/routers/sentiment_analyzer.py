from http import HTTPStatus
from typing import Any, Dict, List
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed

import re
import json
import feedparser
import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from starlette.responses import JSONResponse

from config import pow_db_config, pow_live_db_config, OPENAI_API_KEY
from app.services.ai_assistant import OpenAIAssistant
from palzlib_db.db_client import DBClient
from palzlib_db.db_mapper import DBMapper
from sentiment_analyzer.factory.sentiment_factory import SentimentAnalyzerFactory
# from app.utils.auth.bearer_token import BearerAuth

def parse_llm_json(text: str):
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)  # fallback if already clean


router = APIRouter(
    prefix="/sentiment_analyzer",
    tags=["sentiment_analyzer"],
    # dependencies=[Depends(BearerAuth())],
)

ai_assistant = OpenAIAssistant(api_key=OPENAI_API_KEY)


db_client = DBClient(db_config=pow_db_config)
db_mapping = DBMapper(db_client=db_client)

live_db_client = DBClient(db_config=pow_live_db_config)
live_db_mapping = DBMapper(db_client=live_db_client)

JOB_RESULTS: Dict[str, Dict[str, Any]] = {}

RSS_FETCH_TIMEOUT = 10
RSS_FETCH_WORKERS = 10
ANALYSIS_CHUNK_SIZE = 50
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class InputData(BaseModel):
    lang: str
    text: str


def fetch_single_rss(
    rss_url: str,
    rss_to_source: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fetch a single RSS feed and return normalized entries.
    """
    results: List[Dict[str, Any]] = []

    if not rss_url:
        return results

    try:
        response = requests.get(rss_url, timeout=RSS_FETCH_TIMEOUT)
        response.raise_for_status()

        parsed = feedparser.parse(response.content)
        source = rss_to_source.get(rss_url, {})

        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            published = (
                entry.get("published")
                or entry.get("updated")
                or entry.get("pubDate")
                or None
            )

            if not title:
                continue

            results.append(
                {
                    "title": title,
                    "link": link,
                    "published": published,
                    "rss_url": rss_url,
                    "source_id": source.get("id"),
                    "source_name": source.get("name"),
                    "source_web": source.get("web"),
                }
            )

    except Exception as exc:
        print(f"Failed to fetch RSS {rss_url}: {exc}")

    return results


def fetch_rss_news(
    rss_links: List[str],
    rss_to_source: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fetch all RSS feeds concurrently and deduplicate by link/title.
    """
    all_items: List[Dict[str, Any]] = []
    unique_links = list({link for link in rss_links if link})

    with ThreadPoolExecutor(max_workers=RSS_FETCH_WORKERS) as executor:
        futures = {
            executor.submit(fetch_single_rss, link, rss_to_source): link
            for link in unique_links
        }

        for future in as_completed(futures):
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as exc:
                print(f"RSS future failed: {exc}")

    seen = set()
    deduped: List[Dict[str, Any]] = []

    for item in all_items:
        dedupe_key = item.get("link") or item.get("title")
        if not dedupe_key:
            continue
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        deduped.append(item)

    return deduped


def build_result_response(
    job_id: str,
    page: int = 0,
    page_size: int = DEFAULT_PAGE_SIZE,
    include_all: bool = False,
) -> Dict[str, Any]:
    """
    Return either a paginated result set or all items for a job.
    """
    if job_id not in JOB_RESULTS:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOB_RESULTS[job_id]

    if include_all:
        page = 0
        page_size = job["total"]
    else:
        if page < 0:
            page = 0

        if page_size < 1:
            page_size = DEFAULT_PAGE_SIZE

        page_size = min(page_size, MAX_PAGE_SIZE)

    start = page * page_size
    end = start + page_size

    paged_feeds = job["feeds"][start:end]
    paged_results = job["results"][start:end]

    items = [
        {
            "feed": feed,
            "sentiment": result,
        }
        for feed, result in zip(paged_feeds, paged_results)
    ]

    return {
        "job_id": job_id,
        "status": job["status"],
        "completed": job["completed"],
        "total": job["total"],
        "page": page,
        "page_size": page_size,
        "error": job.get("error"),
        "items": items,
    }


def background_chunked_analysis(job_id: str, lang: str = "hun") -> None:
    """
    Perform sentiment analysis in chunks and update JOB_RESULTS in memory.
    """
    try:
        analyzer = SentimentAnalyzerFactory.get_analyzer(lang)
        feeds = JOB_RESULTS[job_id]["feeds"]

        for i in range(0, len(feeds), ANALYSIS_CHUNK_SIZE):
            chunk = feeds[i : i + ANALYSIS_CHUNK_SIZE]
            titles = [feed["title"] for feed in chunk]

            sentiments_list = analyzer.analyze_batch(titles)

            for j, sentiment_obj in enumerate(sentiments_list):
                JOB_RESULTS[job_id]["results"][i + j] = sentiment_obj.asdict()
                JOB_RESULTS[job_id]["completed"] += 1

        JOB_RESULTS[job_id]["status"] = "completed"

    except Exception as exc:
        print(f"Background analysis failed for job {job_id}: {exc}")
        JOB_RESULTS[job_id]["status"] = "failed"
        JOB_RESULTS[job_id]["error"] = str(exc)


@router.get("/start_analysis")
async def start_analysis(
    background_tasks: BackgroundTasks,
    lang: str = Query(default="hun"),
):
    """
    Start RSS fetch + background sentiment analysis.
    Returns only job metadata.
    """
    stmt = text(
        """
        SELECT id, name, web, rss, lang
        FROM sources
        WHERE lang = :lang
          AND rss IS NOT NULL
          AND rss != ''
        """
    )

    with db_client.get_db_session() as session:
        sources = session.execute(stmt, {"lang": lang}).all()

    if not sources:
        raise HTTPException(
            status_code=404,
            detail=f"No RSS sources found for lang='{lang}'",
        )

    rss_links = [row.rss for row in sources if getattr(row, "rss", None)]

    rss_to_source = {
        row.rss: {
            "id": row.id,
            "name": row.name,
            "web": row.web,
        }
        for row in sources
        if getattr(row, "rss", None)
    }

    feeds = fetch_rss_news(rss_links, rss_to_source)

    if not feeds:
        raise HTTPException(status_code=404, detail="No RSS items could be fetched")

    job_id = str(uuid4())

    JOB_RESULTS[job_id] = {
        "status": "running",
        "lang": lang,
        "feeds": feeds,
        "sources": rss_to_source,
        "results": [None] * len(feeds),
        "completed": 0,
        "total": len(feeds),
        "error": None,
    }

    background_tasks.add_task(background_chunked_analysis, job_id, lang)

    return JSONResponse(
        status_code=200,
        content={
            "message": "Analysis started",
            "job_id": job_id,
            "status": "running",
            "completed": 0,
            "total": len(feeds),
            "error": None,
        },
    )


@router.get("/results/{job_id}")
async def get_results(
    job_id: str,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1),
    include_all: bool = Query(default=False),
):
    """
    Get paginated results for a given job, or all results with include_all=true.
    """
    return JSONResponse(
        status_code=200,
        content=build_result_response(
            job_id=job_id,
            page=page,
            page_size=page_size,
            include_all=include_all,
        ),
    )


@router.post("/analyze_text", status_code=HTTPStatus.OK)
async def analyze_text(item: InputData):
    analyzer = SentimentAnalyzerFactory.get_analyzer(item.lang)
    result = analyzer.analyze_text(item.text)
    return JSONResponse(status_code=200, content=result.asdict())



def get_score_label(avg_score: float) -> str:
    """
    Basic sentiment label from the average sentiment score.
    """
    if avg_score >= 0.05:
        return "positive"
    if avg_score <= -0.05:
        return "negative"
    return "neutral"


def get_summary(
    avg_score: float,
    positive_pct: float,
    neutral_pct: float,
    negative_pct: float,
) -> dict:
    """
    Create a more human-friendly summary label using both
    average sentiment score and class distribution.

    Returns:
        {
            "label": "mostly_negative",
            "dominant_label": "negative",
            "dominant_pct": 61.2
        }
    """
    distribution = {
        "positive": positive_pct,
        "neutral": neutral_pct,
        "negative": negative_pct,
    }

    dominant_label = max(distribution, key=distribution.get)
    dominant_pct = distribution[dominant_label]

    # Strong clear dominance
    if dominant_label == "positive" and dominant_pct >= 70 and avg_score >= 0.05:
        summary_label = "positive"
    elif dominant_label == "negative" and dominant_pct >= 70 and avg_score <= -0.05:
        summary_label = "negative"

    # Mostly one-sided
    elif dominant_label == "positive" and dominant_pct >= 55:
        summary_label = "mostly_positive"
    elif dominant_label == "negative" and dominant_pct >= 55:
        summary_label = "mostly_negative"

    # Mostly neutral / neutral
    elif neutral_pct >= 60 and abs(avg_score) < 0.05:
        summary_label = "neutral"

    # Mixed / polarized
    elif positive_pct >= 30 and negative_pct >= 30 and abs(avg_score) < 0.10:
        summary_label = "mixed"

    # Fallback from avg score
    elif avg_score >= 0.05:
        summary_label = "mostly_positive"
    elif avg_score <= -0.05:
        summary_label = "mostly_negative"
    else:
        summary_label = "neutral"

    return {
        "label": summary_label,
        "dominant_label": dominant_label,
        "dominant_pct": round(dominant_pct, 2),
    }


@router.get("/live/analyze", status_code=HTTPStatus.OK)
async def live_analyze(
    query: str = Query(..., min_length=1),
    window_hours: int = Query(6, ge=1, le=168),
):
    with live_db_client.get_db_session() as session:
        stmt = text(
            """
            SELECT
                COUNT(*) AS total_articles,
                COALESCE(AVG(s.sentiment_score), 0) AS avg_sentiment_score,
                COUNT(*) FILTER (WHERE s.sentiment_label = 'positive') AS positive_count,
                COUNT(*) FILTER (WHERE s.sentiment_label = 'neutral')  AS neutral_count,
                COUNT(*) FILTER (WHERE s.sentiment_label = 'negative') AS negative_count
            FROM articles a
            JOIN article_sentiments s
                ON s.article_id = a.id
            WHERE
                a.title_search_vector @@ plainto_tsquery('english', :query)
                AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                AND a.clustered_at IS NOT NULL
            """
        )

        row = session.execute(
            stmt,
            {
                "query": query,
                "window_hours": window_hours,
            },
        ).mappings().one()

    total_articles = row["total_articles"] or 0
    positive_count = row["positive_count"] or 0
    neutral_count = row["neutral_count"] or 0
    negative_count = row["negative_count"] or 0
    avg_sentiment_score = float(row["avg_sentiment_score"] or 0)

    avg_sentiment_label = get_score_label(avg_sentiment_score)

    if total_articles > 0:
        positive_pct = round((positive_count / total_articles) * 100, 2)
        neutral_pct = round((neutral_count / total_articles) * 100, 2)
        negative_pct = round((negative_count / total_articles) * 100, 2)
    else:
        positive_pct = 0.0
        neutral_pct = 0.0
        negative_pct = 0.0

    summary = get_summary(
        avg_score=avg_sentiment_score,
        positive_pct=positive_pct,
        neutral_pct=neutral_pct,
        negative_pct=negative_pct,
    )

    return {
        "query": query,
        "window_hours": window_hours,
        "article_count": total_articles,
        "avg_sentiment": {
            "score": round(avg_sentiment_score, 4),
            "label": avg_sentiment_label,
        },
        "distribution": {
            "positive_count": positive_count,
            "neutral_count": neutral_count,
            "negative_count": negative_count,
            "positive_pct": positive_pct,
            "neutral_pct": neutral_pct,
            "negative_pct": negative_pct,
        },
        "summary": summary,
    }

@router.get("/live/headlines", status_code=HTTPStatus.OK)
async def live_headlines(
    query: str = Query(..., min_length=1),
    window_hours: int = Query(6, ge=1, le=168),
    use_ai: bool = Query(default=False)
):

    prompt_for_extractor = f"""
                You are an input parser for a live news analysis application.
            Your job is to extract structured search information from a user's message.

            You must extract:
            - query: the main searchable company, topic, asset, person, or keyword
            - window_hours: the requested time range in hours
            - intent: the user's goal

            Important rules:
            - Do not answer the user's question.
            - Do not summarize the news.
            - Do not add explanations.
            - Do not use outside knowledge, except to interpret time phrases.
            - Extract only the main searchable topic.
            - Keep the query short and clean.
            - Remove filler phrases such as "what is the market saying about", "tell me about", "show me", "why is", etc.
            - If no time is mentioned, use 24.
            - If the request is unclear, still return the best reasonable extraction.

            Intent values:
            - "summary" = the user wants an overview of current coverage
            - "reason" = the user asks why something is in the news
            - "trend" = the user asks whether tone, sentiment, or coverage is changing
            - "comparison" = the user compares two topics
            - "unknown" = unclear intent

            Time rules that should be applied when interpreting the query. and use these to set the window_hours value:
            - "today" -> 24
            - "yesterday" -> 24
            - "last 6 hours" -> 6
            - "last 12 hours" -> 12
            - "last 24 hours" -> 24
            - "this week" -> 168
            - "last week" -> 168
            - "past week" -> 168
            - "last 2 days" -> 48
            - "last 3 days" -> 72
            If there is no time specified, the default should be 6.
            Return valid JSON only in this exact format:
                "query": "string or null",
                "window_hours": 6,
                "intent": "summary | reason | trend | comparison | unknown"
            User input:
            "{query}"
    """

    if use_ai:
        extractor_response = ai_assistant.send_message(prompt_for_extractor)
        if extractor_response:
            response = parse_llm_json(extractor_response)
            query = response["query"]
            window_hours = response["window_hours"]

    with live_db_client.get_db_session() as session:
        stmt = text(
            """
            SELECT
                a.id, a.title, a.title_hash, a.summary, a.link, a.published_at,
                s."name" as source_name,
                ars.sentiment_label, ars.sentiment_score, ars.sentiment_raw 
            FROM articles a
            JOIN article_sentiments ars ON ars.article_id = a.id
            JOIN sources as s on s.id=a.source_id 
            WHERE
                a.title_search_vector @@ plainto_tsquery('english', :query)
                AND a.published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                AND a.clustered_at IS NOT NULL
            ORDER BY a.published_at DESC
            """
        )

        rows = session.execute(
            stmt,
            {
                "query": query,
                "window_hours": window_hours,
            },
        ).mappings().all()

    ai_summary_text = None
    # If AI summary is requested then use AI to summarize the sentiment of the headlines.
    if use_ai and rows:
        headline_titles = [row["title"] for row in rows]

        prompt = f"""
            These headlines are about {query} topic.
            The headlines are the last {window_hours} hours.
            Please provide a concise summary of the following headlines in 2-3 sentences.
        """

        prompt2 = f"""
	    You are a news analysis assistant.
    	Your task is to summarize the overall story emerging from a set of recent news headlines that were retrieved for a user's search query.
    	Search query: "{query}"
    	Time window: "{window_hours} hours"
    	Below is a set of recent news headlines that matched the search.

    Your task:
    - Write a short summary of what the current coverage is mainly about.
    - Use only the provided headlines.
    - Do not add outside knowledge.
    - Do not speculate beyond what the headlines clearly suggest.
    - If the headlines are mixed, say that clearly.
    - If there are only a few headlines, keep the summary cautious.
    - Keep the output concise and natural.

    Output rules:
    - Return only plain text.
    - Write 2 to 4 sentences.
    - Do not use bullet points.
    - Do not mention sentiment scores, article counts, or percentages.
    - Do not say "based on the headlines" or similar meta wording unless necessar.
	Here are the news headlines:
        """
        ai_summary_text = ai_assistant.send_message(f"{prompt2}\n:{headline_titles}")

    return {
        "query": query,
        "window_hours": window_hours,
        "total_articles": len(rows),
        "headlines": [row for row in rows],
        "ai_summary": ai_summary_text,
    }


@router.get("/live/sentiment_change", status_code=HTTPStatus.OK)
async def sentiment_change(
    query: str = Query(..., min_length=1),
    window_hours: int = Query(6, ge=1, le=168),
):
    with live_db_client.get_db_session() as session:
        stmt = text(
            """
            WITH matched_articles AS (
                SELECT
                    a.id,
                    a.published_at,
                    ars.sentiment_score
                FROM articles a
                JOIN article_sentiments ars ON ars.article_id = a.id
                WHERE
                    a.title_search_vector @@ plainto_tsquery('english', :query)
                    AND a.published_at >= NOW() - (:window_hours * 2 * INTERVAL '1 hour')
            ),
            windowed AS (
                SELECT
                    CASE
                        WHEN published_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            THEN 'current'
                        ELSE 'previous'
                    END AS window_name,
                    sentiment_score
                FROM matched_articles
            )
            SELECT
                window_name,
                COUNT(*) AS article_count,
                COALESCE(AVG(sentiment_score), 0) AS avg_sentiment_score
            FROM windowed
            GROUP BY window_name;
            """
        )

        rows = session.execute(
            stmt,
            {
                "query": query,
                "window_hours": window_hours,
            },
        ).mappings().all()

    current = {
        "article_count": 0,
        "avg_sentiment_score": 0.0,
    }
    previous = {
        "article_count": 0,
        "avg_sentiment_score": 0.0,
    }


    for row in rows:
        payload = {
            "article_count": row["article_count"] or 0,
            "avg_sentiment_score": float(row["avg_sentiment_score"] or 0),
        }
        if row["window_name"] == "current":
            current = payload
        elif row["window_name"] == "previous":
            previous = payload

    delta = current["avg_sentiment_score"] - previous["avg_sentiment_score"]

    if delta > 0.05:
        direction = "improving"
    elif delta < -0.05:
        direction = "worsening"
    else:
        direction = "stable"

    return {
        "query": query,
        "window_hours": window_hours,
        "current": {
            "article_count": current["article_count"],
            "avg_sentiment_score": current["avg_sentiment_score"],
        },
        "previous": {
            "article_count": previous["article_count"],
            "avg_sentiment_score": previous["avg_sentiment_score"],
        },
        "change": {
            "delta": round(delta, 4),
            "direction": direction,
        },
    }

