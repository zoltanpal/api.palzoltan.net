import json
import re
from typing import Any

from app.models.sentio import Intent, ParsedQuery
from app.services.ai_assistant import OpenAIAssistant
from app.services.sentio.analytics import DEFAULT_WINDOW_HOURS, normalize_window
from app.services.sentio.prompts import build_extractor_prompt
from config import OPENAI_API_KEY

ai_assistant = OpenAIAssistant(api_key=OPENAI_API_KEY)


def parse_llm_json(text: str) -> dict[str, Any]:
    """ Parses the LLM response, extracting JSON content. Handles both raw JSON and fenced code blocks."""
    if not text:
        raise ValueError("LLM returned empty response")

    raw_text = text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_text, re.DOTALL)

    if fenced_match:
        raw_text = fenced_match.group(1).strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON returned by LLM: {exc}") from exc


def parse_user_query_with_ai(user_input: str) -> ParsedQuery:
    """ Uses an AI assistant to parse the user's natural language query into a structured format."""
    response_text = ai_assistant.send_message(build_extractor_prompt(user_input))

    if not response_text:
        return ParsedQuery(
            query=None,
            window_hours=DEFAULT_WINDOW_HOURS,
            intent=Intent.unknown,
        )

    parsed = ParsedQuery(**parse_llm_json(response_text))
    normalized_window = normalize_window(parsed.window_hours)

    if not parsed.query:
        return ParsedQuery(
            query=None,
            window_hours=normalized_window,
            intent=Intent.unknown,
        )

    parsed.window_hours = normalized_window
    return parsed
