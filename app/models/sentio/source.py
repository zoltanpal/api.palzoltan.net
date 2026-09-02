from pydantic import BaseModel


class DetailedSourceResponse(BaseModel):
    name: str
    site_url: str
    current_article_count: int
    category: str | None = None
