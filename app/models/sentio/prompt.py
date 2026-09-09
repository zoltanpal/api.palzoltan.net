from pydantic import BaseModel, Field, field_validator

from app.models.sentio.enums import Intent


class ParsedQuery(BaseModel):
    query: str | None = None
    window_hours: int = Field(6, ge=1, le=168)
    intent: Intent = Intent.UNKNOWN


class PromptResponse(BaseModel):
    prompt: str
    query: str
    window_hours: int
    intent: Intent = Intent.UNKNOWN


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2_000)

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prompt cannot be empty")
        return value


class QueryPromptRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    window_hours: int = Field(6, ge=1, le=168)
    prompt: str | None = Field(default=None, max_length=2_000)
    use_ai: bool = True

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query cannot be empty")
        return value

    @field_validator("prompt")
    @classmethod
    def strip_optional_prompt(cls, value: str | None) -> str | None:
        return value.strip() if value else None
