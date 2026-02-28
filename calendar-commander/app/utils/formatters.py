"""Formatting helpers for Telegram message output."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _event_start_datetime(event: dict, timezone: str) -> datetime | None:
    """Normalize event start payload into timezone-aware datetime."""
    start = event.get("start", {})
    date_time = start.get("dateTime")
    if date_time:
        parsed = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo(timezone))

    date_only = start.get("date")
    if date_only:
        return datetime.fromisoformat(f"{date_only}T00:00:00+00:00").astimezone(
            ZoneInfo(timezone)
        )

    return None


def format_event(event: dict, timezone: str) -> str:
    """Format a single event line item."""
    summary = event.get("summary", "(No title)")
    start_time = _event_start_datetime(event, timezone)
    if start_time is None:
        return f"• {summary} — time unavailable"

    return f"• {start_time.strftime('%Y-%m-%d %I:%M %p')} — {summary}"


def format_numbered_event(index: int, event: dict, timezone: str) -> str:
    """Format a numbered event line for deletion workflow."""
    summary = event.get("summary", "(No title)")
    start_time = _event_start_datetime(event, timezone)
    if start_time is None:
        return f"{index}. {summary} — time unavailable"
    return f"{index}. {start_time.strftime('%Y-%m-%d %I:%M %p')} — {summary}"
