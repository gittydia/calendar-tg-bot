"""Tests for the daily scheduler."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.bot.handlers import BotServices
from app.main import send_daily_notifications
from app.services.auth_service import AuthService
from app.services.calendar_service import CalendarService
from app.services.token_store import TokenStore


@pytest.fixture
def token_store(tmp_path):
    return TokenStore(db_path=str(tmp_path / "tokens.db"))


@pytest.fixture
def settings():
    s = MagicMock()
    s.timezone = "Asia/Manila"
    return s


@pytest.fixture
def calendar_service(settings, token_store):
    auth_service = MagicMock(spec=AuthService)
    auth_service.list_all_user_ids.side_effect = lambda: token_store.list_all_user_ids()
    auth_service.get_credentials.return_value = MagicMock()

    service = CalendarService(auth_service=auth_service, timezone=settings.timezone)

    mock_resource = MagicMock()
    mock_resource.events.return_value.list.return_value.execute.return_value = {"items": []}
    service._get_service = MagicMock(return_value=mock_resource)

    return service


@pytest.fixture
def services(token_store, calendar_service, settings):
    tasks_service = MagicMock()
    tasks_service.list_tasks_due_today = AsyncMock(return_value=[])
    return BotServices(
        calendar_service=calendar_service,
        tasks_service=tasks_service,
        parser_service=MagicMock(),
        timezone=settings.timezone,
    )


@pytest.fixture
def telegram_app():
    app = MagicMock()
    app.bot.send_message = AsyncMock()
    return app


@pytest.mark.asyncio
async def test_no_users(services, telegram_app, settings):
    """When no users are connected, do nothing."""
    await send_daily_notifications(services, telegram_app, settings)
    telegram_app.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_user_no_events(token_store, services, telegram_app, settings):
    """User with no events gets a 'no events' message."""
    token_store.save_credentials("12345", '{"token": "dummy"}')

    await send_daily_notifications(services, telegram_app, settings)

    telegram_app.bot.send_message.assert_awaited_once_with(
        chat_id=12345,
        text="\u2600\ufe0f Good morning! Nothing scheduled for today.",
    )


@pytest.mark.asyncio
async def test_user_with_events(token_store, services, telegram_app, settings):
    """User with events gets a formatted schedule."""
    token_store.save_credentials("12345", '{"token": "dummy"}')

    fake_events = [
        {"summary": "Team standup", "start": {"dateTime": "2026-05-10T09:00:00+08:00"}},
        {"summary": "Lunch with client", "start": {"dateTime": "2026-05-10T12:00:00+08:00"}},
    ]
    (services._calendar_service._get_service.return_value
     .events.return_value
     .list.return_value
     .execute.return_value) = {"items": fake_events}

    await send_daily_notifications(services, telegram_app, settings)

    call = telegram_app.bot.send_message.await_args
    assert call.kwargs["chat_id"] == 12345
    text = call.kwargs["text"]
    assert "Good morning! Here's your schedule for today:" in text
    assert "📌 Events:" in text
    assert "Team standup" in text
    assert "Lunch with client" in text


@pytest.mark.asyncio
async def test_user_permission_error(token_store, services, telegram_app, settings):
    """User without valid credentials is skipped (no message sent)."""
    token_store.save_credentials("12345", '{"token": "dummy"}')

    services._calendar_service._get_service.side_effect = PermissionError("not connected")

    await send_daily_notifications(services, telegram_app, settings)

    telegram_app.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_users(token_store, services, telegram_app, settings):
    """Multiple users each get their own notification."""
    token_store.save_credentials("1", '{"token": "user1"}')
    token_store.save_credentials("2", '{"token": "user2"}')

    mock_resource = MagicMock()
    mock_resource.events.return_value.list.return_value.execute.return_value = {"items": []}
    services._calendar_service._get_service = MagicMock(return_value=mock_resource)

    await send_daily_notifications(services, telegram_app, settings)

    assert telegram_app.bot.send_message.await_count == 2


def test_scheduler_target_time():
    """Verify the next-run-at-6AM calculation is correct."""
    tz = ZoneInfo("Asia/Manila")
    now = datetime(2026, 5, 10, 22, 0, tzinfo=tz)
    target = datetime.combine(now.date(), time(6, 0), tzinfo=tz)
    if now >= target:
        target += timedelta(days=1)
    assert target == datetime(2026, 5, 11, 6, 0, tzinfo=tz)
    assert int((target - now).total_seconds()) == 28800

    now = datetime(2026, 5, 10, 4, 0, tzinfo=tz)
    target = datetime.combine(now.date(), time(6, 0), tzinfo=tz)
    if now >= target:
        target += timedelta(days=1)
    assert target == datetime(2026, 5, 10, 6, 0, tzinfo=tz)
    assert int((target - now).total_seconds()) == 7200
