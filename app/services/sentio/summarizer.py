from app.services.sentio.prompts import build_headline_summary_prompt
from config import OPENAI_API_KEY


def summarize_headlines_with_ai(
    query: str,
    window_hours: int,
    headlines: list[str],
    prompt: str | None = None,
) -> str | None:
    """Generate a concise summary of the supplied headlines."""
    if not headlines:
        return None

    if not OPENAI_API_KEY:
        return None

    from app.services.ai_assistant import OpenAIAssistant

    return OpenAIAssistant(api_key=OPENAI_API_KEY).send_message(
        build_headline_summary_prompt(
            query=query,
            window_hours=window_hours,
            headlines=headlines,
            prompt=prompt,
        )
    )
