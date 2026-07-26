"""Formatting helpers for Telegram message output."""

from __future__ import annotations

from datetime import date, datetime
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


def _event_end_datetime(event: dict, timezone: str) -> datetime | None:
    """Normalize event end payload into timezone-aware datetime."""
    end = event.get("end", {})
    date_time = end.get("dateTime")
    if date_time:
        parsed = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo(timezone))

    date_only = end.get("date")
    if date_only:
        return datetime.fromisoformat(f"{date_only}T00:00:00+00:00").astimezone(
            ZoneInfo(timezone)
        )

    return None


def _format_time_range(start_time: datetime, end_time: datetime | None) -> str:
    """Format start/end as a readable time range."""
    if end_time is None:
        return start_time.strftime("%Y-%m-%d %I:%M %p")
    if start_time.date() == end_time.date():
        return f"{start_time.strftime('%Y-%m-%d %I:%M %p')} - {end_time.strftime('%I:%M %p')}"
    return f"{start_time.strftime('%Y-%m-%d %I:%M %p')} - {end_time.strftime('%Y-%m-%d %I:%M %p')}"


def format_event(event: dict, timezone: str) -> str:
    """Format a single event line item."""
    summary = event.get("summary", "(No title)")
    start_time = _event_start_datetime(event, timezone)
    if start_time is None:
        return f"• {summary} — time unavailable"

    end_time = _event_end_datetime(event, timezone)
    return f"• {_format_time_range(start_time, end_time)} — {summary}"


def format_numbered_event(index: int, event: dict, timezone: str) -> str:
    """Format a numbered event line for deletion workflow."""
    summary = event.get("summary", "(No title)")
    start_time = _event_start_datetime(event, timezone)
    if start_time is None:
        return f"{index}. {summary} — time unavailable"

    end_time = _event_end_datetime(event, timezone)
    return f"{index}. {_format_time_range(start_time, end_time)} — {summary}"


def format_task(task: dict) -> str:
    """Format a single task line item."""
    title = task.get("title", "(No title)")
    due = task.get("due")
    if due:
        due_date = datetime.fromisoformat(due.replace("Z", "+00:00"))
        due_str = due_date.strftime("%b %d, %Y")
        return f"• {title} (due {due_str})"
    return f"• {title}"


def format_numbered_task(index: int, task: dict) -> str:
    """Format a numbered task line for deletion workflow."""
    title = task.get("title", "(No title)")
    due = task.get("due")
    if due:
        due_date = datetime.fromisoformat(due.replace("Z", "+00:00"))
        due_str = due_date.strftime("%b %d, %Y")
        return f"{index}. {title} (due {due_str})"
    return f"{index}. {title}"
