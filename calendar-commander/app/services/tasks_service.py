"""Google Tasks API operations abstracted behind an async-friendly service."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, cast

from googleapiclient.discovery import Resource, build

from app.services.auth_service import AuthService


class TasksService:
    """Per-user Google Tasks operations."""

    def __init__(self, auth_service: AuthService) -> None:
        self._auth_service = auth_service

    def _get_service(self, telegram_user_id: str) -> Resource:
        credentials = self._auth_service.get_credentials(telegram_user_id)
        if credentials is None:
            raise PermissionError(
                "Your Google session has expired or is not connected. "
                "Please use /connect to re-link your account."
            )
        return cast(Resource, build("tasks", "v1", credentials=credentials, cache_discovery=False))

    async def _get_default_tasklist_id(self, telegram_user_id: str) -> str:
        def _get_or_create() -> str:
            service = cast(Any, self._get_service(telegram_user_id))
            result = service.tasklists().list(maxResults=1).execute()
            items = result.get("items", [])
            if items:
                return items[0]["id"]
            tasklist = service.tasklists().insert(body={"title": "My Tasks"}).execute()
            return tasklist["id"]
        return await asyncio.to_thread(_get_or_create)

    async def list_tasks(self, telegram_user_id: str, tasklist_id: str | None = None) -> list[dict]:
        def _list() -> list[dict]:
            service = cast(Any, self._get_service(telegram_user_id))
            tl_id = tasklist_id or self._get_default_tasklist_id_sync(service)
            result = service.tasks().list(
                tasklist=tl_id,
                showHidden=False,
                maxResults=100,
            ).execute()
            return result.get("items", [])
        return await asyncio.to_thread(_list)

    async def list_tasks_due_today(self, telegram_user_id: str, today: date, tasklist_id: str | None = None) -> list[dict]:
        def _list() -> list[dict]:
            service = cast(Any, self._get_service(telegram_user_id))
            tl_id = tasklist_id or self._get_default_tasklist_id_sync(service)
            day_start = today.isoformat() + "T00:00:00.000Z"
            day_end = today.isoformat() + "T23:59:59.999Z"
            result = service.tasks().list(
                tasklist=tl_id,
                showHidden=False,
                maxResults=100,
                dueMin=day_start,
                dueMax=day_end,
            ).execute()
            return result.get("items", [])
        return await asyncio.to_thread(_list)

    def _get_default_tasklist_id_sync(self, service: Any) -> str:
        result = service.tasklists().list(maxResults=1).execute()
        items = result.get("items", [])
        if items:
            return items[0]["id"]
        tasklist = service.tasklists().insert(body={"title": "My Tasks"}).execute()
        return tasklist["id"]

    async def create_task(
        self,
        telegram_user_id: str,
        title: str,
        due_date: date | None = None,
        notes: str = "",
        tasklist_id: str | None = None,
    ) -> dict:
        def _create() -> dict:
            service = cast(Any, self._get_service(telegram_user_id))
            tl_id = tasklist_id or self._get_default_tasklist_id_sync(service)
            body: dict[str, Any] = {
                "title": title,
                "notes": notes,
                "status": "needsAction",
            }
            if due_date:
                body["due"] = due_date.isoformat() + "T00:00:00.000Z"
            return (
                service.tasks()
                .insert(tasklist=tl_id, body=body)
                .execute()
            )
        return await asyncio.to_thread(_create)

    async def delete_task(
        self,
        telegram_user_id: str,
        task_id: str,
        tasklist_id: str | None = None,
    ) -> None:
        def _delete() -> None:
            service = cast(Any, self._get_service(telegram_user_id))
            tl_id = tasklist_id or self._get_default_tasklist_id_sync(service)
            service.tasks().delete(tasklist=tl_id, task=task_id).execute()
        await asyncio.to_thread(_delete)
