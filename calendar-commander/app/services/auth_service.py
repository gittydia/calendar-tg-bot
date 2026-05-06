"""Google OAuth2 authentication and token lifecycle management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence
from urllib.parse import quote

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.services.token_store import TokenStore


class AuthService:
    """Per-user Google OAuth with automatic token refresh."""

    def __init__(
        self,
        credentials_file: str,
        token_store: TokenStore,
        scopes: Sequence[str],
    ) -> None:
        self._credentials_file = Path(credentials_file)
        self._token_store = token_store
        self._scopes = list(scopes)

    def get_credentials(self, telegram_user_id: str) -> Credentials | None:
        creds = self._load(telegram_user_id)
        if creds is None:
            return None

        if creds.valid:
            return creds

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._token_store.save_credentials(telegram_user_id, creds.to_json())
            return creds

        return None

    def _load(self, telegram_user_id: str) -> Credentials | None:
        json_str = self._token_store.get_credentials(telegram_user_id)
        if json_str is None:
            return None
        data = json.loads(json_str)
        return Credentials.from_authorized_user_info(data, self._scopes)

    def build_oauth_url(self, redirect_uri: str, telegram_user_id: str) -> str:
        if not self._credentials_file.exists():
            raise FileNotFoundError(
                f"OAuth credentials file not found: {self._credentials_file}"
            )
        with open(self._credentials_file, "r") as f:
            client_config = json.load(f)
        web_config = client_config.get("web", client_config.get("installed", {}))
        client_id = web_config["client_id"]
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self._scopes),
            "state": telegram_user_id,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    def exchange_code(self, code: str, telegram_user_id: str, redirect_uri: str) -> Credentials:
        if not self._credentials_file.exists():
            raise FileNotFoundError(
                f"OAuth credentials file not found: {self._credentials_file}"
            )
        import requests
        with open(self._credentials_file, "r") as f:
            client_config = json.load(f)
        web_config = client_config.get("web", client_config.get("installed", {}))
        client_id = web_config["client_id"]
        client_secret = web_config.get("client_secret", "")

        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        token_data = resp.json()

        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=self._scopes,
        )
        self._token_store.save_credentials(telegram_user_id, creds.to_json())
        return creds

    def disconnect(self, telegram_user_id: str) -> bool:
        return self._token_store.delete_credentials(telegram_user_id)
