from http import HTTPStatus
from typing import Dict, List
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from palzlib.sentiment_analyzers.factory.sentiment_factory import (
    SentimentAnalyzerFactory,
)
from pydantic import BaseModel
from starlette.responses import JSONResponse

from config import NEWS_API_KEY
from libs.auth.bearer_token import BearerAuth

router = APIRouter(
    prefix="/sentiment_analyzer",
    tags=["sentiment_analyzer"],
    dependencies=[Depends(BearerAuth())],
)


class InputData(BaseModel):
    """Schema for input data used in sentiment analysis.

    Defines the input data required for text analysis,
    including the language and the text itself.
    """

    lang: str
    text: str


# Storing the jobs' results of the text sentiment analysis
JOB_RESULTS: Dict[str, Dict] = {}


@router.get("/start_analysis")
async def start_analysis(
    start_date: str,
    word: str,
    lang: str = "hu",
    background_tasks: BackgroundTasks = None,
):
    """
    Starts sentiment analysis on articles fetched from NewsAPI for a given word and language.
    Returns the first page of results while continuing analysis in the background.

    Args:
        start_date (str): Date to start fetching articles from.
        word (str): Search keyword.
        lang (str): Language code (default: "hu").
        background_tasks (BackgroundTasks): Optional background task manager.

    Returns:
        dict: Paginated sentiment analysis results (first page).
    """
    if not word:
        raise HTTPException(status_code=404, detail="Word parameter is required")

    url = (
        f"https://newsapi.org/v2/everything?q={word}"
        f"&from={start_date}&sortBy=publishedAt"
        f"&apiKey={NEWS_API_KEY}&searchIn=title"
        f"&language={lang}"
    )

    # Fetch articles from NewsAPI
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
    feeds = response.json().get("articles", [])

    # Initialize job and store feeds in a dict
    job_id = str(uuid4())
    JOB_RESULTS[job_id] = {
        "feeds": feeds,
        "results": [None] * len(feeds),
        "completed": 0,
        "total": len(feeds),
    }

    # Launch background chunked analysis
    if background_tasks:
        background_tasks.add_task(background_chunked_analysis, job_id)

    # Return results by page
    return get_result_page(job_id, page=0, page_size=50)


def background_chunked_analysis(job_id: str, lang: str = "hun"):
    """
    Performs sentiment analysis in chunks in the background and updates JOB_RESULTS.

    Args:
        job_id (str): ID of the sentiment analysis job.
        lang (str): Language code for the analyzer.
    """

    analyzer = SentimentAnalyzerFactory.get_analyzer(lang)
    feeds = JOB_RESULTS[job_id]["feeds"]
    chunk_size = 50

    for i in range(0, len(feeds), chunk_size):
        titles = [f["title"] for f in feeds[i : i + chunk_size]]
        sentiments_list = analyzer.analyze_batch(titles)
        for j, sentiment_obj in enumerate(sentiments_list):
            JOB_RESULTS[job_id]["results"][i + j] = sentiment_obj.asdict()
            JOB_RESULTS[job_id]["completed"] += 1


@router.get("/results/{job_id}")
def get_result_page(job_id: str, page: int = 0, page_size: int = 50):
    """
    Returns a paginated page of sentiment analysis results for a specific job.

    Args:
        job_id (str): Job ID to retrieve results for.
        page (int): Page number (default: 0).
        page_size (int): Number of results per page (default: 50).

    Returns:
        dict: Paginated list of analyzed articles with sentiment scores.
    """
    job = JOB_RESULTS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    start = page * page_size
    end = start + page_size
    page_data: List[dict] = []

    for i in range(start, min(end, len(job["feeds"]))):
        feed = job["feeds"][i]
        sentiments = job["results"][i]
        page_data.append(
            {
                "title": feed["title"],
                "source": feed.get("source", {}).get("name"),
                "published": feed.get("publishedAt"),
                "sentiments": sentiments,  # Can be None if still processing
            }
        )

    return {
        "job_id": job_id,
        "page": page,
        "page_size": page_size,
        "total": job["total"],
        "completed": job["completed"],
        "results": page_data,
    }


@router.post("/analyze_text", status_code=HTTPStatus.OK)
async def analyze_text(item: InputData):
    analyzer = SentimentAnalyzerFactory.get_analyzer(item.lang)
    result = analyzer.analyze_text(item.text)

    return JSONResponse(status_code=200, content=result.asdict())
