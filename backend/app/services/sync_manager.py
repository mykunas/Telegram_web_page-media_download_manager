from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.tasks.sync_tasks import (
    enqueue_consistency_recheck,
    enqueue_history_backfill,
    start_sync_worker,
    stop_sync_worker,
)

_runtime_lock = Lock()


class SyncManager:
    """Manage runtime sync service state and task trigger entrypoints."""

    def __init__(self, app_state: Any) -> None:
        self._app_state = app_state
        self._ensure_runtime_state()

    def _ensure_runtime_state(self) -> None:
        if not hasattr(self._app_state, "sync_runtime"):
            self._app_state.sync_runtime = {
                "service_running": False,
                "history_task_running": False,
                "recheck_task_running": False,
                "last_action": "initialized",
                "last_action_at": datetime.now(UTC).isoformat(),
            }

    def _update_runtime(self, **updates: Any) -> dict[str, Any]:
        with _runtime_lock:
            self._ensure_runtime_state()
            self._app_state.sync_runtime.update(updates)
            self._app_state.sync_runtime["last_action_at"] = datetime.now(UTC).isoformat()
            return dict(self._app_state.sync_runtime)

    def get_runtime_status(self) -> dict[str, Any]:
        self._ensure_runtime_state()
        return dict(self._app_state.sync_runtime)

    def start_service(self) -> dict[str, Any]:
        runtime = self.get_runtime_status()
        if runtime["service_running"]:
            return {
                "action": "start",
                "accepted": False,
                "detail": "sync service is already running",
                **runtime,
            }

        task_result = start_sync_worker()
        runtime = self._update_runtime(
            service_running=True,
            last_action="start",
        )
        return {
            "action": "start",
            "accepted": bool(task_result.get("accepted", True)),
            "detail": task_result.get("detail", "sync service started"),
            **runtime,
        }

    def stop_service(self) -> dict[str, Any]:
        runtime = self.get_runtime_status()
        if not runtime["service_running"]:
            return {
                "action": "stop",
                "accepted": False,
                "detail": "sync service is already stopped",
                **runtime,
            }

        task_result = stop_sync_worker()
        runtime = self._update_runtime(
            service_running=False,
            history_task_running=False,
            recheck_task_running=False,
            last_action="stop",
        )
        return {
            "action": "stop",
            "accepted": bool(task_result.get("accepted", True)),
            "detail": task_result.get("detail", "sync service stopped"),
            **runtime,
        }

    def trigger_history_backfill(self) -> dict[str, Any]:
        runtime = self.get_runtime_status()
        if not runtime["service_running"]:
            return {
                "action": "history",
                "accepted": False,
                "detail": "sync service is not running",
                **runtime,
            }

        task_result = enqueue_history_backfill()
        runtime = self._update_runtime(
            history_task_running=bool(task_result.get("accepted", True)),
            last_action="history",
        )
        return {
            "action": "history",
            "accepted": bool(task_result.get("accepted", True)),
            "detail": task_result.get("detail", "history backfill task triggered"),
            **runtime,
        }

    def trigger_recheck(self) -> dict[str, Any]:
        runtime = self.get_runtime_status()
        if not runtime["service_running"]:
            return {
                "action": "recheck",
                "accepted": False,
                "detail": "sync service is not running",
                **runtime,
            }

        task_result = enqueue_consistency_recheck()
        runtime = self._update_runtime(
            recheck_task_running=bool(task_result.get("accepted", True)),
            last_action="recheck",
        )
        return {
            "action": "recheck",
            "accepted": bool(task_result.get("accepted", True)),
            "detail": task_result.get("detail", "consistency recheck task triggered"),
            **runtime,
        }
