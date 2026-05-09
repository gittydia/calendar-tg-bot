"""Runtime configuration and environment variable loading."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    bot_token: str
    webhook_url: str
    base_url: str
    port: int = 8000
    timezone: str = "Asia/Manila"
    credentials_file: str = "credentials.json"
    db_path: str = "tokens.db"
    database_url: str = ""

    @property
    def full_webhook_url(self) -> str:
        return f"{self.webhook_url.rstrip('/')}/webhook"

    @property
    def connect_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/connect"

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{self.base_url.rstrip('/')}/oauth/callback"


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_settings() -> Settings:
    return Settings(
        bot_token=_require_env("BOT_TOKEN"),
        webhook_url=_require_env("WEBHOOK_URL"),
        base_url=_require_env("BASE_URL"),
        port=int(os.getenv("PORT", "8000")),
        timezone=os.getenv("TIMEZONE", "Asia/Manila"),
        credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
        db_path=os.getenv("DB_PATH", "tokens.db"),
        database_url=os.getenv("DATABASE_URL", ""),
    )
