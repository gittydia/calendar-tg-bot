"""Natural language parsing service for event text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from dateparser import parse as parse_date
from dateparser.search import search_dates


DURATION_RE = re.compile(
    r"(?:for\s+)?(\d+)\s*(?:hours?|hrs?)\b"
    r"|(?:for\s+)?(\d+)\s*(?:minutes?|mins?)\b"
    r"|(\d+)[hH]\s*(\d+)[mM]",
    re.IGNORECASE,
)

_DURATION_LIKE_RE = re.compile(
    r"\d+\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b",
    re.IGNORECASE,
)

JUNK_WORDS_RE = re.compile(r"\b(?:from|to|until|at|on|for)\b", re.IGNORECASE)

_NON_DATE_WORDS = frozenset({
    "from", "to", "until", "by", "after", "before",
    "at", "on", "in", "and", "or", "for", "this",
})


@dataclass(frozen=True)
class ParsedEvent:
    """Represents parsed event details extracted from user input."""

    title: str
    start_time: datetime
    end_time: datetime | None = None


class ParserService:
    """Parses natural language into event summary and datetime."""

    def __init__(self, timezone: str) -> None:
        self._timezone = timezone

    def parse_event_text(self, raw_text: str) -> ParsedEvent | None:
        """Extract event title and datetime from a natural language sentence."""
        cleaned = raw_text.strip()
        if not cleaned:
            return None

        raw_matches = search_dates(
            cleaned,
            settings={
                "TIMEZONE": self._timezone,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
            },
        )
        if not raw_matches:
            return None

        matches = [
            (t, dt)
            for t, dt in raw_matches
            if t.strip().lower() not in _NON_DATE_WORDS
            and not _DURATION_LIKE_RE.fullmatch(t.strip())
        ]
        if not matches:
            return None

        title = cleaned
        for matched_text, _ in matches:
            title = title.replace(matched_text, "", 1)
        for dur_match in DURATION_RE.finditer(cleaned):
            title = title.replace(dur_match.group(0), "")
        title = JUNK_WORDS_RE.sub("", title).strip(" ,.-")
        title = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", "", title, flags=re.IGNORECASE).strip(" ,.-")
        if not title:
            title = cleaned

        start_time = matches[0][1]
        end_time: datetime | None = None

        if len(matches) >= 2:
            end_time = matches[-1][1]
        else:
            dur_matches = DURATION_RE.findall(cleaned)
            if dur_matches:
                total_minutes = 0
                for g in dur_matches:
                    if g[0]:
                        total_minutes += int(g[0]) * 60
                    elif g[1]:
                        total_minutes += int(g[1])
                    elif g[2]:
                        total_minutes += int(g[2]) * 60
                        if g[3]:
                            total_minutes += int(g[3])
                end_time = start_time + timedelta(minutes=total_minutes)

        return ParsedEvent(title=title, start_time=start_time, end_time=end_time)

    def parse_datetime(self, text: str) -> datetime | None:
        """Parse a single date/time string into a timezone-aware datetime."""
        cleaned = text.strip()
        if not cleaned:
            return None
        return parse_date(
            cleaned,
            settings={
                "TIMEZONE": self._timezone,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
            },
        )
