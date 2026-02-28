"""Telegram command definitions."""

from __future__ import annotations

from telegram import BotCommand


BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Start the bot and show quick usage"),
    BotCommand("today", "Show today's events"),
    BotCommand("events", "Show next 10 upcoming events"),
    BotCommand("create_event", "Create an event from natural language"),
    BotCommand("delete_event", "Delete an upcoming event by index"),
    BotCommand("help", "Show help and examples"),
]


HELP_TEXT = (
    "📅 <b>Calendar Commander</b>\n\n"
    "Available commands:\n"
    "/today - Show events for today\n"
    "/events - Show next 10 upcoming events\n"
    "/create_event &lt;text&gt; - Create event from text\n"
    "  Example: /create_event Meeting tomorrow at 3pm\n"
    "/delete_event - List upcoming events and delete by index\n"
    "/help - Show this message"
)
