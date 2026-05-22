"""Tests for parser, formatter, and calendar event creation changes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.services.calendar_service import CalendarService
from app.services.parser_service import ParserService, ParsedEvent
from app.utils.formatters import (
    _event_end_datetime,
    _format_time_range,
    format_event,
    format_numbered_event,
)

TZ = "Asia/Manila"
TZ_INFO = ZoneInfo(TZ)


@pytest.fixture
def parser() -> ParserService:
    return ParserService(timezone=TZ)


@pytest.fixture
def calendar_service() -> CalendarService:
    auth = MagicMock()
    auth.get_credentials.return_value = MagicMock()
    return CalendarService(auth_service=auth, timezone=TZ)


# ── Parser: parse_event_text ──────────────────────────────────────────


class TestParseEventText:
    def test_single_date_match(self, parser: ParserService):
        result = parser.parse_event_text("Meeting tomorrow at 3pm")
        assert result is not None
        assert result.title == "Meeting"
        assert result.start_time is not None
        assert result.end_time is None

    def test_no_date_match(self, parser: ParserService):
        result = parser.parse_event_text("Just a reminder")
        assert result is None

    def test_empty_text(self, parser: ParserService):
        assert parser.parse_event_text("") is None
        assert parser.parse_event_text("   ") is None

    def test_end_time_from_second_date_match(self, parser: ParserService):
        result = parser.parse_event_text("Meeting 3pm to 5pm tomorrow")
        assert result is not None
        assert result.title == "Meeting"
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.end_time > result.start_time

    def test_end_time_from_duration_hours(self, parser: ParserService):
        result = parser.parse_event_text("Workshop tomorrow at 10am for 2 hours")
        assert result is not None
        assert result.title == "Workshop"
        expected = result.start_time + timedelta(hours=2)
        assert result.end_time == expected

    def test_end_time_from_duration_minutes(self, parser: ParserService):
        result = parser.parse_event_text("Sync tomorrow at 2pm for 90 minutes")
        assert result is not None
        assert result.title == "Sync"
        expected = result.start_time + timedelta(minutes=90)
        assert result.end_time == expected

    def test_duration_1h30m_format(self, parser: ParserService):
        result = parser.parse_event_text("Review tomorrow at 9am 1h30m")
        assert result is not None
        expected = result.start_time + timedelta(hours=1, minutes=30)
        assert result.end_time == expected

    def test_title_fallback_to_original(self, parser: ParserService):
        result = parser.parse_event_text("tomorrow at 3pm")
        assert result is not None
        assert result.title == "tomorrow at 3pm"

    def test_cleans_junk_words_from_title(self, parser: ParserService):
        result = parser.parse_event_text("Meeting tomorrow from 3pm to 5pm")
        assert result is not None
        assert result.title == "Meeting"
        assert result.end_time is not None


# ── Parser: parse_datetime ────────────────────────────────────────────


class TestParseDatetime:
    def test_valid_date(self, parser: ParserService):
        dt = parser.parse_datetime("tomorrow at 3pm")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_invalid_date(self, parser: ParserService):
        assert parser.parse_datetime("not a date") is None

    def test_empty(self, parser: ParserService):
        assert parser.parse_datetime("") is None
        assert parser.parse_datetime("   ") is None


# ── Formatters ────────────────────────────────────────────────────────


class TestFormatTimeRange:
    def test_same_day(self):
        start = datetime(2026, 5, 22, 9, 0, tzinfo=TZ_INFO)
        end = datetime(2026, 5, 22, 10, 0, tzinfo=TZ_INFO)
        result = _format_time_range(start, end)
        assert "2026-05-22" in result
        assert "09:00" in result or "9:00" in result
        assert "10:00" in result
        assert result.count("2026-05-22") == 1

    def test_no_end(self):
        start = datetime(2026, 5, 22, 9, 0, tzinfo=TZ_INFO)
        result = _format_time_range(start, None)
        assert "2026-05-22" in result
        assert "09:00" in result or "9:00" in result

    def test_different_days(self):
        start = datetime(2026, 5, 22, 22, 0, tzinfo=TZ_INFO)
        end = datetime(2026, 5, 23, 1, 0, tzinfo=TZ_INFO)
        result = _format_time_range(start, end)
        assert result.count("2026-05-22") == 1
        assert result.count("2026-05-23") == 1


FAKE_EVENT = {
    "summary": "Test Event",
    "start": {"dateTime": "2026-05-22T09:00:00+08:00", "timeZone": "Asia/Manila"},
    "end": {"dateTime": "2026-05-22T10:00:00+08:00", "timeZone": "Asia/Manila"},
}

FAKE_EVENT_NO_END = {
    "summary": "No End",
    "start": {"dateTime": "2026-05-22T09:00:00+08:00", "timeZone": "Asia/Manila"},
}

FAKE_EVENT_NO_TIME = {
    "summary": "All Day",
    "start": {"date": "2026-05-22"},
    "end": {"date": "2026-05-23"},
}


class TestFormatEvent:
    def test_with_end_time(self):
        result = format_event(FAKE_EVENT, TZ)
        assert "Test Event" in result
        assert "09:00" in result or "9:00" in result
        assert "10:00" in result

    def test_without_end_time(self):
        result = format_event(FAKE_EVENT_NO_END, TZ)
        assert "No End" in result
        assert "09:00" in result or "9:00" in result

    def test_no_start_time(self):
        result = format_event({"summary": "Broken"}, TZ)
        assert "Broken" in result
        assert "time unavailable" in result


class TestFormatNumberedEvent:
    def test_with_end_time(self):
        result = format_numbered_event(1, FAKE_EVENT, TZ)
        assert result.startswith("1.")
        assert "Test Event" in result
        assert "10:00" in result

    def test_without_end_time(self):
        result = format_numbered_event(2, FAKE_EVENT_NO_END, TZ)
        assert result.startswith("2.")
        assert "No End" in result

    def test_no_start_time(self):
        result = format_numbered_event(3, {"summary": "Broken"}, TZ)
        assert "time unavailable" in result


# ── CalendarService: create_event ─────────────────────────────────────


class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_with_end_time(self, calendar_service: CalendarService):
        start = datetime(2026, 5, 22, 14, 0, tzinfo=TZ_INFO)
        end = datetime(2026, 5, 22, 15, 30, tzinfo=TZ_INFO)

        mock_service = MagicMock()
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "abc123",
            "summary": "Test",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        calendar_service._get_service = MagicMock(return_value=mock_service)

        result = await calendar_service.create_event("123", "Test", start, end_time=end)
        assert result["id"] == "abc123"

    @pytest.mark.asyncio
    async def test_defaults_to_60_minutes(self, calendar_service: CalendarService):
        start = datetime(2026, 5, 22, 14, 0, tzinfo=TZ_INFO)

        captured = {}

        def capture_insert(**kwargs):
            captured.update(kwargs)
            mock_req = MagicMock()
            mock_req.execute.return_value = {"id": "x"}
            return mock_req

        mock_service = MagicMock()
        mock_service.events.return_value.insert = capture_insert
        calendar_service._get_service = MagicMock(return_value=mock_service)

        await calendar_service.create_event("123", "Test", start)

        body = captured["body"]
        expected_end = start + timedelta(minutes=60)
        assert body["end"]["dateTime"] == expected_end.isoformat()
