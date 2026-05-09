"""Storage for per-user Google OAuth tokens — supports SQLite and PostgreSQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class TokenStore:
    """Per-user credential persistence backed by SQLite or PostgreSQL."""

    def __init__(self, db_path: str = "tokens.db", database_url: str = "") -> None:
        self._db_path = db_path
        self._database_url = database_url
        self._pg = bool(database_url)
        if self._pg:
            try:
                self._init_pg()
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "PostgreSQL unavailable (%s), falling back to SQLite", exc
                )
                self._pg = False
        if not self._pg:
            self._db = Path(db_path)
            self._init_sqlite()

    def _conn(self):
        if self._pg:
            import psycopg2

            return psycopg2.connect(
                self._database_url,
                connect_timeout=5,
            )
        return sqlite3.connect(self._db, timeout=5)

    def _init_pg(self) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
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

    def _init_sqlite(self) -> None:
        with self._conn() as conn:
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
        if self._pg:
            self._save_pg(telegram_user_id, credentials_json)
        else:
            self._save_sqlite(telegram_user_id, credentials_json)

    def _save_pg(self, telegram_user_id: str, credentials_json: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_tokens (telegram_user_id, credentials_json)
                    VALUES (%s, %s)
                    ON CONFLICT (telegram_user_id)
                    DO UPDATE SET credentials_json = EXCLUDED.credentials_json,
                                  last_updated = CURRENT_TIMESTAMP
                    """,
                    (telegram_user_id, credentials_json),
                )
            conn.commit()

    def _save_sqlite(self, telegram_user_id: str, credentials_json: str) -> None:
        with self._conn() as conn:
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
        if self._pg:
            return self._get_pg(telegram_user_id)
        return self._get_sqlite(telegram_user_id)

    def _get_pg(self, telegram_user_id: str) -> str | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT credentials_json FROM user_tokens WHERE telegram_user_id = %s",
                    (telegram_user_id,),
                )
                row = cur.fetchone()
        return row[0] if row else None

    def _get_sqlite(self, telegram_user_id: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT credentials_json FROM user_tokens WHERE telegram_user_id = ?",
                (telegram_user_id,),
            ).fetchone()
        return row[0] if row else None

    def delete_credentials(self, telegram_user_id: str) -> bool:
        if self._pg:
            return self._delete_pg(telegram_user_id)
        return self._delete_sqlite(telegram_user_id)

    def _delete_pg(self, telegram_user_id: str) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_tokens WHERE telegram_user_id = %s",
                    (telegram_user_id,),
                )
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    def _delete_sqlite(self, telegram_user_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM user_tokens WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            conn.commit()
        return cursor.rowcount > 0

    def list_all_user_ids(self) -> list[str]:
        if self._pg:
            return self._list_all_pg()
        return self._list_all_sqlite()

    def _list_all_pg(self) -> list[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT telegram_user_id FROM user_tokens")
                rows = cur.fetchall()
        return [row[0] for row in rows]

    def _list_all_sqlite(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT telegram_user_id FROM user_tokens"
            ).fetchall()
        return [row[0] for row in rows]

    def has_credentials(self, telegram_user_id: str) -> bool:
        return self.get_credentials(telegram_user_id) is not None
