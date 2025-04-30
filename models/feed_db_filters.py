from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import and_


@dataclass
class FeedDBFilters:
    one_week_ago: str = field(
        default_factory=lambda: (datetime.now() - timedelta(days=7)).strftime(
            "%Y-%m-%d 00:00:00"
        )
    )
    Feed = None  # Expected to be assigned externally
    words: List[str] = field(default_factory=list)
    sources: List[int] = field(default_factory=list)
    start_date: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d 00:00:00")
    )
    end_date: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d 23:59:59")
    )
    free_text: str = ""
    selected_words: List[str] = field(default_factory=list)

    def generate_conditions(self):
        if not self.Feed:
            raise ValueError(
                "Feed model must be assigned before generating conditions."
            )

        conditions = []

        if self.start_date:
            conditions.append(self.Feed.published >= self.start_date)
        if self.end_date:
            conditions.append(self.Feed.published <= self.end_date)
        if self.words:
            words_cond = [word.lower().strip() for word in self.words]
            conditions.append(self.Feed.words.contains(words_cond))
        if self.sources:
            conditions.append(self.Feed.source_id.in_(self.sources))
        if self.free_text:
            conditions.append(self.Feed.title.ilike(f"%{self.free_text}%"))

        return and_(*conditions) if conditions else None

    @property
    def conditions(self):
        return self.generate_conditions()

    @property
    def conditions_dict(self) -> Dict[str, Optional[str]]:
        return {
            field_.name: getattr(self, field_.name)
            for field_ in fields(self)
            if getattr(self, field_.name)
        }

    def process_args(self, args: dict):
        self.start_date = args.get("start_date") or self.start_date
        self.end_date = args.get("end_date") or self.end_date

        if sources := args.get("sources"):
            self.sources = list(map(int, sources.split(",")))

        if words := args.get("words"):
            self.words = words.split(",")
            self.selected_words.extend(self.words)

        if free_text := args.get("free_text"):
            self.free_text = free_text
            self.selected_words.append(self.free_text)
