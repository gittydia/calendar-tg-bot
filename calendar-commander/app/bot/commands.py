"""Telegram bot commands and descriptions."""

from telegram import BotCommand

BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Get started with Calendar Commander"),
    BotCommand("help", "Show all available commands"),
    BotCommand("connect", "Connect your Google Calendar account"),
    BotCommand("disconnect", "Disconnect your Google Calendar account"),
    BotCommand("today", "Show today's events"),
    BotCommand("events", "Show next 10 upcoming events"),
    BotCommand("create_event", "Create event with natural language"),
    BotCommand("delete_event", "Delete an upcoming event"),
    BotCommand("tasks", "Show your tasks"),
    BotCommand("create_task", "Create a task"),
    BotCommand("delete_task", "Delete a task"),
]

HELP_TEXT = (
    "<b>Available commands:</b>\n\n"
    "/connect — Link your Google Calendar\n"
    "/disconnect — Unlink your Google Calendar\n"
    "/today — Show today's events\n"
    "/events — Show next 10 upcoming events\n"
    "/create_event &lt;text&gt; — Create event (e.g. /create_event Meeting tomorrow at 3pm)\n"
    "/delete_event — Select an event to delete\n"
    "/tasks — Show your tasks\n"
    "/create_task &lt;text&gt; — Create a task\n"
    "/delete_task — Select a task to delete"
)
