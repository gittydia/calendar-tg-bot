"""Google Calendar operations abstracted behind an async-friendly service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import Resource, build

from app.services.auth_service import AuthService


class CalendarService:
    """Per-user Google Calendar operations."""

    def __init__(self, auth_service: AuthService, timezone: str) -> None:
        self._auth_service = auth_service
        self._timezone = timezone
        self._services: dict[str, Resource] = {}

    def _get_service(self, telegram_user_id: str) -> Resource:
        if telegram_user_id not in self._services:
            credentials = self._auth_service.get_credentials(telegram_user_id)
            if credentials is None:
                raise PermissionError(
                    f"User {telegram_user_id} has not connected their Google account. "
                    "Use /connect to link your calendar."
                )
            self._services[telegram_user_id] = build(
                "calendar", "v3", credentials=credentials, cache_discovery=False
            )
        return self._services[telegram_user_id]

    async def get_today_events(self, telegram_user_id: str) -> list[dict]:
        tz = ZoneInfo(self._timezone)
        now_local = datetime.now(tz)
        start = datetime.combine(now_local.date(), time.min, tzinfo=tz)
        end = datetime.combine(now_local.date(), time.max, tzinfo=tz)
        return await self._list_events(telegram_user_id, start.isoformat(), end.isoformat(), max_results=50)

    async def get_upcoming_events(self, telegram_user_id: str, limit: int = 10) -> list[dict]:
        now_utc = datetime.now(UTC).isoformat()
        return await self._list_events(telegram_user_id, now_utc, None, max_results=limit)

    async def create_event(self, telegram_user_id: str, title: str, start_time: datetime, duration_minutes: int = 60) -> dict:
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
            service = self._get_service(telegram_user_id)
            return (
                service.events()
                .insert(calendarId="primary", body=body)
                .execute()
            )

        return await asyncio.to_thread(_create)

    async def delete_event(self, telegram_user_id: str, event_id: str) -> None:
        def _delete() -> None:
            service = self._get_service(telegram_user_id)
            service.events().delete(calendarId="primary", eventId=event_id).execute()

        await asyncio.to_thread(_delete)

    async def _list_events(
        self,
        telegram_user_id: str,
        time_min: str,
        time_max: str | None,
        max_results: int,
    ) -> list[dict]:
        def _list() -> list[dict]:
            service = self._get_service(telegram_user_id)
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
        start = event.get("start", {})
        date_time = start.get("dateTime")
        if date_time:
            return datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        date_only = start.get("date")
        if date_only:
            return datetime.fromisoformat(f"{date_only}T00:00:00+00:00")
        return datetime.max.replace(tzinfo=UTC)
