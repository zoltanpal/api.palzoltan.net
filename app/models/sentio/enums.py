from enum import Enum


class Intent(str, Enum):
    SUMMARY = "summary"
    REASON = "reason"
    TREND = "trend"
    COMPARISON = "comparison"
    UNKNOWN = "unknown"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SummaryLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MOSTLY_POSITIVE = "mostly_positive"
    MOSTLY_NEGATIVE = "mostly_negative"
    MIXED = "mixed"


class ChangeDirection(str, Enum):
    IMPROVING = "improving"
    WORSENING = "worsening"
    STABLE = "stable"
