"""FastAPI webhook application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from telegram import Update
from telegram.ext import Application

from app.bot.application import create_application, setup_bot_metadata
from app.bot.handlers import BotServices
from app.config import Settings, get_settings
from app.services.auth_service import AuthService
from app.services.calendar_service import CalendarService
from app.services.parser_service import ParserService

LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def build_services(settings: Settings) -> BotServices:
    """Create service-layer dependencies."""
    auth_service = AuthService(
        credentials_file=settings.credentials_file,
        token_file=settings.token_file,
        scopes=SCOPES,
    )
    calendar_service = CalendarService(auth_service=auth_service, timezone=settings.timezone)
    parser_service = ParserService(timezone=settings.timezone)

    return BotServices(
        calendar_service=calendar_service,
        parser_service=parser_service,
        timezone=settings.timezone,
    )


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Initialize and shutdown Telegram webhook runtime."""
    settings = get_settings()
    services = build_services(settings)
    telegram_app = create_application(settings, services)

    fastapi_app.state.settings = settings
    fastapi_app.state.telegram_app = telegram_app

    await telegram_app.initialize()
    await telegram_app.start()
    await setup_bot_metadata(telegram_app)
    await telegram_app.bot.set_webhook(url=settings.full_webhook_url)
    LOGGER.info("Webhook configured at %s", settings.full_webhook_url)

    try:
        yield
    finally:
        await telegram_app.bot.delete_webhook(drop_pending_updates=False)
        await telegram_app.stop()
        await telegram_app.shutdown()


app = FastAPI(title="Calendar Commander Bot", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Lightweight liveness probe endpoint."""
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Receive Telegram webhook updates and feed PTB update queue."""
    telegram_app: Application | None = getattr(request.app.state, "telegram_app", None)
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram application is not initialized.")

    try:
        payload = await request.json()
        update = Update.de_json(payload, telegram_app.bot)
        await telegram_app.update_queue.put(update)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to process webhook payload", exc_info=exc)
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

    return {"status": "accepted"}
