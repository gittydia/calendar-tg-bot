"""Google OAuth2 authentication and token lifecycle management."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


class AuthService:
    """Provides authorized Google API credentials with auto-refresh."""

    def __init__(
        self,
        credentials_file: str,
        token_file: str,
        scopes: Sequence[str],
    ) -> None:
        self._credentials_file = Path(credentials_file)
        self._token_file = Path(token_file)
        self._scopes = list(scopes)

    def get_credentials(self) -> Credentials:
        """Load credentials, refresh token when expired, or run OAuth flow."""
        creds: Credentials | None = None

        if self._token_file.exists():
            creds = Credentials.from_authorized_user_file(
                str(self._token_file),
                self._scopes,
            )

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds

        if not self._credentials_file.exists():
            raise FileNotFoundError(
                f"OAuth credentials file not found: {self._credentials_file}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self._credentials_file),
            self._scopes,
        )
        creds = flow.run_local_server(port=9999)
        self._token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds
