"""Natural language parsing service for event text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dateparser.search import search_dates


@dataclass(frozen=True)
class ParsedEvent:
    """Represents parsed event details extracted from user input."""

    title: str
    start_time: datetime


class ParserService:
    """Parses natural language into event summary and datetime."""

    def __init__(self, timezone: str) -> None:
        self._timezone = timezone

    def parse_event_text(self, raw_text: str) -> ParsedEvent | None:
        """Extract event title and datetime from a natural language sentence."""
        cleaned = raw_text.strip()
        if not cleaned:
            return None

        matches = search_dates(
            cleaned,
            settings={
                "TIMEZONE": self._timezone,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
            },
        )
        if not matches:
            return None

        matched_text, start_time = matches[0]
        title = cleaned.replace(matched_text, "").strip(" ,.-")
        if not title:
            title = cleaned

        return ParsedEvent(title=title, start_time=start_time)
