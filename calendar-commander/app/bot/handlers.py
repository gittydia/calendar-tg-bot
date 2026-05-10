"""Telegram update handlers and registration."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.commands import HELP_TEXT
from app.services.calendar_service import CalendarService
from app.services.parser_service import ParserService
from app.utils.formatters import format_event, format_numbered_event

LOGGER = logging.getLogger(__name__)


class BotServices:
    """Factory for per-user service instances."""

    def __init__(
        self,
        calendar_service: CalendarService,
        parser_service: ParserService,
        timezone: str,
    ) -> None:
        self._calendar_service = calendar_service
        self._parser_service = parser_service
        self._timezone = timezone

    def list_user_ids(self) -> list[str]:
        return self._calendar_service._auth_service.list_all_user_ids()

    def for_user(self, telegram_user_id: str) -> "UserServices":
        return UserServices(
            telegram_user_id=telegram_user_id,
            calendar_service=self._calendar_service,
            parser_service=self._parser_service,
            timezone=self._timezone,
        )


class UserServices:
    """Per-user service context."""

    def __init__(
        self,
        telegram_user_id: str,
        calendar_service: CalendarService,
        parser_service: ParserService,
        timezone: str,
    ) -> None:
        self.telegram_user_id = telegram_user_id
        self.calendar_service = calendar_service
        self.parser_service = parser_service
        self.timezone = timezone

    @property
    def uid(self) -> str:
        return self.telegram_user_id


def register_handlers(application: Application, services: BotServices) -> None:
    application.bot_data["services"] = services

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("connect", connect_command))
    application.add_handler(CommandHandler("disconnect", disconnect_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("events", events_command))
    application.add_handler(CommandHandler("create_event", create_event_command))
    application.add_handler(CommandHandler("delete_event", delete_event_command))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_event_index_handler,
        )
    )


def _services(context: ContextTypes.DEFAULT_TYPE) -> BotServices:
    return context.application.bot_data["services"]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "Hello! I can manage your Google Calendar.\n"
            "Use /connect to link your account, then /help for commands."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    services = _services(context)
    user_id = str(update.effective_user.id)
    user = services.for_user(user_id)

    if user.calendar_service._auth_service.get_credentials(user_id):
        await update.effective_message.reply_text(
            "Your Google Calendar is already connected. "
            "Use /disconnect to unlink and reconnect."
        )
        return

    settings = context.application.bot_data["settings"]
    connect_url = f"{settings.base_url.rstrip('/')}/connect?uid={user_id}"

    await update.effective_message.reply_text(
        "Click the link below to connect your Google Calendar:\n\n"
        f"{connect_url}",
        disable_web_page_preview=True,
    )


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    services = _services(context)
    user_id = str(update.effective_user.id)
    auth = services.for_user(user_id).calendar_service._auth_service

    if auth.disconnect(user_id):
        await update.effective_message.reply_text(
            "Your Google Calendar has been disconnected."
        )
    else:
        await update.effective_message.reply_text(
            "No connected Google Calendar account found."
        )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    services = _services(context)
    user = services.for_user(str(update.effective_user.id))

    try:
        events = await user.calendar_service.get_today_events(user.uid)
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to fetch today's events", exc_info=exc)
        await update.effective_message.reply_text("Unable to fetch today's events right now.")
        return

    if not events:
        await update.effective_message.reply_text("No events scheduled for today.")
        return

    lines = ["📌 Today's events:"]
    lines.extend(format_event(item, user.timezone) for item in events)
    await update.effective_message.reply_text("\n".join(lines))


async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    services = _services(context)
    user = services.for_user(str(update.effective_user.id))

    try:
        events = await user.calendar_service.get_upcoming_events(user.uid, limit=10)
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to fetch upcoming events", exc_info=exc)
        await update.effective_message.reply_text("Unable to fetch upcoming events right now.")
        return

    if not events:
        await update.effective_message.reply_text("No upcoming events found.")
        return

    lines = ["📅 Next 10 events:"]
    lines.extend(format_event(item, user.timezone) for item in events)
    await update.effective_message.reply_text("\n".join(lines))


async def create_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    services = _services(context)
    user = services.for_user(str(update.effective_user.id))
    raw_text = " ".join(context.args or []).strip()

    if not raw_text:
        await update.effective_message.reply_text(
            "Usage: /create_event <description>\n"
            "Example: /create_event Meeting tomorrow at 3pm"
        )
        return

    parsed = user.parser_service.parse_event_text(raw_text)
    if parsed is None:
        await update.effective_message.reply_text(
            "Couldn't parse a date/time from your input.\n"
            "Try: /create_event Meeting tomorrow at 3pm"
        )
        return

    try:
        event = await user.calendar_service.create_event(
            user.uid,
            title=parsed.title,
            start_time=parsed.start_time,
            duration_minutes=60,
        )
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to create event", exc_info=exc)
        await update.effective_message.reply_text("Unable to create the event right now.")
        return

    await update.effective_message.reply_text(
        "✅ Event created:\n" + format_event(event, user.timezone)
    )


async def delete_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None or context.user_data is None:
        return
    services = _services(context)
    user = services.for_user(str(update.effective_user.id))

    try:
        events = await user.calendar_service.get_upcoming_events(user.uid, limit=10)
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to load events for deletion", exc_info=exc)
        await update.effective_message.reply_text("Unable to load events for deletion right now.")
        return

    if not events:
        await update.effective_message.reply_text("No upcoming events available to delete.")
        return

    context.user_data["delete_candidates"] = events
    context.user_data["awaiting_delete_index"] = True

    lines = ["Select an event to delete by sending its number:"]
    lines.extend(
        format_numbered_event(index + 1, event, user.timezone)
        for index, event in enumerate(events)
    )
    await update.effective_message.reply_text("\n".join(lines))


async def delete_event_index_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if context.user_data is None or not context.user_data.get("awaiting_delete_index"):
        return
    if update.effective_user is None or update.effective_message is None:
        return

    services = _services(context)
    user = services.for_user(str(update.effective_user.id))
    message = (update.effective_message.text or "").strip()
    candidates: list[dict] = context.user_data.get("delete_candidates", [])

    if not message.isdigit():
        await update.effective_message.reply_text("Please send a valid number from the list.")
        return

    index = int(message)
    if index < 1 or index > len(candidates):
        await update.effective_message.reply_text("Number out of range. Please try again.")
        return

    selected_event = candidates[index - 1]
    event_id = selected_event.get("id")
    if not event_id:
        await update.effective_message.reply_text("Selected event cannot be deleted.")
        return

    try:
        await user.calendar_service.delete_event(user.uid, event_id)
        await update.effective_message.reply_text("🗑️ Event deleted successfully.")
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
    except Exception as exc:
        LOGGER.exception("Failed to delete event", exc_info=exc)
        await update.effective_message.reply_text("Unable to delete the selected event right now.")
    finally:
        context.user_data["awaiting_delete_index"] = False
        context.user_data.pop("delete_candidates", None)
