
def build_extractor_prompt(user_input: str) -> str:
    return f"""
You are an input parser for a live news analysis application.
Your job is to extract structured search information from a user's message.

You must extract:
- query: the main searchable company, topic, asset, person, or keyword
- window_hours: the requested time range in hours
- intent: the user's goal

Important rules:
- Do not answer the user's question.
- Do not use outside knowledge, except to interpret time phrases.
- Extract only the main searchable topic.
- Keep the query short and clean.
- Remove filler phrases such as "what is the market saying about",
  "tell me about", "show me", "why is", etc.
- If the request is unclear, still return the best reasonable extraction.

Intent values:
- "summary" = the user wants an overview of current coverage
- "reason" = the user asks why something is in the news
- "trend" = the user asks whether tone, sentiment, or coverage is changing
- "comparison" = the user compares two topics
- "unknown" = unclear intent

Time rules:
- "today" -> 24
- "yesterday" -> 24
- "last 6 hours" -> 6
- "last 12 hours" -> 12
- "last 24 hours" -> 24
- "this week" -> 72
- "last week" -> 72
- "past week" -> 72
- "last 2 days" -> 48
- "last 3 days" -> 72
- If there is no time specified, default to 6

Return valid JSON only in this exact format:
{{
  "query": "string or null",
  "window_hours": 6,
  "intent": "summary | reason | trend | comparison | unknown"
}}

User input:
"{user_input}"
""".strip()


def build_headline_summary_prompt(
    query: str,
    window_hours: int,
    headlines: list[str],
    prompt: str | None = None,
) -> str:
    additional_instructions = ""
    if prompt:
        additional_instructions = f"""
The user also provided this prompt: "{prompt.strip()}"
Use this to better understand their intent and what they are looking for,
and focus the summary on what seems most relevant to their underlying question or interest.
"""

    return f"""
You are a professional news analysis assistant.
Your task is to summarize the overall story emerging from a set of recent news
headlines that were retrieved for a user's search query.
{additional_instructions}

Search query: "{query}"
Time window: "{window_hours} hours"

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
- Do not say "based on the headlines" unless necessary.

Here are the headlines:
{chr(10).join(f"- {headline}" for headline in headlines)}
""".strip()
