"""Google Calendar operations abstracted behind an async-friendly service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import Resource, build

from app.services.auth_service import AuthService


class CalendarService:
    """Performs event listing, creation, and deletion against Google Calendar."""

    def __init__(self, auth_service: AuthService, timezone: str) -> None:
        self._auth_service = auth_service
        self._timezone = timezone
        self._service: Resource | None = None

    def _get_service(self) -> Resource:
        """Build and cache Google Calendar client."""
        if self._service is None:
            credentials = self._auth_service.get_credentials()
            self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    async def get_today_events(self) -> list[dict]:
        """Return events scheduled for today in configured timezone."""
        tz = ZoneInfo(self._timezone)
        now_local = datetime.now(tz)
        start = datetime.combine(now_local.date(), time.min, tzinfo=tz)
        end = datetime.combine(now_local.date(), time.max, tzinfo=tz)
        return await self._list_events(start.isoformat(), end.isoformat(), max_results=50)

    async def get_upcoming_events(self, limit: int = 10) -> list[dict]:
        """Return next upcoming events from now onward."""
        now_utc = datetime.now(UTC).isoformat()
        return await self._list_events(now_utc, None, max_results=limit)

    async def create_event(self, title: str, start_time: datetime, duration_minutes: int = 60) -> dict:
        """Create a new calendar event with default 1-hour duration."""
        tz = ZoneInfo(self._timezone)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=tz)
        end_time = start_time + timedelta(minutes=duration_minutes)

        body = {
            "summary": title,
            "start": {"dateTime": start_time.isoformat(), "timeZone": self._timezone},
            "end": {"dateTime": end_time.isoformat(), "timeZone": self._timezone},
        }

        def _create() -> dict:
            service = self._get_service()
            return (
                service.events()
                .insert(calendarId="primary", body=body)
                .execute()
            )

        return await asyncio.to_thread(_create)

    async def delete_event(self, event_id: str) -> None:
        """Delete an event by ID."""

        def _delete() -> None:
            service = self._get_service()
            service.events().delete(calendarId="primary", eventId=event_id).execute()

        await asyncio.to_thread(_delete)

    async def _list_events(
        self,
        time_min: str,
        time_max: str | None,
        max_results: int,
    ) -> list[dict]:
        """List events from calendar, sorted by start time by API order."""

        def _list() -> list[dict]:
            service = self._get_service()
            query: dict = {
                "calendarId": "primary",
                "timeMin": time_min,
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": max_results,
            }
            if time_max:
                query["timeMax"] = time_max

            response = service.events().list(**query).execute()
            return response.get("items", [])

        events = await asyncio.to_thread(_list)
        return sorted(events, key=self._event_sort_key)

    def _event_sort_key(self, event: dict) -> datetime:
        """Build comparable datetime key from event start payload."""
        start = event.get("start", {})
        date_time = start.get("dateTime")
        if date_time:
            return datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        date_only = start.get("date")
        if date_only:
            return datetime.fromisoformat(f"{date_only}T00:00:00+00:00")
        return datetime.max.replace(tzinfo=UTC)
