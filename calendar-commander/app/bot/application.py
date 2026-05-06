"""Telegram Application factory and shared bot setup."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes

from app.bot.commands import BOT_COMMANDS
from app.bot.handlers import BotServices, register_handlers
from app.config import Settings

LOGGER = logging.getLogger(__name__)


def create_application(settings: Settings, services: BotServices) -> Application:
    app = Application.builder().token(settings.bot_token).updater(None).build()
    app.bot_data["services"] = services
    app.bot_data["settings"] = settings
    register_handlers(app, services)
    app.add_error_handler(global_error_handler)
    return app


async def setup_bot_metadata(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)


async def global_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    LOGGER.exception("Unhandled Telegram update error", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "An internal error occurred while processing your request."
        )
