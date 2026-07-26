"""Telegram update handlers and registration."""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

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
from app.services.parser_service import ParserService, ParsedEvent, ParsedTask
from app.services.tasks_service import TasksService
from app.utils.formatters import (
    format_event,
    format_numbered_event,
    format_numbered_task,
    format_task,
    _format_time_range,
)

LOGGER = logging.getLogger(__name__)


class BotServices:
    """Factory for per-user service instances."""

    def __init__(
        self,
        calendar_service: CalendarService,
        tasks_service: TasksService,
        parser_service: ParserService,
        timezone: str,
    ) -> None:
        self._calendar_service = calendar_service
        self._tasks_service = tasks_service
        self._parser_service = parser_service
        self._timezone = timezone

    def list_user_ids(self) -> list[str]:
        return self._calendar_service._auth_service.list_all_user_ids()

    def for_user(self, telegram_user_id: str) -> "UserServices":
        return UserServices(
            telegram_user_id=telegram_user_id,
            calendar_service=self._calendar_service,
            tasks_service=self._tasks_service,
            parser_service=self._parser_service,
            timezone=self._timezone,
        )


class UserServices:
    """Per-user service context."""

    def __init__(
        self,
        telegram_user_id: str,
        calendar_service: CalendarService,
        tasks_service: TasksService,
        parser_service: ParserService,
        timezone: str,
    ) -> None:
        self.telegram_user_id = telegram_user_id
        self.calendar_service = calendar_service
        self.tasks_service = tasks_service
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
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("create_task", create_task_command))
    application.add_handler(CommandHandler("delete_task", delete_task_command))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            create_event_message_handler,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_event_index_handler,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            create_task_message_handler,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_task_index_handler,
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

    today = datetime.now(ZoneInfo(user.timezone)).date()

    try:
        tasks = await user.tasks_service.list_tasks_due_today(user.uid, today)
    except Exception as exc:
        LOGGER.exception("Failed to fetch today's tasks", exc_info=exc)
        tasks = []

    lines = []

    if events:
        lines.append("📌 Today's events:")
        lines.extend(format_event(item, user.timezone) for item in events)

    if tasks:
        if lines:
            lines.append("")
        lines.append("📋 Today's tasks:")
        lines.extend(format_task(item) for item in tasks)

    if not lines:
        await update.effective_message.reply_text("Nothing scheduled for today.")
        return

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
        context.user_data["creating_event"] = {"step": "title"}
        await update.effective_message.reply_text(
            "Let's create an event! What's the title?"
        )
        return

    parsed = user.parser_service.parse_event_text(raw_text)
    if parsed is None:
        context.user_data["creating_event"] = {
            "step": "start",
            "title": raw_text,
        }
        await update.effective_message.reply_text(
            f"I'll use \"{raw_text}\" as the title.\n"
            "When should it start? (e.g., tomorrow at 3pm, 2026-05-25 15:00)"
        )
        return

    await _create_and_reply(update, context, user, parsed)


async def _create_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: UserServices,
    parsed: ParsedEvent,
) -> None:
    """Create the event and reply with the result."""
    try:
        event = await user.calendar_service.create_event(
            user.uid,
            title=parsed.title,
            start_time=parsed.start_time,
            end_time=parsed.end_time,
        )
    except PermissionError as exc:
        if update.effective_message:
            await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to create event", exc_info=exc)
        if update.effective_message:
            await update.effective_message.reply_text("Unable to create the event right now.")
        return

    if update.effective_message:
        await update.effective_message.reply_text(
            "✅ Event created:\n" + format_event(event, user.timezone)
        )


async def create_event_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if context.user_data is None:
        return
    creation = context.user_data.get("creating_event")
    if not creation:
        return
    if update.effective_user is None or update.effective_message is None:
        return

    services = _services(context)
    user = services.for_user(str(update.effective_user.id))
    text = (update.effective_message.text or "").strip()

    if text.lower() == "cancel":
        context.user_data.pop("creating_event", None)
        await update.effective_message.reply_text("Event creation cancelled.")
        return

    step = creation.get("step")

    if step == "title":
        creation["title"] = text
        creation["step"] = "start"
        await update.effective_message.reply_text(
            "When should it start? (e.g., tomorrow at 3pm, 2026-05-25 15:00)"
        )

    elif step == "start":
        start_time = user.parser_service.parse_datetime(text)
        if start_time is None:
            await update.effective_message.reply_text(
                "Couldn't understand that time. Please try again.\n"
                "Examples: tomorrow at 3pm, 2026-05-25 15:00, next Friday 9am"
            )
            return
        creation["start_time"] = start_time
        creation["step"] = "end"
        await update.effective_message.reply_text(
            "When should it end?\n"
            "Send a time (e.g., 5pm, 2 hours later) or \"skip\" for 1-hour duration."
        )

    elif step == "end":
        if text.lower() == "skip":
            creation["end_time"] = None
        else:
            end_time = user.parser_service.parse_datetime(text)
            if end_time is None:
                await update.effective_message.reply_text(
                    "Couldn't understand that time. Send a time or \"skip\" for 1-hour duration."
                )
                return
            creation["end_time"] = end_time

        creation["step"] = "confirm"
        title = creation["title"]
        start = creation["start_time"]
        end = creation.get("end_time")

        time_str = _format_time_range(start, end) if end else start.strftime("%Y-%m-%d %I:%M %p")
        await update.effective_message.reply_text(
            f"Create this event?\n\n"
            f"📌 {title}\n"
            f"🕐 {time_str}\n\n"
            f"Reply \"yes\" to confirm, \"no\" to cancel."
        )

    elif step == "confirm":
        if text.lower() in ("yes", "y"):
            title = creation["title"]
            start_time = creation["start_time"]
            end_time = creation.get("end_time")

            parsed = ParsedEvent(title=title, start_time=start_time, end_time=end_time)
            context.user_data.pop("creating_event", None)
            await _create_and_reply(update, context, user, parsed)
        else:
            context.user_data.pop("creating_event", None)
            await update.effective_message.reply_text("Event creation cancelled.")


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


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    services = _services(context)
    user = services.for_user(str(update.effective_user.id))

    try:
        tasks = await user.tasks_service.list_tasks(user.uid)
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to fetch tasks", exc_info=exc)
        await update.effective_message.reply_text("Unable to fetch tasks right now.")
        return

    if not tasks:
        await update.effective_message.reply_text("No tasks found.")
        return

    lines = ["📋 Your tasks:"]
    lines.extend(format_task(item) for item in tasks)
    await update.effective_message.reply_text("\n".join(lines))


async def create_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    services = _services(context)
    user = services.for_user(str(update.effective_user.id))
    raw_text = " ".join(context.args or []).strip()

    if not raw_text:
        context.user_data["creating_task"] = {"step": "title"}
        await update.effective_message.reply_text(
            "Let's create a task! What's the title?"
        )
        return

    parsed = user.parser_service.parse_task_text(raw_text)
    if parsed is None:
        context.user_data["creating_task"] = {
            "step": "due",
            "title": raw_text,
        }
        await update.effective_message.reply_text(
            f"I'll use \"{raw_text}\" as the title.\n"
            "When is it due? (e.g., tomorrow, next Friday, 2026-06-30)\n"
            "Or send \"skip\" for no due date."
        )
        return

    await _create_task_and_reply(update, context, user, parsed)


async def _create_task_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: UserServices,
    parsed: ParsedTask,
) -> None:
    try:
        task = await user.tasks_service.create_task(
            user.uid,
            title=parsed.title,
            due_date=parsed.due_date,
        )
    except PermissionError as exc:
        if update.effective_message:
            await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to create task", exc_info=exc)
        if update.effective_message:
            await update.effective_message.reply_text("Unable to create the task right now.")
        return

    if update.effective_message:
        await update.effective_message.reply_text(
            "✅ Task created:\n" + format_task(task)
        )


async def create_task_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if context.user_data is None:
        return
    creation = context.user_data.get("creating_task")
    if not creation:
        return
    if update.effective_user is None or update.effective_message is None:
        return

    services = _services(context)
    user = services.for_user(str(update.effective_user.id))
    text = (update.effective_message.text or "").strip()

    if text.lower() == "cancel":
        context.user_data.pop("creating_task", None)
        await update.effective_message.reply_text("Task creation cancelled.")
        return

    step = creation.get("step")

    if step == "title":
        creation["title"] = text
        creation["step"] = "due"
        await update.effective_message.reply_text(
            "When is it due? (e.g., tomorrow, next Friday, 2026-06-30)\n"
            "Or send \"skip\" for no due date."
        )

    elif step == "due":
        if text.lower() == "skip":
            creation["due_date"] = None
        else:
            due_date = user.parser_service.parse_date(text)
            if due_date is None:
                await update.effective_message.reply_text(
                    "Couldn't understand that date. Please try again or send \"skip\"."
                )
                return
            creation["due_date"] = due_date

        creation["step"] = "confirm"
        title = creation["title"]
        due = creation.get("due_date")
        due_str = due.strftime("%b %d, %Y") if due else "No due date"
        await update.effective_message.reply_text(
            f"Create this task?\n\n"
            f"📌 {title}\n"
            f"📅 {due_str}\n\n"
            f"Reply \"yes\" to confirm, \"no\" to cancel."
        )

    elif step == "confirm":
        if text.lower() in ("yes", "y"):
            title = creation["title"]
            due_date = creation.get("due_date")

            parsed = ParsedTask(title=title, due_date=due_date)
            context.user_data.pop("creating_task", None)
            await _create_task_and_reply(update, context, user, parsed)
        else:
            context.user_data.pop("creating_task", None)
            await update.effective_message.reply_text("Task creation cancelled.")


async def delete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None or context.user_data is None:
        return
    services = _services(context)
    user = services.for_user(str(update.effective_user.id))

    try:
        tasks = await user.tasks_service.list_tasks(user.uid)
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        LOGGER.exception("Failed to load tasks for deletion", exc_info=exc)
        await update.effective_message.reply_text("Unable to load tasks for deletion right now.")
        return

    if not tasks:
        await update.effective_message.reply_text("No tasks available to delete.")
        return

    context.user_data["delete_task_candidates"] = tasks
    context.user_data["awaiting_delete_task_index"] = True

    lines = ["Select a task to delete by sending its number:"]
    lines.extend(
        format_numbered_task(index + 1, task)
        for index, task in enumerate(tasks)
    )
    await update.effective_message.reply_text("\n".join(lines))


async def delete_task_index_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if context.user_data is None or not context.user_data.get("awaiting_delete_task_index"):
        return
    if update.effective_user is None or update.effective_message is None:
        return

    services = _services(context)
    user = services.for_user(str(update.effective_user.id))
    message = (update.effective_message.text or "").strip()
    candidates: list[dict] = context.user_data.get("delete_task_candidates", [])

    if not message.isdigit():
        await update.effective_message.reply_text("Please send a valid number from the list.")
        return

    index = int(message)
    if index < 1 or index > len(candidates):
        await update.effective_message.reply_text("Number out of range. Please try again.")
        return

    selected_task = candidates[index - 1]
    task_id = selected_task.get("id")
    if not task_id:
        await update.effective_message.reply_text("Selected task cannot be deleted.")
        return

    try:
        await user.tasks_service.delete_task(user.uid, task_id)
        await update.effective_message.reply_text("🗑️ Task deleted successfully.")
    except PermissionError as exc:
        await update.effective_message.reply_text(str(exc))
    except Exception as exc:
        LOGGER.exception("Failed to delete task", exc_info=exc)
        await update.effective_message.reply_text("Unable to delete the selected task right now.")
    finally:
        context.user_data["awaiting_delete_task_index"] = False
        context.user_data.pop("delete_task_candidates", None)
