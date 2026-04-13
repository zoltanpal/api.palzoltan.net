from app.services.ai_assistant import OpenAIAssistant
from app.services.sentio.prompts import build_headline_summary_prompt
from config import OPENAI_API_KEY

ai_assistant = OpenAIAssistant(api_key=OPENAI_API_KEY)


def summarize_headlines_with_ai(
    query: str,
    window_hours: int,
    headlines: list[str],
    prompt: str | None = None,
) -> str | None:
    """ Uses an AI assistant to generate a summary of the current news coverage based on recent headlines. """
    if not headlines:
        return None

    return ai_assistant.send_message(
        build_headline_summary_prompt(
            query=query,
            window_hours=window_hours,
            headlines=headlines,
            prompt=prompt,
        )
    )
