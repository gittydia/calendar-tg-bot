"""SQLite-backed storage for per-user Google OAuth tokens."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class TokenStore:
    """Thread-safe per-user credential persistence."""

    def __init__(self, db_path: str = "tokens.db") -> None:
        self._db = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_tokens (
                    telegram_user_id TEXT PRIMARY KEY,
                    credentials_json TEXT NOT NULL,
                    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save_credentials(self, telegram_user_id: str, credentials_json: str) -> None:
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """
                INSERT INTO user_tokens (telegram_user_id, credentials_json)
                VALUES (?, ?)
                ON CONFLICT(telegram_user_id)
                DO UPDATE SET credentials_json = excluded.credentials_json,
                              last_updated = CURRENT_TIMESTAMP
                """,
                (telegram_user_id, credentials_json),
            )
            conn.commit()

    def get_credentials(self, telegram_user_id: str) -> str | None:
        with sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT credentials_json FROM user_tokens WHERE telegram_user_id = ?",
                (telegram_user_id,),
            ).fetchone()
        return row[0] if row else None

    def delete_credentials(self, telegram_user_id: str) -> bool:
        with sqlite3.connect(self._db) as conn:
            cursor = conn.execute(
                "DELETE FROM user_tokens WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            conn.commit()
        return cursor.rowcount > 0

    def has_credentials(self, telegram_user_id: str) -> bool:
        return self.get_credentials(telegram_user_id) is not None
