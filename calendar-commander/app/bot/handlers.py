"""Telegram update handlers and registration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

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


@dataclass(frozen=True)
class BotServices:
    """Dependencies injected into bot handlers."""

    calendar_service: CalendarService
    parser_service: ParserService
    timezone: str


def register_handlers(application: Application, services: BotServices) -> None:
    """Attach all command and message handlers to the Telegram app."""
    application.bot_data["services"] = services

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
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
    """Welcome message and high-level usage instructions."""
    await update.effective_message.reply_text(
        "Hello! I can manage your Google Calendar.\n"
        "Use /help to see all commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display command help message."""
    await update.effective_message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's events sorted by time."""
    services = _services(context)

    try:
        events = await services.calendar_service.get_today_events()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to fetch today's events", exc_info=exc)
        await update.effective_message.reply_text("Unable to fetch today's events right now.")
        return

    if not events:
        await update.effective_message.reply_text("No events scheduled for today.")
        return

    lines = ["📌 Today's events:"]
    lines.extend(format_event(item, services.timezone) for item in events)
    await update.effective_message.reply_text("\n".join(lines))


async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the next 10 upcoming events."""
    services = _services(context)

    try:
        events = await services.calendar_service.get_upcoming_events(limit=10)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to fetch upcoming events", exc_info=exc)
        await update.effective_message.reply_text("Unable to fetch upcoming events right now.")
        return

    if not events:
        await update.effective_message.reply_text("No upcoming events found.")
        return

    lines = ["📅 Next 10 events:"]
    lines.extend(format_event(item, services.timezone) for item in events)
    await update.effective_message.reply_text("\n".join(lines))


async def create_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create an event from natural language input with default 1-hour duration."""
    services = _services(context)
    raw_text = " ".join(context.args).strip()

    if not raw_text:
        await update.effective_message.reply_text(
            "Usage: /create_event <description>\n"
            "Example: /create_event Meeting tomorrow at 3pm"
        )
        return

    parsed = services.parser_service.parse_event_text(raw_text)
    if parsed is None:
        await update.effective_message.reply_text(
            "Couldn't parse a date/time from your input.\n"
            "Try: /create_event Meeting tomorrow at 3pm"
        )
        return

    try:
        event = await services.calendar_service.create_event(
            title=parsed.title,
            start_time=parsed.start_time,
            duration_minutes=60,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to create event", exc_info=exc)
        await update.effective_message.reply_text("Unable to create the event right now.")
        return

    await update.effective_message.reply_text(
        "✅ Event created:\n" + format_event(event, services.timezone)
    )


async def delete_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List upcoming events and ask user for index to delete."""
    services = _services(context)

    try:
        events = await services.calendar_service.get_upcoming_events(limit=10)
    except Exception as exc:  # noqa: BLE001
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
        format_numbered_event(index + 1, event, services.timezone)
        for index, event in enumerate(events)
    )
    await update.effective_message.reply_text("\n".join(lines))


async def delete_event_index_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Consume free-text number input for deletion workflow."""
    if not context.user_data.get("awaiting_delete_index"):
        return

    services = _services(context)
    message = update.effective_message.text.strip()
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
        await services.calendar_service.delete_event(event_id)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to delete event", exc_info=exc)
        await update.effective_message.reply_text("Unable to delete the selected event right now.")
        return
    finally:
        context.user_data["awaiting_delete_index"] = False
        context.user_data.pop("delete_candidates", None)

    await update.effective_message.reply_text("🗑️ Event deleted successfully.")
