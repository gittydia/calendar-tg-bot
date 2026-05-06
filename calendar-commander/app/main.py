"""FastAPI webhook application entrypoint."""

from __future__ import annotations

import logging

from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import Application

from app.bot.application import create_application, setup_bot_metadata
from app.bot.handlers import BotServices
from app.config import Settings, get_settings
from app.services.auth_service import AuthService
from app.services.calendar_service import CalendarService
from app.services.parser_service import ParserService
from app.services.token_store import TokenStore

LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

CONNECT_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connect Google Calendar</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
        .card {{ background: #1e293b; border-radius: 16px; padding: 2.5rem; max-width: 420px; width: 90%; box-shadow: 0 25px 50px rgba(0,0,0,.4); text-align: center; }}
        h1 {{ font-size: 1.5rem; margin-bottom: .5rem; }}
        p {{ color: #94a3b8; margin-bottom: 2rem; line-height: 1.6; }}
        .btn {{ display: inline-block; background: #4285f4; color: #fff; padding: .85rem 2rem; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1rem; transition: background .2s; }}
        .btn:hover {{ background: #3367d6; }}
        .icon {{ font-size: 3rem; margin-bottom: 1rem; }}
        .footer {{ margin-top: 2rem; font-size: .8rem; color: #64748b; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">📅</div>
        <h1>Connect Google Calendar</h1>
        <p>Link your Google Calendar to interact with it via Telegram. You'll be redirected to Google to authorize access.</p>
        {body}
        <div class="footer">Powered by Calendar Commander</div>
    </div>
</body>
</html>
"""


def build_services(settings: Settings) -> BotServices:
    token_store = TokenStore(db_path=settings.db_path)
    auth_service = AuthService(
        credentials_file=settings.credentials_file,
        token_store=token_store,
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
    settings = get_settings()
    services = build_services(settings)
    telegram_app = create_application(settings, services)

    fastapi_app.state.settings = settings
    fastapi_app.state.telegram_app = telegram_app
    fastapi_app.state.services = services

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
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    settings: Settings = app.state.settings
    services: BotServices = app.state.services
    has_tokens = services._calendar_service._auth_service._token_store.has_credentials("any")
    if has_tokens:
        body = '<p style="color:#4ade80;margin-bottom:1.5rem;">✅ The bot is running.</p><p>Open Telegram and send <code>/start</code> to your bot.</p>'
    else:
        body = f'<a href="{settings.connect_url}" class="btn">Connect via Telegram Bot</a>'
    return CONNECT_PAGE.format(body=body)


@app.get("/connect", response_class=HTMLResponse)
async def connect_page(request: Request):
    uid = request.query_params.get("uid", "")
    services: BotServices = app.state.services
    settings: Settings = app.state.settings

    if uid:
        auth_url = services._calendar_service._auth_service.build_oauth_url(
            settings.oauth_redirect_uri, uid
        )
        body = (
            f'<a href="{auth_url}" class="btn">Connect with Google</a>'
            f'<p style="margin-top:1.5rem;font-size:.85rem;color:#64748b;">This will authorize Calendar Commander to access your Google Calendar.</p>'
        )
    else:
        body = '<p style="color:#f59e0b;margin-bottom:1.5rem;">Connect through your Telegram bot for the best experience. Send <code>/connect</code> in the bot.</p>'

    return CONNECT_PAGE.format(body=body)


@app.get("/oauth/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(
            content=CONNECT_PAGE.format(
                body=f'<p style="color:#f87171;margin-bottom:1.5rem;">Error: {error}</p>'
                     f'<a href="/" class="btn">Go Back</a>'
            )
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    services: BotServices = app.state.services
    auth = services._calendar_service._auth_service
    settings: Settings = app.state.settings
    redirect_uri = settings.oauth_redirect_uri

    try:
        auth.exchange_code(code, state, redirect_uri)
    except Exception as exc:
        LOGGER.exception("OAuth code exchange failed", exc_info=exc)
        return HTMLResponse(
            content=CONNECT_PAGE.format(
                body=f'<p style="color:#f87171;margin-bottom:1.5rem;">Failed to connect: {exc}</p>'
                     f'<a href="/" class="btn">Go Back</a>'
            )
        )

    telegram_app: Application = app.state.telegram_app
    try:
        await telegram_app.bot.send_message(
            chat_id=int(state),
            text="✅ Google Calendar connected successfully! You can now use /today, /events, /create_event, etc.",
        )
    except Exception as exc:
        LOGGER.warning("Could not send confirmation to user %s: %s", state, exc)

    return HTMLResponse(
        content=CONNECT_PAGE.format(
            body='<p style="color:#4ade80;margin-bottom:1.5rem;">✅ Connected successfully! You can close this page and check Telegram.</p>'
                 f'<a href="{settings.connect_url}" class="btn">Go Back</a>'
        )
    )


@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, str]:
    telegram_app: Application | None = getattr(request.app.state, "telegram_app", None)
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram application is not initialized.")

    try:
        payload = await request.json()
        update = Update.de_json(payload, telegram_app.bot)
        await telegram_app.update_queue.put(update)
    except Exception as exc:
        LOGGER.exception("Failed to process webhook payload", exc_info=exc)
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

    return {"status": "accepted"}
