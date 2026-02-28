"""Runtime configuration and environment variable loading."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    bot_token: str
    webhook_url: str
    port: int = 8000
    timezone: str = "Asia/Manila"
    credentials_file: str = "credentials.json"
    token_file: str = "token.json"

    @property
    def full_webhook_url(self) -> str:
        """Build the webhook URL consumed by Telegram."""
        return f"{self.webhook_url.rstrip('/')}/webhook"


def _require_env(name: str) -> str:
    """Fetch and validate mandatory environment variable."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_settings() -> Settings:
    """Load settings from environment variables."""
    return Settings(
        bot_token=_require_env("BOT_TOKEN"),
        webhook_url=_require_env("WEBHOOK_URL"),
        port=int(os.getenv("PORT", "8000")),
        timezone=os.getenv("TIMEZONE", "Asia/Manila"),
        credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
        token_file=os.getenv("GOOGLE_TOKEN_FILE", "token.json"),
    )
