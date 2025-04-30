from collections import defaultdict


def to_dict(obj):
    """Converts an SQLAlchemy ORM object to a dictionary."""
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


def generate_sentiment_by_source_series(input_data) -> dict:
    """
    Organizes sentiment data by source
        and aggregates values into separate lists for negative, neutral, and positive sentiments.

    :param input_data: List of tuples (source, value, sentiment)
    :return: Dictionary containing lists of values for each sentiment category.
    """

    sentiment_data: defaultdict = defaultdict(lambda: defaultdict(list))

    # Categorize data by sentiment type
    for key, value, sentiment in input_data:
        sentiment_data[sentiment][key].append(value)

    # Prepare final structured output
    series_data: dict = {"Negative": [], "Neutral": [], "Positive": []}
    all_keys = sorted(
        set(key for sentiment in sentiment_data.values() for key in sentiment)
    )

    for key in all_keys:
        series_data["Negative"].extend(sentiment_data["negative"].get(key, [0]))
        series_data["Neutral"].extend(sentiment_data["neutral"].get(key, [0]))
        series_data["Positive"].extend(sentiment_data["positive"].get(key, [0]))

    return series_data
